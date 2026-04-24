# Implementation Plan: identity

## Status
**Complete** — all files are implemented and the domain is wired into the runtime.

## Domain References
- Domain spec: [`docs/domains/identity.md`](../domains/identity.md)
- Data model: [`docs/data-model.md`](../data-model.md#identity)
- Workflow: [`docs/workflows/otp-delivery.md`](../workflows/otp-delivery.md)
- User slices: 01-user-registration, 02-user-login, 03-session-refresh, 04-user-logout

## Dependencies
None — `identity` has no domain dependencies. It is the foundation every other domain builds on.

## What Was Built
- Phone-number registration and OTP-based authentication via Twilio
- JWT access token (15 min) + refresh token (7 day, HttpOnly cookie) session lifecycle
- `OTPDeliveryWorkflow` Temporal workflow with 3 exponential-backoff retries
- Outbox events: `identity.UserRegistered`, `identity.UserLoggedIn`
- SQL view: `users_public` (id, name only — phone never exposed cross-domain)

## Implemented Files
| File | Status |
|---|---|
| `domains/identity/models.py` | Done — `User`, `OTPRequest`, `Session`, `IdentityOutbox` |
| `domains/identity/repositories.py` | Done |
| `domains/identity/services.py` | Done |
| `domains/identity/schemas.py` | Done |
| `domains/identity/events.py` | Done |
| `domains/identity/api.py` | Done |
| `domains/identity/bootstrap.py` | Done |
| `domains/identity/workflows/otp_delivery.py` | Done |
| `domains/identity/workflows/activities.py` | Done |

## API Endpoints (implemented)
| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/request-otp` | Send OTP to phone number |
| `POST` | `/auth/verify-otp` | Verify OTP, issue tokens |
| `POST` | `/auth/refresh` | Rotate access token via refresh token |
| `POST` | `/auth/logout` | Revoke session |

## Key Constraints (do not change without an ADR)
- OTP is stored as a bcrypt hash — never plaintext
- Phone normalised to E.164 at the API boundary before any storage or lookup
- Session revocation uses `revoked_at` (no blacklist cache) — middleware checks `revoked_at IS NULL` on every request
- `Users.is_active` column exists in the model (soft-delete safety valve) — not in the original data-model spec; confirm before exposing via API
