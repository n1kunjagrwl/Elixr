# peers — E2E Test Guide

> Last generated: 2026-05-17

## Business Intent

From the user's perspective, the peers domain is a simple personal ledger for informal money flows — splitting dinner bills, covering a friend's share of a trip, or tracking a small loan. A user adds named peer contacts, logs individual balances (recording who owes whom, for what, and how much), and then records settlements as repayments happen, whether in full or over several instalments. The domain keeps a running `remaining_amount` automatically and moves each balance through `open → partial → settled` status as money changes hands. When a contact is no longer relevant, the user can delete them — but only after all outstanding balances are fully settled. No events are published, no notifications are sent, and nothing is automated: every balance and settlement is entered explicitly by the user.

---

## Domain Scope

| Item | Detail |
|------|--------|
| Tables owned | `peer_contacts`, `peer_balances`, `peer_settlements` |
| Events published | None |
| Events consumed | None |
| Temporal workflows | None |
| SQL views exposed | `peer_contacts_public` (columns: `id`, `user_id`, `name`) — consumed by the `earnings` domain |
| Slices covered | 33, 34, 35, 40 |

---

## Test Scenarios

---

### Scenario 1: Add a Peer Contact (minimal fields)

**Source slice**: `docs/slices/33-add-peer-contact.md`
**Business intent**: A user can save a named peer contact so that peer balances can be associated with a real person.
**Domains involved**: peers

#### Preconditions
- Authenticated user exists with no existing peer contacts.

#### Steps
1. `POST /api/v1/peers/contacts` with body `{ "name": "Rahul" }` (phone and notes omitted).
2. Receive `201 Created` response.

#### Assertions
- **DB**: A `peer_contacts` row exists with `name = 'Rahul'`, `phone = NULL`, `notes = NULL`, `user_id` matching the authenticated user, and non-null `created_at` / `updated_at`.
- **API response**: Response body contains `id` (UUID), `name = "Rahul"`, `phone = null`, `notes = null`.
- **Events**: No outbox rows created; no events published.
- **Side effects**: The new contact appears in `peer_contacts_public` view for this `user_id` — query `SELECT id, name FROM peer_contacts_public WHERE user_id = ?` and assert `"Rahul"` is returned.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Same name entered twice | Two separate rows inserted with distinct UUIDs — no uniqueness error | [ ] |
| Phone number supplied as free text (e.g., `"+91 98765 43210"`) | Stored exactly as entered; no normalisation or format rejection | [ ] |
| Name field omitted entirely | `422 Unprocessable Entity` — name is required | [ ] |

---

### Scenario 2: Add a Peer Contact (all fields)

**Source slice**: `docs/slices/33-add-peer-contact.md`
**Business intent**: A user can enrich a contact with a phone number and contextual notes.
**Domains involved**: peers

#### Preconditions
- Authenticated user exists.

#### Steps
1. `POST /api/v1/peers/contacts` with body `{ "name": "Mom", "phone": "9876543210", "notes": "College roommate" }`.
2. Receive `201 Created` response.

#### Assertions
- **DB**: Row has `phone = '9876543210'` and `notes = 'College roommate'` stored as plain text exactly as entered.
- **API response**: All three fields (`name`, `phone`, `notes`) reflected in the response body.
- **Events**: None.
- **Side effects**: Contact name `"Mom"` visible in `peer_contacts_public` for this user.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Phone number in logs | Phone must not appear in any application log line — no-PII log policy | [ ] |

---

### Scenario 3: Log a Peer Balance — "Owed to me" direction

**Source slice**: `docs/slices/34-log-peer-balance.md`
**Business intent**: The user records that a peer owes them money for a specific shared expense.
**Domains involved**: peers

#### Preconditions
- Authenticated user exists.
- A `peer_contacts` row exists for this user (e.g., `peer_id = <uuid>`, name `"Rahul"`).

#### Steps
1. `POST /api/v1/peers/balances` with body:
   ```json
   {
     "peer_id": "<rahul-uuid>",
     "description": "Goa trip accommodation",
     "direction": "owed_to_me",
     "original_amount": 1500.00,
     "currency": "INR"
   }
   ```
