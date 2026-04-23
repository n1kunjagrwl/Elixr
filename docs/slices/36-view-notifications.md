# Slice: View Notification Inbox

## User Goal
Review all system notifications — budget alerts, statement processing results, SIP detections, earning classifications, account nudges — and act on the ones that require a response.

## Trigger
User taps the notification bell icon in the app header, or the badge count on the icon catches their attention.

## Preconditions
- User is authenticated.
- At least one `notifications` row exists for this user.

## Steps

### Step 1: Open Notification Inbox
**User action**: Taps the notification bell.
**System response**: `GET /notifications?unread=true` is called. Returns all notifications where `read_at IS NULL`, ordered by `created_at DESC`. Unread notifications are shown with a highlighted background or dot.

### Step 2: Browse Notifications
**User action**: Scrolls through the notification feed.
**System response**: Each notification shows:
- Title (e.g., "Budget limit exceeded", "Statement processed", "SIP payment detected")
- Body with contextual details (amounts, account names, category names)
- Relative timestamp ("2 hours ago", "Yesterday")
- Unread indicator if `read_at IS NULL`

Notification types that require user action show a "Tap to review" CTA:
- `SIPDetected` → confirm or dismiss the SIP link
- `EarningClassificationNeeded` → classify the credit as income/repayment/ignore
- `ExtractionPartiallyCompleted` → re-upload the statement
- `ExtractionCompleted` → review the processed transactions

Notification types that are informational only (no required action):
- `BudgetLimitWarning` / `BudgetLimitBreached` → deep-link to budget detail
- `AccountLinked` → deep-link to statement upload

### Step 3: Tap a Notification
**User action**: Taps a specific notification.
**System response**: The notification's `metadata.route` is used to navigate the user to the relevant screen:
- `/budgets?goal_id={id}` → budget detail
- `/statements/{job_id}/review` → statement review
- `/investments/sip/confirm?transaction_id={id}&sip_id={id}` → SIP confirmation
- `/earnings/classify?transaction_id={id}` → credit classification
- `/statements/upload?account_id={id}` → statement upload for the new account

The notification is marked read (`read_at = now()`) when the user taps it.

### Step 4: View Older Notifications
**User action**: Removes the `unread=true` filter to see all notifications.
**System response**: `GET /notifications` returns all notifications including read ones. Notifications older than 90 days are hidden from the feed (but not deleted from the DB — they are archived for audit purposes).

## Domains Involved
- **notifications**: Owns the `notifications` table; serves read/unread queries.
- All other domains that published events which created these notifications (budgets, investments, earnings, statements, accounts).

## Edge Cases & Failures
- **No unread notifications**: Inbox shows "All caught up" empty state.
- **Notification action route no longer valid** (e.g., the statement job was completed by a different device before the user tapped): The deep-link destination handles the stale state gracefully — e.g., the statement review screen shows "Statement already processed" if `extraction_jobs.status = 'completed'`.
- **Rapid sequence of budget breach notifications** (multiple transactions in the same category pushed it over 100%): Only one `BudgetLimitBreached` notification exists per goal per period. The `budgets` domain's `budget_alerts` deduplication ensures this.

## Success Outcome
User sees all relevant system notifications, can act on those that require input, and navigate directly to the affected screen via deep-link routing.
