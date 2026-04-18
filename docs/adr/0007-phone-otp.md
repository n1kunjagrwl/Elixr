# ADR-0007: Phone OTP over Password Authentication

**Date**: 2026-04-18  
**Status**: Accepted

---

## Context

Elixir stores sensitive financial data. Authentication must be strong enough to protect that data while being convenient enough that users actually engage with the app frequently (daily expense logging requires low-friction login).

Options for authentication:
1. Email + password
2. Social OAuth (Google, Apple)
3. Phone number + OTP (passwordless)
4. Passkeys (WebAuthn — Face ID / Touch ID)

The primary target audience is Indian mobile users who are accustomed to OTP-based authentication from banking apps, UPI apps, and e-commerce. The phone number is a natural unique identifier in this context — most Indian users have and protect their phone number.

---

## Decision

Use **phone number + OTP** as the sole authentication method. No passwords. Sessions managed via JWT (15-minute access token, 7-day refresh token). OTP delivered via Twilio.

---

## Consequences

### Positive

- **No password storage.** There are no passwords to hash, breach-monitor, or reset. A DB breach leaks no credentials that could be reused on other services.
- **No password reset flow.** "Forgot my password" is a significant source of user friction and support burden. It does not exist here — OTP is always the path.
- **Familiar UX for Indian users.** OTP login is the standard in India across banking, UPI apps, food delivery, and e-commerce. Users understand the flow immediately.
- **Phone number as unique identifier.** One phone number = one account. No need for email uniqueness enforcement, email verification flows, or username conflicts.
- **Inherently two-factor.** Knowing the phone number is not enough — you must also have access to the device that receives the OTP. This is effectively 1.5FA (possession of phone + knowledge of number).

### Negative / Trade-offs

- **Twilio dependency and cost.** Each login requires an SMS, which has a per-message cost (approximately ₹6–8 per OTP in India). For a personal app with infrequent logins and 7-day sessions, this cost is minimal. At scale, if abuse occurs (OTP flooding), costs could spike — mitigated by rate limiting (max 3 OTP requests per phone per 15 minutes).
- **Phone number required.** Users without a phone (or who do not wish to share their phone number) cannot use the app. This is an acceptable constraint for the target audience.
- **OTP interception risk.** SMS OTPs can theoretically be intercepted via SIM swap attacks or SS7 vulnerabilities. Mitigated by: 60-second expiry (short window for interception), 3-attempt lockout, and the fact that intercepting an OTP also requires knowing the target user's phone number. This threat model is acceptable for a personal finance app — bank-grade security is not the goal.
- **Users must have phone reception to log in.** OTP delivery requires SMS delivery. In areas with poor connectivity, this can be unreliable. Mitigated by: 7-day refresh tokens mean users rarely need to log in fresh while in the field.

---

## Session Management

- **Access token**: JWT, 15-minute expiry, stateless validation (signature + expiry). Stored in memory on the client (not localStorage — XSS risk).
- **Refresh token**: JWT, 7-day expiry, validated against `sessions` table (revocation check). Stored in an HttpOnly, Secure, SameSite=Strict cookie.
- **Revocation**: Setting `sessions.revoked_at` immediately invalidates the session for all subsequent requests. The auth middleware checks `revoked_at IS NULL` on every refresh token use.

---

## Future: Biometric Auth via WebAuthn

Once a user has an established session, they can register a WebAuthn credential (Face ID, Touch ID, hardware key) for subsequent logins. The flow:

1. User logs in via OTP (first time or after credential expiry)
2. User registers a WebAuthn credential: `navigator.credentials.create()`
3. On next login: `navigator.credentials.get()` — no OTP required
4. WebAuthn credential stored server-side (public key only); no sensitive data

This makes frequent logins frictionless while keeping OTP as the fallback and account recovery mechanism. Not implemented initially — architecture does not preclude it.

---

## Alternatives Considered

**Email + password**: Requires hashing (bcrypt), breach monitoring, password reset via email, email verification, minimum password complexity enforcement. Higher implementation and maintenance cost with no security advantage over OTP for this audience. Ruled out.

**Google/Apple OAuth**: Familiar "Sign in with Google" flow. No Twilio cost. Requires the user to have a Google or Apple account — not universal for the target audience. Also creates dependency on Google/Apple for authentication — if their OAuth is down, users cannot log in. Ruled out as the primary method; may be added as an additional option later.

**Passkeys only (WebAuthn)**: Passkeys are excellent UX and have strong security properties. They require an existing session or account recovery mechanism to bootstrap — which brings us back to needing OTP or email as the initial auth method. Passkeys are a future enhancement layer, not a replacement for the bootstrapping mechanism.
