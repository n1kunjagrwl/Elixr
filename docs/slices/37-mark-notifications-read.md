# Slice: Mark Notifications as Read

## User Goal
Clear the unread badge and mark notifications as seen, individually or all at once.

## Trigger
User taps a notification (auto-marks it read) or taps "Mark all as read" in the notification inbox.

## Preconditions
- User is authenticated.
- At least one `notifications` row exists with `read_at IS NULL`.

## Steps

### Step 1A: Mark Single Notification Read (on tap)
**User action**: Taps any notification in the feed.
**System response**: `PATCH /notifications/{id}/read` is called. `notifications.read_at = now()` is set for that row. The unread indicator is removed. The user is navigated to the notification's deep-link destination.

### Step 1B: Mark All Notifications Read
**User action**: Taps "Mark all as read" button in the inbox header.
**System response**: `PATCH /notifications/read-all` is called. Sets `read_at = now()` on all `notifications` rows for this user where `read_at IS NULL`. The badge count on the bell icon drops to zero.

### Step 2: Notification History Preserved
**User action**: Scrolls through the now-read notification list.
**System response**: All notifications remain visible in the feed (read or unread). Notifications are never deleted — only marked read. Notifications older than 90 days are hidden from the feed (archived view, not deleted from DB). The user can still find older notifications in an "All notifications" / archived view if needed.

## Domains Involved
- **notifications**: Owns the `read_at` update endpoint; no events published.

## Edge Cases & Failures
- **Concurrent mark-all on two devices**: Both `PATCH /notifications/read-all` calls set `read_at = now()` for the same rows. The second call is a no-op for rows already marked read. Both succeed without conflict.
- **Mark all read when a new notification arrives simultaneously**: The new notification arrives after the `read-all` query runs — it will have `read_at = NULL`. The badge reappears with count 1. This is expected behaviour.
- **Notification for a completed action** (e.g., SIP confirmed but notification still shows unread): Tapping it navigates to the SIP detail which shows "Already confirmed". The notification is marked read on tap. No functional issue.

## Success Outcome
The notification bell badge is cleared. All notifications are marked as seen. The notification history is preserved for future reference.
