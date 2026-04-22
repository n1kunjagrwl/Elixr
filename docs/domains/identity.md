# Domain: identity

## Responsibility

Manages user accounts, authentication, and sessions. The identity domain is the sole owner of who a user is and whether they are allowed to access the system. It handles phone-number registration, OTP generation and delivery via Twilio, JWT issuance, and session lifecycle (creation, refresh, revocation). No other domain is aware of how authentication works — they receive a validated `user_id` from the auth middleware and trust it.

---

## Tables Owned

### `users`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | Internal user identifier |
| `phone_e164` | `text` UNIQUE NOT NULL | Phone in E.164 format e.g. `+919876543210` |
| `name` | `text` | Display name (user-provided, optional initially) |
| `created_at` | `timestamptz` | Account creation time |

Phone is stored in E.164 format to ensure consistent formatting regardless of how the user enters it. It is the unique identifier for login.

### `otp_requests`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | → `users.id` (within-domain FK) |
| `code_hash` | `text` NOT NULL | bcrypt hash of the 6-digit OTP — never stored in plaintext |
| `expires_at` | `timestamptz` NOT NULL | `now() + 60 seconds` |
| `attempt_count` | `int` DEFAULT 0 | Incremented on each failed verification |
| `locked_until` | `timestamptz` | Set to `now() + 5 minutes` after 3 failed attempts |
| `delivered` | `bool` DEFAULT false | Set true once Twilio confirms delivery |
| `created_at` | `timestamptz` | — |

### `sessions`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | → `users.id` (within-domain FK) |
| `access_token_jti` | `uuid` UNIQUE | JWT ID of the active access token |
| `refresh_token_jti` | `uuid` UNIQUE | JWT ID of the active refresh token |
| `expires_at` | `timestamptz` | When the refresh token expires (7 days) |
| `revoked_at` | `timestamptz` | Set on logout — both tokens are invalidated |
| `created_at` | `timestamptz` | — |

### `outbox`
Standard outbox table. See [data-model.md](../data-model.md).

---

## SQL Views Exposed

### `users_public`
```sql
CREATE VIEW users_public AS
SELECT id, name FROM users;
```
Exposes user ID and name only. Phone number is never accessible to other domains.

---

## Events Published

### `UserRegistered`
```python
@dataclass
class UserRegistered:
    event_type = "identity.UserRegistered"
    user_id: UUID
    created_at: datetime
```
Published when a new user account is created (first OTP verification). Consumed by: _(future: onboarding domain)_

### `UserLoggedIn`
```python
@dataclass
class UserLoggedIn:
    event_type = "identity.UserLoggedIn"
    user_id: UUID
    session_id: UUID
```
Published on successful login. Currently no consumers — retained for audit and future analytics.

---

## Events Subscribed

None. The identity domain has no dependencies on other domains.

---

## Service Methods Exposed

No direct cross-domain service calls. Other domains receive only the validated `user_id` via JWT middleware.

---

## Temporal Workflow

### `OTPDeliveryWorkflow`

See [workflows/otp-delivery.md](../workflows/otp-delivery.md) for the full flow.

Summary:
1. Generate 6-digit OTP, hash with bcrypt, store in `otp_requests`
2. Temporal activity: send SMS via Twilio Verify API
3. Retry up to 3 times on failure with exponential backoff (2s, 4s, 8s)
4. If all retries fail, mark `otp_requests.delivered = false` and surface error to user

---

## Key Design Decisions

**OTP stored as a bcrypt hash.** A plaintext OTP in the database would be a credential leak if the DB is compromised. The code is short-lived (60s) but hashing it costs nothing meaningful and adds defence in depth.

**Phone as E.164 from the moment it enters the system.** All normalisation (removing spaces, adding country code) happens at the API boundary before any storage or lookup. This prevents duplicate accounts via formatting differences.

**Session revocation via `revoked_at`.** Revoked sessions are kept in the table for audit purposes. The auth middleware checks `revoked_at IS NULL` on every request — there is no token blacklist cache.

**Access token expiry is 15 minutes.** Short enough to limit exposure from a stolen token, long enough not to annoy the user. The 7-day refresh token allows seamless re-issuance without requiring a new OTP.