2. Receive `201 Created` response.

#### Assertions
- **DB**: `peer_balances` row has:
  - `direction = 'owed_to_me'`
  - `original_amount = 1500.00`
  - `settled_amount = 0.00`
  - `remaining_amount = 1500.00` (PostgreSQL generated column)
  - `status = 'open'`
  - `currency = 'INR'`
  - `linked_transaction_id = NULL`
  - `user_id` matching the authenticated user
- **API response**: Contains `id`, `status = "open"`, `remaining_amount = 1500.00`, `direction = "owed_to_me"`.
- **Events**: No events published; no outbox rows.
- **Side effects**: None.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `peer_id` does not belong to the authenticated user | `404 Not Found` or `403 Forbidden` — no cross-user access | [ ] |
| `original_amount` is zero or negative | `422 Unprocessable Entity` | [ ] |
| `description` omitted | `422 Unprocessable Entity` | [ ] |
| `currency` omitted | Defaults to `'INR'` | [ ] |

---

### Scenario 4: Log a Peer Balance — "I owe" direction

**Source slice**: `docs/slices/34-log-peer-balance.md`
**Business intent**: The user records a debt they owe to a peer, not the other way around.
**Domains involved**: peers

#### Preconditions
- Authenticated user and a `peer_contacts` row both exist.

#### Steps
1. `POST /api/v1/peers/balances` with body:
   ```json
   {
     "peer_id": "<sister-uuid>",
     "description": "Shared hotel booking — my share",
     "direction": "i_owe",
     "original_amount": 3000.00,
     "currency": "INR"
   }
   ```
2. Receive `201 Created` response.

#### Assertions
- **DB**: `peer_balances` row has `direction = 'i_owe'` (not `owed_to_me`), `original_amount = 3000.00`, `status = 'open'`, `remaining_amount = 3000.00`.
- **API response**: `direction = "i_owe"` is returned correctly — verify the field is not defaulted or normalised away.
- **Events**: None.
- **Side effects**: None.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `direction` field is any value other than `owed_to_me` or `i_owe` | `422 Unprocessable Entity` | [ ] |
| Multiple open balances with the same peer | Each creates a separate row; no uniqueness conflict | [ ] |

---

### Scenario 5: Log a Peer Balance with Optional Linked Transaction

**Source slice**: `docs/slices/34-log-peer-balance.md`
**Business intent**: A user can optionally link a balance to a known bank transaction for reconciliation.
**Domains involved**: peers, transactions (informational reference only)

#### Preconditions
- Authenticated user, a peer contact, and a `transactions` row all exist.

#### Steps
1. `POST /api/v1/peers/balances` with body including `"linked_transaction_id": "<tx-uuid>"`.
2. Receive `201 Created` response.

#### Assertions
- **DB**: `peer_balances.linked_transaction_id = '<tx-uuid>'` stored as-is. No FK constraint is enforced at the DB level.
- **API response**: `linked_transaction_id` echoed back in response.
- **Events**: None — no cross-domain event triggered by this link.
- **Side effects**: No changes to the referenced `transactions` row.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `linked_transaction_id` references a non-existent transaction UUID | Stored without error — no FK constraint; informational only | [ ] |
| `linked_transaction_id` references a transaction belonging to a different user | TODO: clarify whether the service validates user ownership of the linked transaction | [ ] |

---

### Scenario 6: Record a Full Settlement on an Open Balance

**Source slice**: `docs/slices/35-record-peer-settlement.md`
**Business intent**: The user records that a peer repaid the full outstanding amount in one payment.
**Domains involved**: peers

#### Preconditions
- Authenticated user has a `peer_balances` row with `status = 'open'`, `original_amount = 1500.00`, `settled_amount = 0.00`, `remaining_amount = 1500.00`.

