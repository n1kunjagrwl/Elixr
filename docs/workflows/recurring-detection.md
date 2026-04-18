# Workflow: RecurringTransactionDetectionWorkflow

**Domain**: `transactions`  
**Trigger**: Temporal schedule — weekly, Sunday 02:00 IST  
**Output**: Updates `transactions.source` for detected recurring rows; publishes notifications  

---

## Purpose

Automatically identifies transactions that recur on a predictable schedule — subscriptions, EMIs, rent, SIPs not yet linked to a SIP registration. Labels them as `recurring_detected` so the user can confirm and use them for spending awareness. This is an analytical, background operation. It never modifies categories or creates new transactions.

---

## Step-by-step

```
1. For each user with at least one transaction in the last 90 days:

2. Fetch the last 90 days of debit transactions for this user:
   SELECT id, date, amount, raw_description, source
   FROM transactions
   WHERE user_id = ? AND type = 'debit' AND date >= now() - interval '90 days'
   ORDER BY date

3. Normalise merchant names:
   - Uppercase, strip leading/trailing whitespace
   - Remove reference numbers: patterns like [A-Z0-9]{12,} (UPI ref IDs, NEFT refs)
   - Remove date-like tokens: DD/MM, Jan, Feb, etc.
   - Remove trailing amounts: "500.00" at end of description
   Example: "UPI/2024031512345678/NETFLIX" → "UPI NETFLIX"

4. Group transactions by normalised_description:
   Cluster transactions where the normalised description matches AND
   the amount is within ±5% of the cluster's median amount.

5. For each cluster with >= 2 transactions:
   Compute the intervals between consecutive dates in the cluster (in days).

   Check if intervals are consistent with a known frequency:
     Daily:     all intervals within [0.8, 1.2] of 1 day
     Weekly:    all intervals within [5, 9] days
     Fortnightly: all intervals within [12, 16] days
     Monthly:   all intervals within [28, 33] days
     Quarterly: all intervals within [88, 95] days

   A cluster is "recurring" if:
     - At least 2 occurrences in the 90-day window
     - Intervals are consistent with one of the above frequencies
     - The transactions are not already sourced as 'recurring_detected'
       or already linked as SIPs

6. For each identified recurring cluster:
   a. Update transactions.source = 'recurring_detected'
      for all transactions in this cluster

   b. Publish a single notification (not one per transaction):
      "We noticed you pay ~₹{median_amount} to {merchant} every {frequency}.
       This looks like a recurring charge. Review and confirm."
      metadata: { route: "/transactions?filter=recurring&merchant={normalised_desc}" }

7. Log summary: {user_id, clusters_found, transactions_labelled}
```

---

## What This Is NOT

This workflow **does not**:
- Create new transactions
- Change categories
- Automatically set up budget rules based on recurrences
- Cancel or flag subscriptions the user may want to cancel

It only labels existing transactions and informs the user. All action taken on the recurring transactions is user-initiated.

---

## Error Handling

If the workflow fails for a specific user (e.g., DB timeout during their transaction fetch), that user's analysis is skipped and logged. The workflow continues to process remaining users. Because this runs weekly, a single failed run has minimal impact — the next Sunday run will process all users again.

Temporal retry policy:
- Per-user activity: 2 attempts, no backoff (the query is fast and idempotent)
- Workflow level: no automatic retry — if the whole workflow fails, it runs again next Sunday

---

## Idempotency

The workflow is safe to run multiple times. The update `source = 'recurring_detected'` is idempotent. Notifications are deduplicated by checking whether a recurring notification for the same merchant was sent in the last 7 days — no duplicate prompts if the workflow runs twice.

---

## Future Extensions

- Let users **confirm** a recurring transaction → saves a rule in `categorization_rules` so future occurrences are auto-categorised
- Let users **dismiss** a merchant → add to a suppression list so it's not flagged again
- Use detected recurrences as input for future **cash flow projection** feature
