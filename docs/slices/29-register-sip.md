# Slice: Register SIP

## User Goal
Tell the app about a recurring SIP (Systematic Investment Plan) debit so the system can automatically recognise future SIP transactions and link them to the correct investment holding.

## Trigger
User taps "Register SIP" from the Investments screen or from within a specific holding's detail page.

## Preconditions
- User is authenticated.
- A bank account is linked (row exists in `bank_accounts` for this user) — a SIP registration must be tied to a specific debit account.
- The target instrument (mutual fund, stock, or ETF) already exists as a `holdings` row for this user, or the user creates it during this flow (via slice 27).

## Steps

### Step 1: Select the Instrument
**User action**: User searches for and selects the mutual fund, stock, or ETF for which they want to register the SIP. The picker shows only instruments of type `mf`, `stock`, or `etf` that the user already holds (or is adding now).

**System response**: Backend returns matching `holdings` rows with their associated `instruments.name` and `instruments.ticker`. If the user has no holding yet, a shortcut "Add this instrument first" link is shown, routing to slice 27.

### Step 2: Enter SIP Amount
**User action**: User enters the SIP instalment amount (e.g. ₹5,000). This is the amount that will be debited each cycle.

**System response**: UI validates that the amount is > 0. A note is displayed: "We'll match debits within ±2% of this amount."

### Step 3: Select Frequency and Debit Day
**User action**: User selects the SIP frequency:
- **Monthly** — debit happens once per month.
- **Weekly** — debit happens once per week.
- **Quarterly** — debit happens once per quarter.

Then the user enters the **debit day**:
- For monthly/quarterly: a day-of-month number (1–28; 29–31 are intentionally excluded to avoid month-end ambiguity).
- For weekly: a day-of-week (Monday–Sunday).

**System response**: UI shows a plain-English confirmation: e.g. "We'll look for a ₹5,000 debit on the 7th of each month ±3 days."

### Step 4: Select Bank Account
**User action**: User picks the bank account from which the SIP is debited. The picker lists all active bank accounts linked to the user.

**System response**: The selected `bank_accounts.id` will be stored as `sip_registrations.bank_account_id`. Only debits from this specific account will be matched against this SIP registration.

### Step 5: Submit
**User action**: User reviews the summary and taps "Register SIP".

**System response**:
1. Backend inserts a row into `sip_registrations`:
   - `user_id`, `instrument_id` (from the holding's instrument), `amount`, `frequency`, `debit_day`, `bank_account_id`.
   - `is_active = true`.
2. A success toast is shown: "SIP registered. We'll notify you when we spot a matching debit."
3. The holding's detail page now shows a "SIP Active" badge.

### Step 6: Future Detection (background)
**User action**: None — this is automatic.

**System response**: Whenever a new debit transaction is created for this user (via statement upload, CSV import, or manual entry), the Transactions domain publishes a `TransactionCreated` event. The Investments domain's SIP detection logic evaluates all `is_active = true` SIP registrations for this user:
- Amount within ±2% of `sip_registrations.amount`.
- Transaction date within ±3 days of `debit_day` for the relevant period.
- `bank_account_id` matches the transaction's account.
If matched, a `SIPDetected` event is published, which the Notifications domain converts into a push/in-app notification (see slice 30).

## Domains Involved
- **Investments**: Core domain. Writes `sip_registrations`, performs SIP detection on `TransactionCreated` events, publishes `SIPDetected`.
- **Transactions**: Source of `TransactionCreated` events that trigger SIP detection.
- **Notifications**: Consumes `SIPDetected` to create an in-app notification prompting user confirmation.
- **Accounts**: Provides the list of bank accounts for the picker. If an account is removed, `AccountRemoved` event deactivates matching `sip_registrations` rows.

## Edge Cases & Failures
- **No bank accounts linked**: The form is blocked with a prompt to link a bank account first. The "Register SIP" button is disabled.
- **Debit day out of range**: Days 29–31 are not allowed for monthly/quarterly frequency (shown as greyed out in the UI) to prevent missed detections in short months.
- **Duplicate SIP registration**: If a `sip_registrations` row already exists for the same `user_id` + `instrument_id` + `bank_account_id` + `frequency` + `debit_day` and `is_active = true`, the backend returns a 409 Conflict: "An active SIP for this instrument and account already exists."
- **Amount too small**: Amounts below ₹100 are rejected as implausible SIP amounts (422 validation error).
- **Bank account removed after registration**: The `AccountRemoved` event sets `is_active = false` on all `sip_registrations` for that account. The SIP registration is silently deactivated — no in-app notification is sent. The user will notice the change when they view the investment's detail page, where the "SIP Active" badge will be gone. A future `SIPRegistrationDeactivated` event could notify the user.
- **Multiple matches at detection time**: If a single transaction matches two or more active SIP registrations, a `SIPDetected` notification is published for each. The user will see multiple notifications and must confirm the correct one (see slice 30).

## Success Outcome
An active SIP registration exists in the database. Going forward, matching debits imported from bank statements or entered manually will trigger a "SIP payment detected" notification, allowing the user to confirm and link the transaction to the investment holding with one tap.