#### Steps
1. `POST /api/v1/peers/balances/<balance-id>/settlements` with body:
   ```json
   {
     "amount": 1500.00,
     "currency": "INR",
     "method": "upi",
     "settled_at": "2026-05-17T10:00:00Z"
   }
   ```
2. Receive `201 Created` response.

#### Assertions
- **DB — `peer_settlements`**: A new row exists with `amount = 1500.00`, `currency = 'INR'`, `method = 'upi'`, `balance_id` matching the balance.
- **DB — `peer_balances`**: `settled_amount = 1500.00`, `remaining_amount = 0.00` (generated column recalculated by PostgreSQL), `status = 'settled'`.
- **API response**: Settlement response contains `id`, `amount = 1500.00`.
- **Events**: None.
- **Side effects**: Balance no longer appears in the active open-balance list for this peer. The `peer_settlements` row is NOT deleted or modified — it is the permanent record.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Settlement amount > `remaining_amount` | `422 Unprocessable Entity` — settlement cannot exceed what is owed | [ ] |
| Settlement amount = 0 | `422 Unprocessable Entity` | [ ] |
| `settled_at` is backdated (past date) | Accepted — stored as provided | [ ] |
| Attempt to `PUT`/`PATCH` an existing `peer_settlements` row | `405 Method Not Allowed` or `404` — settlements are append-only, no edit endpoint exists | [ ] |

---

### Scenario 7: Record a Partial Settlement — Status Transitions

**Source slice**: `docs/slices/35-record-peer-settlement.md`
**Business intent**: A user records a partial repayment; the balance moves to `partial` and the remaining amount decreases correctly.
**Domains involved**: peers

#### Preconditions
- `peer_balances` row with `status = 'open'`, `original_amount = 2000.00`, `remaining_amount = 2000.00`.

#### Steps
1. `POST /api/v1/peers/balances/<balance-id>/settlements` with `amount = 1000.00`.
2. Receive `201 Created`.
3. `POST /api/v1/peers/balances/<balance-id>/settlements` with `amount = 1000.00`.
4. Receive `201 Created`.

#### Assertions
- After step 2:
  - **DB — `peer_balances`**: `settled_amount = 1000.00`, `remaining_amount = 1000.00`, `status = 'partial'`.
  - **DB — `peer_settlements`**: One row with `amount = 1000.00`.
- After step 4:
  - **DB — `peer_balances`**: `settled_amount = 2000.00`, `remaining_amount = 0.00`, `status = 'settled'`.
  - **DB — `peer_settlements`**: Two rows exist; neither is modified after creation.
- **API response**: Each `POST` returns the newly created settlement row only — prior settlement rows are not altered.
- **Events**: None.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Attempt to settle an already-`settled` balance | `422 Unprocessable Entity` — `remaining_amount = 0`, settlement not possible | [ ] |
| `status = 'partial'` after first settlement, then second settlement fully clears it | Status transitions from `partial` → `settled` (not back to `open`) | [ ] |

---

### Scenario 8: Settlement Correction via New Append Entry

**Source slice**: `docs/slices/35-record-peer-settlement.md`
**Business intent**: If the user recorded the wrong settlement amount, they add a correcting entry — there is no edit button on past settlements.
**Domains involved**: peers

#### Preconditions
- `peer_balances` row with `original_amount = 1000.00`. One `peer_settlements` row already exists with `amount = 800.00` (incorrect — should have been `500.00`). Balance state: `settled_amount = 800.00`, `remaining_amount = 200.00`, `status = 'partial'`.

#### Steps
1. The user does NOT edit the existing `peer_settlements` row.
2. `POST /api/v1/peers/balances/<balance-id>/settlements` with `amount = -300.00` and `notes = "Correction: original entry was too high by 300"`.
3. Receive `201 Created`.

