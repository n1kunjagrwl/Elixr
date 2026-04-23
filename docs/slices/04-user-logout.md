# Slice: User Logout

## User Goal
Sign out of the current device and invalidate the active session.

## Trigger
User taps "Log out" in settings.

## Preconditions
- User is authenticated with an active session.

## Steps

### Step 1: Tap Log Out
**User action**: Taps "Log out" and confirms the confirmation dialog.
**System response**: `POST /auth/logout` is called with the current access token.

### Step 2: Session Revoked
**User action**: None.
**System response**: Auth middleware identifies the `sessions` row by `access_token_jti`. Sets `sessions.revoked_at = now()`. Both the access and refresh tokens for this session are now invalid — the auth middleware checks `revoked_at IS NULL` on every subsequent request. The `sessions` row is kept for audit purposes; it is never deleted.

### Step 3: Tokens Cleared
**User action**: None.
**System response**: Frontend clears the access token and refresh token from local storage/memory. User is redirected to the login screen.

## Domains Involved
- **identity**: Session revocation via `revoked_at`.

## Edge Cases & Failures
- **Logout called with an already-expired access token**: Auth middleware may reject the request before reaching the logout handler. The frontend should attempt logout with the refresh token if the access token is expired, or simply clear local state if both have expired.
- **Network failure during logout**: The session is not revoked server-side. The user appears logged out on the device (local tokens cleared), but the server session remains valid until natural expiry (7 days). This is an acceptable trade-off — sessions expire on their own schedule.
- **User wants to log out all devices**: Not currently supported as a single operation. Each session must be revoked individually. (Future: "log out all sessions" would set `revoked_at` on all sessions for the user.)

## Success Outcome
The user's session is revoked server-side and local tokens are cleared. Any future request with the old tokens returns 401.
