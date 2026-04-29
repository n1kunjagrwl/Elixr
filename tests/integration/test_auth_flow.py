"""
Integration tests: full auth flow (OTP request → OTP verify → access protected endpoint).

These tests use a real PostgreSQL container via testcontainers and exercise the full
HTTP request/response cycle with real DB reads and writes. No mocking of the database.

Run with:
    uv run pytest tests/integration/ -v
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# Phone numbers used in tests — use distinct numbers per class to avoid state bleed
# across test classes that share the same session-scoped DB.
PHONE = "+919876543210"
PHONE_B = "+919876543211"  # used by TestDuplicateRegistration


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _do_request_otp(client: AsyncClient, phone: str) -> None:
    """POST /auth/request-otp and assert 200."""
    resp = await client.post("/auth/request-otp", json={"phone": phone})
    assert resp.status_code == 200, f"request-otp failed: {resp.text}"


async def _do_full_login(client: AsyncClient, app, phone: str) -> dict:
    """
    Full login: request OTP → capture OTP from mock → verify OTP.
    Returns the parsed JSON from verify-otp (contains access_token).
    The refresh_token is stored in the response cookie automatically.
    """
    await _do_request_otp(client, phone)
    otp_code = app.state._last_otp.get("code")
    assert otp_code is not None, "OTP was not captured from mock Twilio"

    resp = await client.post("/auth/verify-otp", json={"phone": phone, "otp": otp_code})
    assert resp.status_code == 200, f"verify-otp failed: {resp.text}"
    return resp.json()


# ── Test Suite ────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestUserRegistrationAndLogin:
    """Full auth flow against a real PostgreSQL DB."""

    async def test_request_otp_creates_user_and_returns_200(
        self, integration_client: AsyncClient
    ):
        """
        POST /auth/request-otp with a valid E.164 phone should:
        - Return HTTP 200
        - Return a body with 'message' and 'expires_in' fields
        """
        resp = await integration_client.post("/auth/request-otp", json={"phone": PHONE})
        assert resp.status_code == 200
        body = resp.json()
        assert "message" in body
        assert "expires_in" in body
        assert isinstance(body["expires_in"], int)
        assert body["expires_in"] > 0

    async def test_verify_otp_returns_tokens(
        self, integration_client: AsyncClient, integration_app
    ):
        """
        After requesting an OTP, verifying the correct code should:
        - Return HTTP 200
        - Return 'access_token' and 'token_type' in the body
        - Set a 'refresh_token' cookie
        """
        tokens = await _do_full_login(integration_client, integration_app, PHONE)

        assert "access_token" in tokens
        assert tokens.get("token_type") == "bearer"

        # refresh_token is set as an httponly cookie, not in the response body
        assert "refresh_token" in integration_client.cookies

    async def test_protected_endpoint_requires_auth(
        self, integration_client: AsyncClient
    ):
        """
        GET /accounts without an Authorization header must return 401.
        """
        resp = await integration_client.get("/accounts")
        assert resp.status_code == 401

    async def test_protected_endpoint_accepts_valid_token(
        self, integration_client: AsyncClient, integration_app
    ):
        """
        GET /accounts with a valid Bearer token must return 200 (empty list is fine —
        no accounts have been created yet for this user).
        """
        tokens = await _do_full_login(integration_client, integration_app, PHONE)
        access_token = tokens["access_token"]

        resp = await integration_client.get(
            "/accounts",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_refresh_token_gives_new_access_token(
        self, integration_client: AsyncClient, integration_app
    ):
        """
        POST /auth/refresh with a valid refresh_token cookie must return 200 with
        a new 'access_token'.
        """
        # Perform full login — sets the refresh_token cookie on the client
        await _do_full_login(integration_client, integration_app, PHONE)
        assert "refresh_token" in integration_client.cookies, (
            "refresh_token cookie not set"
        )

        resp = await integration_client.post("/auth/refresh")
        assert resp.status_code == 200, f"refresh failed: {resp.text}"
        body = resp.json()
        assert "access_token" in body
        assert body.get("token_type") == "bearer"

    async def test_logout_revokes_refresh_token(
        self, integration_client: AsyncClient, integration_app
    ):
        """
        After a successful logout, the session row is revoked in the DB —
        POST /auth/refresh must return 401 because refresh_session checks revoked_at.

        Note: stateless JWTs remain valid until they expire — the access token is NOT
        invalidated immediately; only the session row (and therefore refresh) is revoked.
        This is by design: the access token has a short TTL (15 min default).
        """
        tokens = await _do_full_login(integration_client, integration_app, PHONE)
        access_token = tokens["access_token"]

        # Confirm the access token works before logout
        resp = await integration_client.get(
            "/accounts",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200

        # Save the refresh_token cookie value BEFORE logout clears it
        refresh_token_before_logout = integration_client.cookies.get("refresh_token")
        assert refresh_token_before_logout is not None, (
            "refresh_token cookie should be set after login"
        )

        # Confirm refresh works before logout
        resp_before = await integration_client.post("/auth/refresh")
        assert resp_before.status_code == 200

        # Logout — revokes the session row in the DB and clears the cookie
        resp = await integration_client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 204, f"logout failed: {resp.text}"

        # Re-inject the refresh_token cookie to simulate a client that still has it
        # (the cookie was cleared by the logout response's Set-Cookie: Max-Age=0).
        # This proves the revocation is DB-level, not just cookie-clearing.
        integration_client.cookies.set("refresh_token", refresh_token_before_logout)
        resp_after = await integration_client.post("/auth/refresh")
        # The session row has revoked_at set — refresh must return 4xx
        assert resp_after.status_code in (401, 403), (
            f"Expected 401/403 after logout on refresh but got {resp_after.status_code}: {resp_after.text}"
        )


@pytest.mark.integration
class TestDuplicateRegistration:
    """Idempotency of OTP request for an already-registered phone."""

    async def test_second_login_reuses_existing_user(
        self, integration_client: AsyncClient, integration_app
    ):
        """
        Requesting an OTP twice with the same phone number must:
        - Return 200 both times (idempotent — user is created on first request)
        - Allow the second OTP to be verified successfully (the user already exists)
        """
        # First request — creates the user
        resp1 = await integration_client.post(
            "/auth/request-otp", json={"phone": PHONE_B}
        )
        assert resp1.status_code == 200

        # Second request — user already exists; still 200
        resp2 = await integration_client.post(
            "/auth/request-otp", json={"phone": PHONE_B}
        )
        assert resp2.status_code == 200

        # Verify with the latest OTP — proves there is exactly one underlying user
        otp_code = integration_app.state._last_otp.get("code")
        assert otp_code is not None

        resp3 = await integration_client.post(
            "/auth/verify-otp", json={"phone": PHONE_B, "otp": otp_code}
        )
        assert resp3.status_code == 200
        body = resp3.json()
        assert "access_token" in body
