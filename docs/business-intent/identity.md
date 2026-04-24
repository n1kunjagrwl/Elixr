# Business Intent: identity

## Why This Domain Exists

Every feature in Elixir is personal — a user's transactions, budgets, and investments must never mix with another user's. The identity domain creates and protects the boundary around each user's data. Without it, none of the financial tracking the app provides is meaningful or safe.

---

## What It Provides

- A way for new users to **create an account** using only their phone number — no email, no password.
- A way for returning users to **sign in** by verifying a one-time code sent to their phone.
- A **session** that keeps the user signed in for up to 7 days without asking them to re-verify, while still expiring access quickly if a token is ever stolen.
- A way to **sign out** and invalidate the session immediately.

---

## How a User Interacts With It

| Action | What the user does | What happens |
|---|---|---|
| Register | Enters their phone number for the first time | Receives an OTP via SMS; enters it to create their account |
| Log in | Returns to the app and enters their phone number | Receives an OTP; enters it to get a new session |
| Stay signed in | Uses the app within 7 days | Access token is refreshed silently; no OTP needed |
| Log out | Taps "Sign out" | Session is revoked immediately on all devices |
| Use app on multiple devices | Opens the app on a second phone or browser | A new independent session is created. Both sessions are valid simultaneously. Logging out on one device does not affect the other. |

---

## User Stories

- As a new user, I want to create an account using my phone number so I don't need to remember a password.
- As a returning user, I want to sign in quickly so I can check my finances without friction.
- As a user, I want my session to stay active while I'm using the app regularly so I don't get logged out unexpectedly.
- As a user, I want to be able to sign out so that someone else using my phone cannot access my financial data.

---

## What It Does Not Do

- Does not store passwords. OTP is the only authentication mechanism.
- Does not manage profile details beyond name and phone number. Avatar, email, preferences — all out of scope.
- Does not handle account deletion. If the user wants their data removed, that is a separate operation outside this domain's current scope.
- Does not support multiple phone numbers per user or number changes.
- Does not support 'log out all devices' as a single operation. Each session can only be revoked from the device it belongs to.

---

## Key Constraint

Every other domain trusts the authenticated `user_id` injected by the auth middleware. They never handle login logic themselves. The identity domain is the only place where "who is this person?" is answered.

- The sign-in flow returns an identical response for both registered and unregistered phone numbers. A user who enters an unregistered number sees 'OTP sent' but receives no SMS. This prevents attackers from discovering which numbers have accounts (user enumeration prevention).