#### Assertions
- **DB — `peer_settlements`**: Two rows now exist for this balance. The original `amount = 800.00` row is completely unchanged. A second row with `amount = -300.00` has been appended.
- **DB — `peer_balances`**: `settled_amount = 500.00` (800 - 300), `remaining_amount = 500.00`, `status = 'partial'`.
- **API response**: New settlement row returned with `amount = -300.00`.
- **Events**: None.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `PUT /api/v1/peers/balances/<balance-id>/settlements/<settlement-id>` attempted | `405 Method Not Allowed` — no edit endpoint | [ ] |
| `DELETE /api/v1/peers/balances/<balance-id>/settlements/<settlement-id>` attempted | `405 Method Not Allowed` — deletions not supported | [ ] |

---

### Scenario 9: Multi-Currency Settlement Does Not Reduce `remaining_amount` (Known Failing Edge Case)

**Source slice**: `docs/slices/35-record-peer-settlement.md`
**Business intent**: Demonstrates a known system limitation — settling a USD-denominated balance with an INR settlement amount silently leaves `remaining_amount` unreduced.
**Domains involved**: peers

#### Preconditions
- `peer_balances` row with `original_amount = 100.00`, `currency = 'USD'`, `settled_amount = 0.00`, `remaining_amount = 100.00`.

#### Steps
1. `POST /api/v1/peers/balances/<balance-id>/settlements` with `amount = 8300.00`, `currency = 'INR'` (INR equivalent of 100 USD at current rate).
2. Receive `201 Created`.

#### Assertions
- **DB — `peer_settlements`**: Row created with `amount = 8300.00`, `currency = 'INR'`.
- **DB — `peer_balances`**: `settled_amount` is incremented by `8300.00` even though the balance is denominated in USD. `remaining_amount` will show a large negative number (`100.00 - 8300.00 = -8200.00`) — this is incorrect and misleading. Alternatively, if `settled_amount` is only incremented when currencies match, `remaining_amount` stays at `100.00` (unsettled) — also incorrect from the user's perspective.
- **API response**: Settlement created successfully with no warning about currency mismatch.
- **Events**: None.

> **This is a known limitation (see INCONSISTENCIES.md §3.10).** The test should assert the actual (broken) behaviour and be marked as a failing/known-issue test until the limitation is resolved. The user has no in-app warning that their balance appears unaffected.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Balance in USD, settlement in USD | `remaining_amount` correctly reduced — same-currency path works | [ ] |
| Balance in INR, settlement in USD | Same silent failure — `remaining_amount` not meaningfully reduced | [ ] |

---

### Scenario 10: Edit a Peer Contact

**Source slice**: `docs/slices/40-edit-delete-peer-contact.md`
**Business intent**: The user can update the name, phone, or notes for an existing peer contact without affecting any balance or settlement records.
**Domains involved**: peers

#### Preconditions
- Authenticated user has a `peer_contacts` row: `name = "Rahul"`, `phone = "9876543210"`, `notes = "College roommate"`.

#### Steps
1. `PATCH /api/v1/peers/contacts/<contact-id>` with body `{ "name": "Rahul K", "notes": "Flatmate until 2024" }`.
2. Receive `200 OK`.

#### Assertions
- **DB**: `peer_contacts` row has `name = 'Rahul K'`, `notes = 'Flatmate until 2024'`, `phone = '9876543210'` (unchanged), and an updated `updated_at` timestamp.
- **API response**: Updated contact fields returned.
- **Events**: No events published — peer contact edits have no downstream domain reactions.
- **Side effects**: `peer_contacts_public` view now returns `name = 'Rahul K'` for this `id`. The updated name is reflected immediately on all balance and settlement screens. Past bank statement descriptions are NOT retroactively reclassified by the `earnings` domain.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Name updated to empty string | `422 Unprocessable Entity` — name is required | [ ] |
| Attempt to edit a contact belonging to a different user | `404 Not Found` or `403 Forbidden` | [ ] |
| Phone field set to `null` in the update | Phone stored as `NULL` — field can be cleared | [ ] |

---

### Scenario 11: Delete a Peer Contact — Blocked by Open Balances

**Source slice**: `docs/slices/40-edit-delete-peer-contact.md`
**Business intent**: A contact with any open or partial balances cannot be deleted; the user must settle all balances first.
**Domains involved**: peers

