# Workflow: OTPDeliveryWorkflow

**Domain**: `identity`  
**Trigger**: `POST /auth/request-otp`  
**Temporal schedule**: Not scheduled — triggered on demand  

---

## Purpose

Delivers a one-time password to the user's phone via Twilio and handles retries if delivery fails. This workflow is deliberately short-lived — it either delivers the OTP within a few seconds or fails cleanly. The OTP is valid for 60 seconds regardless of workflow status.

---

## Full Sequence

### Step 1 — Request received

```
POST /auth/request-otp
  Body: { phone: "+919876543210" }

identity service:
  1. Normalise phone to E.164 format
  2. Fetch or create user record (users table)
  3. Check for active lockout:
     SELECT locked_until FROM otp_requests
     WHERE user_id = ? ORDER BY created_at DESC LIMIT 1
     → If locked_until > now(): return 429 (too many attempts)
  4. Check rate limit: max 3 OTP requests per phone per 15 minutes
     → If exceeded: return 429
  5. Generate 6-digit OTP: secrets.randbelow(900000) + 100000
  6. Hash: bcrypt.hash(str(otp), rounds=10)
  7. Insert otp_requests row:
     {user_id, code_hash, expires_at: now()+60s, attempt_count: 0}
  8. Trigger OTPDeliveryWorkflow(user_id, phone_e164, otp_request_id)
  9. Return 200: { message: "OTP sent", expires_in: 60 }
```

Note: The plaintext OTP is passed to the Temporal workflow as a workflow input (it lives in Temporal's event history, which is encrypted at rest in production). The workflow does not re-generate it — only dispatches it.

### Step 2 — OTPDeliveryWorkflow runs

```
Workflow input: { user_id, phone_e164, otp_code, otp_request_id }

Activity: send_otp_via_twilio(phone_e164, otp_code)
  → Twilio Verify API: POST /Services/{service_sid}/Verifications
    or raw SMS: POST /Accounts/{sid}/Messages
  → On HTTP 2xx: mark otp_requests.delivered = true, return success
  → On HTTP 4xx (invalid number, country blocked): do not retry, return failure
  → On HTTP 5xx or timeout: raise and let Temporal retry

Temporal retry policy for this activity:
  maximum_attempts: 3
  initial_interval: 2s
  backoff_coefficient: 2.0
  (2s → 4s → 8s)

If all 3 attempts fail:
  → Set otp_requests.delivered = false
  → Workflow completes with failure result
  → The /request-otp endpoint already returned 200; the user sees the error
    when they wait for an OTP that never arrives
  → Frontend should show "Resend OTP" after 30 seconds
```

### Step 3 — OTP verification

```
POST /auth/verify-otp
  Body: { phone: "+919876543210", otp: "483921" }

identity service:
  1. Fetch latest otp_request for this user:
     SELECT * FROM otp_requests
     WHERE user_id = ? ORDER BY created_at DESC LIMIT 1

  2. Check expiry:
     → If expires_at < now(): return 400 "OTP expired"

  3. Check lockout:
     → If locked_until > now(): return 429

  4. Verify OTP:
     → bcrypt.verify(submitted_otp, otp_request.code_hash)
     → If mismatch:
          UPDATE otp_requests SET attempt_count = attempt_count + 1
          If attempt_count >= 3:
            UPDATE otp_requests SET locked_until = now() + 5min
          Return 400 "Invalid OTP"

  5. On match:
     → Generate JWT pair:
          access_token:  exp = now() + 15min, jti = uuid4()
          refresh_token: exp = now() + 7days, jti = uuid4()
     → Insert sessions row: {user_id, access_token_jti, refresh_token_jti, expires_at}
     → Return 200: { access_token, refresh_token }
     → Set refresh_token in HttpOnly cookie
```

---

## Token Refresh

```
POST /auth/refresh
  Body: refresh_token (or read from HttpOnly cookie)

  1. Decode refresh token, extract jti
  2. Lookup session by refresh_token_jti
  3. Check session.expires_at > now() AND session.revoked_at IS NULL
  4. Issue new access_token with new jti
  5. Update sessions.access_token_jti = new jti
  6. Return new access_token
```

The refresh token itself is not rotated — it retains its 7-day expiry from original login. Rotating the access token on every refresh is sufficient for session management at this scale.

---

## Logout

```
POST /auth/logout

  1. Decode access token, extract jti
  2. Lookup session by access_token_jti
  3. Set sessions.revoked_at = now()
  4. Clear refresh_token cookie
  5. Return 200
```

After revocation, the auth middleware's `revoked_at IS NULL` check immediately blocks all requests from this session, even if the access token has not yet expired.

---

## Security Notes

- OTP is 6 digits from `secrets.randbelow` (cryptographically secure). Not from `random`.
- bcrypt hash with 10 rounds: ~100ms on modern hardware. This adds meaningful cost to brute-force attempts while being imperceptible to the user.
- `locked_until` is set per `otp_request` row, not per user — a new OTP request creates a new row. The lockout check reads the most recent row. This means a lockout from 3 bad verification attempts blocks further attempts on that OTP request, but a new `request-otp` call (which is separately rate-limited) creates a fresh row.
- The rate limit on `/request-otp` (3 per phone per 15 min) prevents OTP flooding, which would incur Twilio cost and annoy the user.
