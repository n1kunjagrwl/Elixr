# Slice: Session Token Refresh

## User Goal
Continue using the app without interruption when the 15-minute access token expires.

## Trigger
The frontend receives a 401 response on any API call and detects a valid refresh token is still available (refresh token expiry is 7 days).

## Preconditions
- The user has an active session (`sessions` row with `revoked_at IS NULL`).
- The refresh token has not expired (`expires_at` is in the future).
- The session has not been revoked.

## Steps

### Step 1: Frontend Detects 401
**User action**: None — happens transparently in the app.
**System response**: The frontend intercepts the 401 and queues the original request. It sends the refresh token to `POST /auth/refresh`.

### Step 2: Refresh Token Validated
**User action**: None.
**System response**: Auth middleware looks up the `sessions` row by `refresh_token_jti`. Checks:
- `revoked_at IS NULL` — session must not be revoked.
- `expires_at` in the future — refresh token must not be expired.
If both pass, a new access token is issued with a new `jti`. The `sessions` row is updated: `access_token_jti` is replaced with the new JTI. The refresh token JTI is unchanged (refresh tokens are long-lived and single-use only in the sense that the session row tracks the current one).

### Step 3: Original Request Retried
**User action**: None.
**System response**: Frontend replaces the stale access token in memory, retries the original request with the new token. User experience is seamless — no logout, no disruption.

## Domains Involved
- **identity**: Session lookup, access token re-issuance, `sessions` table update.

## Edge Cases & Failures
- **Refresh token also expired**: The 7-day window has passed. Session is invalid. User is redirected to the login flow (phone + OTP required again).
- **Session revoked (logged out on another device)**: `revoked_at IS NOT NULL`. Refresh is rejected. User is forced to log in again.
- **Concurrent refresh attempts**: If two parallel requests both hit 401 and both try to refresh simultaneously, one will succeed and update `access_token_jti`. The other will have an invalidated refresh token JTI and receive a 401 on the refresh call — the frontend should retry with the token returned by the first successful refresh.

## Success Outcome
User continues the app session seamlessly with a new access token, without re-entering their OTP.