#### Preconditions
- `peer_contacts` row for "Rahul" with one `peer_balances` row at `status = 'open'` (or `'partial'`).

#### Steps
1. `DELETE /api/v1/peers/contacts/<contact-id>`.
2. Receive `409 Conflict` (or equivalent blocking response).

#### Assertions
- **DB**: `peer_contacts` row is NOT deleted. `peer_balances` row is NOT deleted.
- **API response**: Error response body includes a message indicating unsettled balances exist (e.g., references the count or total remaining amount). No partial deletion has occurred.
- **Events**: None.
- **Side effects**: None. The guard is enforced even if only one balance among many is open.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Contact has a mix of `settled` and `open` balances | Deletion still blocked — even one open balance is sufficient to reject | [ ] |
| Last open balance is settled between opening the confirmation dialog and confirming delete | Re-check at confirm time passes; deletion succeeds on re-attempt | [ ] |

---

### Scenario 12: Delete a Peer Contact — Allowed (All Balances Settled)

**Source slice**: `docs/slices/40-edit-delete-peer-contact.md`
**Business intent**: A contact whose balances are all settled can be hard-deleted along with their full history.
**Domains involved**: peers

#### Preconditions
- `peer_contacts` row with two `peer_balances` rows, both at `status = 'settled'`. Each settled balance has one or more `peer_settlements` rows.

#### Steps
1. `DELETE /api/v1/peers/contacts/<contact-id>`.
2. User confirms deletion in the UI (confirmation dialog).
3. Receive `204 No Content`.

#### Assertions
- **DB**: `peer_contacts` row is hard-deleted. All associated `peer_balances` rows are deleted in cascade. All associated `peer_settlements` rows (via `peer_balances`) are deleted in cascade.
- **API response**: `204 No Content`.
- **Events**: No events published — no other domain reacts to contact deletion.
- **Side effects**: `peer_contacts_public` view no longer returns any row for this contact's `id`. Future bank credits mentioning this person's name will not be flagged as potential peer repayments by the `earnings` domain.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Contact has no balances at all | Deletion is allowed immediately without a blocking check | [ ] |
| Contact has only settled balances but many `peer_settlements` rows | All cascade-deleted in a single operation — no orphaned settlement rows | [ ] |
| Attempting to fetch the deleted contact via `GET /api/v1/peers/contacts/<id>` after deletion | `404 Not Found` | [ ] |

---

### Scenario 13: Delete a Peer Contact — Cascade Removes Settled History

**Source slice**: `docs/slices/40-edit-delete-peer-contact.md`
**Business intent**: Hard deletion is intentional — once a contact is gone, their entire balance and settlement history is discarded. This is by design.
**Domains involved**: peers

#### Preconditions
- `peer_contacts` row with a fully settled `peer_balances` row that has three `peer_settlements` rows.

#### Steps
1. `DELETE /api/v1/peers/contacts/<contact-id>` (confirmed by user).
2. Receive `204 No Content`.

#### Assertions
- **DB**: All three `peer_settlements` rows are gone. The `peer_balances` row is gone. The `peer_contacts` row is gone. No orphaned rows remain in any of the three tables.
- **Events**: None.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Rolling back the deletion (e.g., user regrets it) | Not supported — hard delete is irreversible; this is documented behaviour | [ ] |

---

## Known Inconsistencies

- **[3.9]** Settlement corrections use a new entry, not an edit. `business-intent/peers.md` states the ledger is append-only but does not describe what the user does when they make a mistake. `slices/35-record-peer-settlement.md` documents a "Add correction" flow where a new `peer_settlements` row is inserted with a correcting (possibly negative) amount. Users expecting an "Edit" button on past settlements will not find one. Scenario 8 above covers this pattern explicitly.

