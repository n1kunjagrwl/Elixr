# identity — E2E Test Guide

> Last generated: 2026-05-17

## Business Intent

A user can create an Elixir account using only their phone number — no email, no password — by verifying a one-time code sent to their phone via SMS. Once registered, they can sign in from any device by repeating the OTP verification, stay signed in for up to 7 days via silent token refresh, and sign out to immediately revoke their session. Multiple devices can hold independent active sessions simultaneously; logging out on one device does not affect sessions on others. The identity domain is the sole authority on who a user is — every other domain trusts the `user_id` the auth middleware injects, never handling login logic themselves.

## Domain Scope

| Item | Detail |
|------|--------|
| Tables owned | `users`, `otp_requests`, `sessions`, `outbox` |
| Events published | `identity.UserRegistered` (on first OTP verification), `identity.UserLoggedIn` (on each successful login) |
| Events consumed | None — identity has no dependencies on other domains |
| Temporal workflows | `OTPDeliveryWorkflow` (OTP generation, bcrypt hash storage, Twilio Verify delivery with up to 3 retries at 2s / 4s / 8s backoff) |
| Slices covered | 01, 02, 03, 04 |

## Test Scenarios

---

### Scenario 1: Successful New User Registration

**Source slice**: `docs/slices/01-user-registration.md`
**Business intent**: A user with no existing account provides their phone number, receives an OTP via SMS, enters the code, and lands in the app with an active JWT session.
**Domains involved**: identity

#### Preconditions
- No `users` row exists for the phone number under test.
- Twilio Verify API is reachable (or stubbed to return success).

#### Steps
1. `POST /api/v1/auth/request-otp` `{"phone": "9876543210"}` → `200 OK` `{"message": "OTP sent"}` (response must be identical whether phone exists or not — see Scenario 5 for anti-enumeration).
2. _(Temporal `OTPDeliveryWorkflow` runs internally)_ — verify DB state before proceeding to step 3.
3. `POST /api/v1/auth/verify-otp` `{"phone": "+919876543210", "otp": "<valid-6-digit-code>"}` → `200 OK` `{"access_token": "<jwt>"}`; refresh token is set as an httpOnly cookie (`refresh_token`).

#### Assertions
- **DB**: `users` row inserted — `phone_e164 = "+919876543210"`, `created_at` is recent.
- **DB**: `otp_requests` row — `delivered = true`, `expires_at = created_at + 60s`, `attempt_count = 0`, `code_hash` is a non-empty bcrypt string (not the plaintext OTP).
- **DB**: `sessions` row inserted — `user_id` matches new user, `revoked_at IS NULL`, `expires_at ≈ now() + 7 days`, `access_token_jti` and `refresh_token_jti` are distinct UUIDs.
- **DB**: `outbox` row — `event_type = "identity.UserRegistered"`, payload contains `user_id` and `created_at`.
- **API response**: `200`, `access_token` present in JSON body; `refresh_token` set as httpOnly cookie; both are valid JWTs with `sub = <user_id>`.
- **Events**: `identity.UserRegistered` published to outbox in the same transaction as the `users` insert.
- **Side effects**: Access token expiry is 15 minutes; refresh token expiry is 7 days.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Phone number entered in local format (e.g., `9876543210`) | API normalises to E.164 (`+919876543210`) before any lookup or storage | [ ] |
| Phone number entered with spaces / dashes | Normalised to E.164 at the request boundary | [ ] |
| OTP expires (submitted after 60-second window) | `POST /api/v1/auth/verify-otp` → `400` or `422` with message "OTP expired. Request a new one." | [ ] |
| 3 consecutive wrong OTP submissions | Third failure sets `otp_requests.locked_until = now() + 5 minutes`; response → `429` or `403` "Too many attempts. Try again in N minutes." | [ ] |
| Same phone submitted twice before OTP completes | Second `POST /auth/register` creates a new `otp_requests` row; old row expires naturally; only the latest OTP is accepted | [ ] |
| Twilio delivery fails all 3 retries | `otp_requests.delivered = false`; user receives an error response; no `users` row is created | [ ] |

---

### Scenario 2: OTPDeliveryWorkflow — Happy Path

**Source slice**: `docs/slices/01-user-registration.md`, `docs/slices/02-user-login.md`
**Business intent**: The Temporal workflow generates a bcrypt-hashed OTP, persists it in `otp_requests`, and delivers the SMS via Twilio on the first attempt.
**Domains involved**: identity

#### Preconditions
- A registration or login request has been accepted (phone normalised, user lookup complete).
- Twilio Verify API stub returns HTTP 200 on first attempt.

