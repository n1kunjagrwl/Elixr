# Slice: User Registration

## User Goal
Create a new Elixir account using a phone number to start tracking personal finances.

## Trigger
User opens the app for the first time and taps "Create account".

## Preconditions
- User has no existing account with this phone number.
- Twilio Verify API is reachable.

## Steps

### Step 1: Enter Phone Number
**User action**: Enters phone number (any local format) and submits.
**System response**: API normalises the number to E.164 format (e.g., `+919876543210`) at the request boundary. Checks `users` table — phone not found, so a new `users` row is NOT yet created. The `OTPDeliveryWorkflow` Temporal workflow is triggered.

### Step 2: OTP Delivery
**User action**: Waits for SMS.
**System response**: Temporal activity generates a 6-digit OTP, hashes it with bcrypt, creates an `otp_requests` row (`expires_at = now() + 60s`, `delivered = false`). Twilio Verify API sends the SMS. On success, `delivered = true` is set. If Twilio fails, the workflow retries up to 3 times with exponential backoff (2s, 4s, 8s). If all retries fail, the error surfaces to the user.

### Step 3: Enter OTP
**User action**: Types the 6-digit code received via SMS.
**System response**: API looks up the `otp_requests` row for this user. Checks:
- `locked_until` — if set and in the future, reject immediately ("Too many attempts. Try again in {N} minutes").
- `expires_at` — if expired, reject ("OTP expired. Request a new one").
- bcrypt compare of submitted code against `code_hash`.
If the code is wrong, `attempt_count` is incremented. When `attempt_count` reaches 3, `locked_until = now() + 5 minutes` is set.

### Step 4: Account Created
**User action**: None — happens automatically on first successful OTP verification.
**System response**: A new `users` row is inserted with the E.164 phone. A `sessions` row is created (`access_token_jti`, `refresh_token_jti`, `expires_at = now() + 7 days`). JWT access token (15 min) and refresh token (7 days) are issued. The `UserRegistered` event is published via outbox. User is redirected to onboarding.

### Step 5: Set Display Name (Optional)
**User action**: Enters their name or skips.
**System response**: If provided, `users.name` is updated. Name is used for display only — not required for any business logic.

## Domains Involved
- **identity**: Owns the entire flow — phone storage, OTP lifecycle, session creation, JWT issuance.
- **notifications** (future): `UserRegistered` event reserved for an onboarding domain.

## Edge Cases & Failures
- **Phone already registered**: The API finds an existing `users` row. Registration is declined — user is directed to the login flow.
- **OTP expired (60-second window)**: Verification is rejected. User must request a new OTP.
- **3 failed OTP attempts**: Account locked for 5 minutes. User sees a countdown before they can try again.
- **Twilio delivery failure after 3 retries**: Workflow surfaces an error; user is shown a "We couldn't send your OTP — please try again" message.
- **Same phone submitted twice before OTP completes**: The second request generates a new `otp_requests` row; the old one expires naturally. Only the latest OTP is valid.

## Success Outcome
User has an active Elixir account, a valid JWT session, and lands on the app home screen ready to add accounts or upload statements.