- **[3.10]** Multi-currency settlement silently fails to reduce `remaining_amount`. `business-intent/peers.md` states only that multi-currency balances are not supported. `slices/35-record-peer-settlement.md` reveals the more severe consequence: if a user records a settlement in a different currency than the balance (e.g., settling a USD balance with an INR amount), the `remaining_amount` — stored in the balance's original currency — is not automatically reduced to reflect the real-world repayment. The user's balance appears unchanged or shows a nonsensical value, with no in-app warning. Scenario 9 above marks this as a known failing edge case.

---

## Coverage Gaps

| Gap | Source | TODO |
|-----|--------|------|
| Linking a settlement to a bank transaction (`linked_transaction_id` on `peer_settlements`) | `slices/35-record-peer-settlement.md` — Step 2, last bullet | Add a scenario asserting the field is stored correctly and that no automatic status change occurs on the `peer_balances` row |
| Verifying that `peer_contacts_public` view is filtered correctly per `user_id` (no cross-user data leakage) | `docs/domains/peers.md` — SQL Views Exposed | Add a scenario with two users each having a contact; assert each user's view returns only their own contacts |
| Settlement amount validation against `remaining_amount` when balance is `partial` (not just `open`) | `slices/35-record-peer-settlement.md` — Edge cases | Add a sub-case to Scenario 7 where a third settlement exceeds the remaining partial amount |
| Concurrent delete guard: settlement completes in another session while delete confirmation is open | `slices/40-edit-delete-peer-contact.md` — Edge cases | Requires a concurrency test or integration test; not feasible as a simple E2E step |
| `GET /api/v1/peers/contacts/<id>` returns balance list grouped by status (`open`, `partial`, `settled`) | `slices/40-edit-delete-peer-contact.md` — Step 1 | TODO: confirm the exact API response schema for the contact detail endpoint |
| Phone PII exclusion from logs under the no-PII policy | `docs/domains/peers.md` and `slices/40-edit-delete-peer-contact.md` — Edge cases | Requires log-capture tooling in the test environment; noted in Scenario 2 edge cases |
| Earnings domain heuristic impact after contact deletion | `slices/40-edit-delete-peer-contact.md` — Path B outcome and `slices/33-add-peer-contact.md` — Step 2 | Functional coverage deferred until an earnings E2E test guide is written |
| `PATCH /api/v1/peers/balances/{balance_id}` — no test scenario covers editing a balance record | `docs/domains/peers.md` — API routes | Add a scenario asserting that `description` and `notes` can be updated, and that `amount` and `original_amount` are immutable (any attempt to change them is rejected with HTTP 422 or silently ignored) |
| Settle all open balances for a contact at once — API endpoint exists at `POST /api/v1/peers/contacts/{contact_id}/settle` but no scenario covers this shortcut path | `docs/domains/peers.md` — API routes | Add a scenario that calls the shortcut endpoint and verifies all `open`/`partial` balances for the contact transition to `settled` atomically |

---

## TODO

- ✅ Resolved — Settlement route is `POST /api/v1/peers/balances/{balance_id}/settlements` (nested under the balance). The settlement history read is `GET /api/v1/peers/balances/{balance_id}/settlements`. There is no top-level `/peers/settlements` endpoint. All scenario route references have been updated.
- Confirm whether negative settlement amounts (used for corrections) are accepted by the schema validation layer or require a separate `notes`-only correction endpoint. Scenario 8 assumes negative amounts are permitted.
- Confirm the HTTP status code returned when deletion is blocked by open balances — `409 Conflict` is assumed above; verify against the actual API implementation.
- Clarify whether `linked_transaction_id` on a balance creation is validated for user ownership of the referenced transaction (currently marked TODO in Scenario 5 edge cases).
- Confirm whether balances are fetched via `GET /api/v1/peers/balances?status=open|partial|settled` (confirmed route) or whether a contact-scoped filter (e.g. `?peer_id=<id>`) is also supported; scenarios above omit read-path assertions for brevity.
- Add read-path scenarios (list contacts, list balances per peer, view settlement history for a balance) once API contracts are finalised.
- Document the `open → settled` direct transition (first settlement clears the full amount) as an explicit sub-case in Scenario 6 or a new scenario — currently only noted in the assertions.