#### Steps
1. Trigger `OTPDeliveryWorkflow` (via `POST /api/v1/auth/request-otp` as the entry point for both registration and login).
2. Inspect DB state after workflow completes.

#### Assertions
- **DB**: `otp_requests` row created — `code_hash` is a bcrypt hash (starts with `$2b$`), `expires_at = created_at + 60s`, `delivered = true`, `attempt_count = 0`.
- **DB**: No plaintext OTP stored anywhere in the database.
- **API response**: The initiating endpoint returns success with "OTP sent" (no OTP value in the response body).
- **Events**: None — OTP delivery is internal; no outbox event is published at this stage.
- **Side effects**: Exactly one Twilio Verify API call was made.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Twilio fails on attempt 1; succeeds on attempt 2 | Workflow retries after 2s; `delivered = true` on success; one `otp_requests` row | [ ] |
| Twilio fails on attempts 1–2; succeeds on attempt 3 | Workflow retries with exponential backoff (2s, 4s); `delivered = true` | [ ] |
| Twilio fails all 3 attempts (2s, 4s, 8s backoff) | Workflow marks `delivered = false`; error surfaced to user; no session or user row created | [ ] |

---

### Scenario 3: Successful Returning User Login

**Source slice**: `docs/slices/02-user-login.md`
**Business intent**: A user with an existing account verifies their phone via OTP and receives a new session without a new `users` row being created.
**Domains involved**: identity

#### Preconditions
- A `users` row already exists for the phone number under test.
- Twilio Verify API is reachable (or stubbed to return success).

#### Steps
1. `POST /api/v1/auth/request-otp` `{"phone": "+919876543210"}` → `200 OK` `{"message": "OTP sent"}`.
2. `POST /api/v1/auth/verify-otp` `{"phone": "+919876543210", "otp": "<valid-6-digit-code>"}` → `200 OK` `{"access_token": "<jwt>"}`; refresh token set as httpOnly cookie.

#### Assertions
- **DB**: No new `users` row created — `users` count for this phone remains 1.
- **DB**: New `sessions` row inserted — `user_id` matches existing user, `revoked_at IS NULL`, `expires_at ≈ now() + 7 days`.
- **DB**: `outbox` row — `event_type = "identity.UserLoggedIn"`, payload contains `user_id` and `session_id`.
- **API response**: `200`, `access_token` present in JSON body; `refresh_token` set as httpOnly cookie; both valid JWTs.
- **Events**: `identity.UserLoggedIn` published to outbox.
- **Side effects**: None. The pre-existing session (if any) is unaffected.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| User has a prior active session on another device | New `sessions` row added; prior session row untouched; both `revoked_at IS NULL` | [ ] |
| OTP expired (submitted after 60-second window) | `400` / `422` "OTP expired. Request a new one." | [ ] |
| `locked_until` is in the future (prior lockout) | Login rejected immediately with `429` / `403` "Too many attempts." before OTP is evaluated | [ ] |
| Resend OTP while prior OTP is still valid | New `otp_requests` row created; old row ignored; only latest OTP valid | [ ] |

---

### Scenario 4: Session Token Refresh

**Source slice**: `docs/slices/03-session-refresh.md`
**Business intent**: When a 15-minute access token expires, the app silently exchanges the still-valid refresh token for a new access token so the user is never interrupted.
**Domains involved**: identity

#### Preconditions
- User has an active `sessions` row (`revoked_at IS NULL`, `expires_at` in the future).
- Access token is expired (or can be simulated as expired).
- Refresh token is still within its 7-day window.

#### Steps
1. `POST /api/v1/auth/refresh` (no body required — refresh token is read from the httpOnly cookie) → `200 OK` `{"access_token": "<new-jwt>"}`.

#### Assertions
- **DB**: `sessions.access_token_jti` updated to the new JTI — old JTI is no longer present.
- **DB**: `sessions.refresh_token_jti` is unchanged.
- **DB**: `sessions.revoked_at` remains NULL.
- **API response**: `200`, new `access_token` present in JSON body; refresh token cookie unchanged.
- **Events**: None — token refresh does not publish an outbox event.
- **Side effects**: Old access token JTI is immediately invalid; subsequent requests using it return `401`.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Refresh token expired (7-day window passed) | `401` — session invalid; user must log in again with phone + OTP | [ ] |
| Session revoked (`revoked_at IS NOT NULL`) | `401` — refresh rejected; user forced to log in again | [ ] |
| Two parallel requests both hit 401 and both attempt refresh simultaneously | First request succeeds, updates `access_token_jti`; second request gets `401` on the refresh call (stale JTI); frontend retries with the token from the first success | [ ] |
| Refresh called without the cookie (no refresh token) | `401` / `422` — missing or invalid refresh token rejected | [ ] |

