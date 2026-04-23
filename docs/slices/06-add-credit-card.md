# Slice: Add Credit Card

## User Goal
Register a credit card so transactions and statements can be attributed to it and budgets can align with the billing cycle.

## Trigger
User taps "Add account" → selects "Credit card" from the accounts screen.

## Preconditions
- User is authenticated.

## Steps

### Step 1: Fill Card Details
**User action**: Enters:
- Nickname (e.g., "HDFC Millennia") — required
- Bank/issuer name (e.g., "HDFC Bank") — required
- Card network: visa | mastercard | amex | rupay — required
- Last 4 digits — optional, for display (e.g., "HDFC ···4521")
- Credit limit — optional, used for utilisation display
- Billing cycle day (1–28): day of month the statement generates — optional but recommended
- Primary currency — defaults to INR
**System response**: Validates that `billing_cycle_day` is in range 1–28 if provided.

### Step 2: Card Created
**User action**: Taps "Save".
**System response**: A `credit_cards` row is inserted (`is_active = true`). The full card number is never stored — only `last4`. The `AccountLinked` event is published via outbox.

### Step 3: Billing Cycle Impact on Budgets
**User action**: None — takes effect when budgets are created.
**System response**: When the user later creates a monthly budget, `billing_cycle_day` allows them to choose a salary-aligned or billing-cycle-aligned period (e.g., period runs 15th–14th). This is resolved at budget creation time, not here.

### Step 4: Onboarding Nudge
**User action**: None.
**System response**: The `notifications` domain creates:
- Title: "Account added"
- Body: "Upload a statement or log a transaction to start tracking {nickname}."

## Domains Involved
- **accounts**: Owns `credit_cards` table, publishes `AccountLinked`.
- **notifications**: Consumes `AccountLinked`, creates onboarding nudge.
- **budgets** (downstream): Uses `billing_cycle_day` when creating period-aligned budget goals.

## Edge Cases & Failures
- **billing_cycle_day not provided**: Budgets for this card default to calendar months (1st–last day). The user can edit the card later to add the billing cycle day.
- **billing_cycle_day = 29, 30, or 31**: Rejected — months with fewer days would produce undefined period starts. The field is capped at 28.
- **Credit limit not provided**: The utilisation display is suppressed in the UI. No other functionality is affected.
- **Amex card**: Stored normally. No special parser is registered for Amex statement formats at this stage.

## Success Outcome
The credit card appears in the user's account list. The user can upload a card statement or log transactions against it, and future budgets can align with the card's billing cycle.
