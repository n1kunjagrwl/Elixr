# Slice: User Login

## User Goal
Sign in to an existing Elixir account to resume tracking finances.

## Trigger
User opens the app on a new device, or their session has expired and they are prompted to log in again.

## Preconditions
- User has a registered account (`users` row exists for the phone number).
- Twilio Verify API is reachable.

## Steps

### Step 1: Enter Phone Number
**User action**: Enters phone number and submits.
**System response**: API normalises to E.164 and looks up `users` by `phone_e164`. If found, triggers `OTPDeliveryWorkflow`. The response to the frontend is identical whether the phone exists or not (to avoid user enumeration).

### Step 2: OTP Delivery
**User action**: Waits for SMS.
**System response**: Temporal workflow generates OTP, bcrypt-hashes it, stores `otp_requests` row (`expires_at = now() + 60s`), and sends via Twilio Verify with up to 3 retries.

### Step 3: Enter OTP
**User action**: Types the 6-digit code.
**System response**: API validates against `otp_requests` — checks lock status, expiry, and bcrypt match. On failure, increments `attempt_count`; sets `locked_until` after 3 failures.

### Step 4: Session Issued
**User action**: None.
**System response**: On successful OTP verification for an existing user, no new `users` row is created. A new `sessions` row is created. Access token (15 min) and refresh token (7 days) are issued and returned. The `UserLoggedIn` event is published (no current consumers — retained for audit). User lands on app home screen.

## Domains Involved
- **identity**: Phone lookup, OTP validation, session creation, JWT issuance.

## Edge Cases & Failures
- **Unknown phone number**: Flow proceeds identically to a known phone (user enumeration prevention). The OTP workflow will detect no `users` row and silently fail — the user sees "OTP sent" but no SMS arrives. After timeout they may be prompted to register.
- **OTP expired**: User must request a new one via "Resend OTP". A fresh `otp_requests` row is created; the old one is ignored.
- **Account locked**: `locked_until` is in the future. Login is rejected for 5 minutes.
- **Prior active session on another device**: The new session is created independently. Multiple active sessions are allowed — each has its own `access_token_jti` and `refresh_token_jti`. The prior session remains valid until it expires or the user explicitly logs out.

## Success Outcome
User has a fresh JWT session and is inside the app.