---

### Scenario 5: Anti-Enumeration on Login

**Source slice**: `docs/slices/02-user-login.md`
**Business intent**: The login flow returns an identical response for registered and unregistered phone numbers to prevent attackers from discovering which numbers have accounts.
**Domains involved**: identity

#### Preconditions
- Phone number `+919999999999` has no `users` row.

#### Steps
1. `POST /api/v1/auth/request-otp` `{"phone": "+919999999999"}` → `200 OK` `{"message": "OTP sent"}`.
2. Wait for any SMS — none arrives.
3. `POST /api/v1/auth/verify-otp` `{"phone": "+919999999999", "otp": "<any-code>"}` → error response (OTP invalid or OTP workflow silently failed).

#### Assertions
- **DB**: No `users` row created for `+919999999999`.
- **DB**: No `otp_requests` row created (or workflow detects no user and silently exits without creating one — exact behaviour to be confirmed; see TODO).
- **API response**: Step 1 must return `200` with the same body shape as a known-phone login (`{"message": "OTP sent"}`). Response time should not differ materially from a known-phone request (timing oracle attack surface).
- **Events**: No outbox events published.
- **Side effects**: No SMS dispatched to Twilio.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Attacker submits known phone followed by unknown phone | Both return identical HTTP status and body | [ ] |
| Response time for unknown phone vs. known phone | Difference must be negligible (< 50ms) to prevent timing-based enumeration | [ ] |

---

### Scenario 6: User Logout (Current Session Revocation)

**Source slice**: `docs/slices/04-user-logout.md`
**Business intent**: The user explicitly signs out, and the server immediately revokes the current session so all tokens for that session become invalid.
**Domains involved**: identity

#### Preconditions
- User is authenticated with an active, non-expired session.

#### Steps
1. `POST /api/v1/auth/logout` (Authorization: `Bearer <access-token>`) → `204 No Content`; refresh token cookie is cleared.
2. Attempt to use the revoked access token on any protected endpoint → `401`.
3. Attempt to use the revoked refresh token on `POST /api/v1/auth/refresh` → `401`.

#### Assertions
- **DB**: `sessions.revoked_at` is set (not NULL) for the session matching `access_token_jti`.
- **DB**: `sessions` row is NOT deleted — kept for audit.
- **API response** (step 2): `401` using old access token.
- **API response** (step 3): `401` using old refresh token.
- **Events**: None — logout does not publish an outbox event.
- **Side effects**: Other sessions for the same user (on other devices) remain unaffected; their `revoked_at` is still NULL.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Logout called with an already-expired access token | Auth middleware may reject before reaching logout handler; frontend should clear local state regardless | [ ] |
| Network failure during logout (request never reaches server) | Session not revoked server-side; local tokens cleared by frontend; session remains valid until natural expiry (7 days) — accepted trade-off | [ ] |
| User wants to log out all devices simultaneously | Not supported — each session must be revoked individually; "log out all sessions" is a future feature | [ ] |
| Second request with revoked session token | Returns `401`; does not change `revoked_at` (idempotent read of the revoked state) | [ ] |

---

### Scenario 7: Set Display Name After Registration (Optional Step)

**Source slice**: `docs/slices/01-user-registration.md`
**Business intent**: After account creation, a user can optionally provide a display name; the app also works if this step is skipped.
**Domains involved**: identity

#### Preconditions
- User has just completed OTP verification and has a valid access token (Scenario 1 complete).

#### Steps
1. `PATCH /api/v1/users/me` `{"name": "Nikunj"}` (Authorization: `Bearer <access-token>`) → `200 OK` `{"id": "<uuid>", "name": "Nikunj"}`.
   _(Note: exact path is a TODO — see Coverage Gaps. `/api/v1/users/me` is the expected convention but must be confirmed from `src/elixir/domains/identity/api.py`.)_

#### Assertions
- **DB**: `users.name = "Nikunj"` for the row matching the authenticated `user_id`.
- **API response**: `200`, name reflected in response body.
- **Events**: None — name update does not publish an outbox event.
- **Side effects**: `users_public` SQL view now returns the updated name.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| User skips name entry (never calls PATCH) | `users.name` remains NULL; app functions normally; name not required for any business logic | [ ] |
| Name submitted as empty string | Behaviour undefined in slice — clarification needed (see TODO) | [ ] |
| Name submitted after re-login (not first session) | Update succeeds; this is not registration-only behaviour | [ ] |

---

## Known Inconsistencies

Entries from `docs/business-intent/INCONSISTENCIES.md` that involve the identity domain:

- **[3.1] Logout is device-scoped; multiple sessions exist simultaneously**: `business-intent/identity.md` describes login and logout without mentioning that a user can have multiple active sessions across multiple devices simultaneously and that logout only revokes the current session. The "log out all sessions" operation is explicitly called out as **not supported** in slice 04. Impact on testing: Scenario 6 must assert that other sessions remain active after a single-device logout, and edge case tables must flag "log out all devices" as a non-functional path. Status: `flag-in-test`.

- **[3.2] Anti-enumeration on login / registration**: `business-intent/identity.md` does not mention the identical-response design for unknown phone numbers. This is a security behaviour with a direct UX consequence — a user who enters an unregistered number sees "OTP sent" but receives no SMS. Impact on testing: Scenario 5 must verify response body, status code, and response timing are indistinguishable between known and unknown phones. Any divergence is a security regression. Status: `flag-in-test`.

---

## Coverage Gaps

| Gap | Source | TODO |
|-----|--------|------|
| ~~Exact HTTP path and method for each identity endpoint are not specified in the slices~~ | ~~`docs/slices/01-04-*.md`~~ | ✅ Resolved — confirmed from `src/elixir/domains/identity/api.py`: `POST /api/v1/auth/request-otp`, `POST /api/v1/auth/verify-otp`, `POST /api/v1/auth/refresh` (cookie-based), `POST /api/v1/auth/logout` (→ 204) |
| Behaviour when `POST /auth/login` is called for an unknown phone at the `otp_requests` level — whether a row is created or the workflow silently exits | `docs/slices/02-user-login.md` — "OTP workflow will detect no users row and silently fail" | [ ] confirm DB state in Scenario 5 assertion |
| `PATCH /api/v1/users/me` endpoint — exact path not yet confirmed from source; request schema and empty-name behaviour unknown | `docs/slices/01-user-registration.md` — Step 5 mentions name update but provides no endpoint details | [ ] confirm from `src/elixir/domains/identity/api.py` and add contract |
| No slice covers "resend OTP" as an explicit user-initiated action (distinguished from re-submitting the registration/login form) | Implied by `slices/01` and `slices/02` edge cases ("Resend OTP") | [ ] write slice `05-resend-otp.md` |
| `OTPDeliveryWorkflow` partial failure states (e.g., OTP created but Twilio call never started) are not described | `docs/workflows/otp-delivery.md` referenced but not read — may contain detail | [ ] read `docs/workflows/otp-delivery.md` and add sub-scenarios if needed |

---

## TODO

- [x] ✅ Resolved — Confirm identity API endpoint paths — Paths confirmed from `src/elixir/domains/identity/api.py`: `POST /api/v1/auth/request-otp`, `POST /api/v1/auth/verify-otp`, `POST /api/v1/auth/refresh` (reads refresh token from httpOnly cookie, no body), `POST /api/v1/auth/logout` (→ 204, clears cookie). All Step assertions have been updated.
- [ ] Confirm HTTP status codes for OTP failure responses (`400` vs `422` vs `429`) — **Blocker**: Scenarios 1, 3 edge cases cite ambiguous status codes — **Next step**: Check `src/elixir/domains/identity/api.py` and `services.py` for the exact codes returned on OTP expiry, wrong code, and lockout.
- [ ] Clarify what happens at the DB level when `POST /api/v1/auth/request-otp` is called for an unknown phone — does `OTPDeliveryWorkflow` create an `otp_requests` row before detecting no user? — **Blocker**: Scenario 5 DB assertion cannot be finalised without this — **Next step**: Review `OTPDeliveryWorkflow` activity code or `docs/workflows/otp-delivery.md`.
- [ ] Determine the exact response shape of `POST /api/v1/auth/refresh` — confirmed it returns `{"access_token": "<jwt>"}` with no new refresh token in the body; verify that the cookie is also refreshed or remains unchanged — **Blocker**: Scenario 4 cookie-refresh assertion is incomplete — **Next step**: Check refresh endpoint implementation in `src/elixir/domains/identity/api.py`.
- [ ] Confirm exact path for `PATCH /api/v1/users/me` (display name update) from `src/elixir/domains/identity/api.py` — **Blocker**: Scenario 7 Step 1 path is an inferred convention, not yet read from source.
- [ ] Add a Playwright E2E test file at `client/tests/identity/` covering Scenarios 1–7 — **Blocker**: HTTP status codes for OTP failure responses (TODO above) — **Next step**: Scaffold test file per `docs/frontend-development-guidelines.md`.
- [ ] Verify response time parity for anti-enumeration (Scenario 5, timing edge case) — requires a load-test or timing harness — **Blocker**: Not yet tested — **Next step**: Add a `pytest` timing assertion or document as a manual security test.
