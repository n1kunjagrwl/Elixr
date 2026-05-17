---
description: Generate comprehensive E2E testing documentation for all Elixir domains using slice specs, domain docs, and business intent. Invoke with /gen-test-docs or /gen-test-docs <domain-name> to regenerate a single domain.
argument-hint: Optional domain name (identity|accounts|statements|import_|transactions|categorization|earnings|budgets|investments|peers|notifications|fx) to process only that domain
allowed-tools: ["Read", "Write", "Edit", "Bash", "Agent", "TaskCreate", "TaskUpdate", "TaskList"]
---

# gen-test-docs — E2E Testing Documentation Generator

You are generating E2E testing documentation for the Elixir personal finance PWA. The docs live in `docs/testing/` (one file per domain). Each file describes what to test, how to test it, and what gaps or known issues exist.

## Context You Must Read First

Before launching any agents, read these files to ground yourself:
- `docs/business-intent/index.md` — domain overview and application flow
- `docs/business-intent/INCONSISTENCIES.md` — known cross-doc conflicts that test docs must flag
- `docs/architecture.md` — tech stack and patterns
- CLAUDE.md — project rules and constraints

## Domain → Slice Mapping

Use this to know which slice files each domain agent needs to read.

| Domain | Slice files | Domain doc |
|--------|-------------|------------|
| identity | 01, 02, 03, 04 | `docs/domains/identity.md` |
| accounts | 05, 06, 07, 08 | `docs/domains/accounts.md` |
| statements | 09, 10, 11, 12 | `docs/domains/statements.md` |
| import_ | 13, 14, 43 | `docs/domains/import_.md` |
| transactions | 15, 16, 44 | `docs/domains/transactions.md` |
| categorization | 10, 17, 18, 19, 20, 21 | `docs/domains/categorization.md` |
| earnings | 22, 23, 38, 39, 45 | `docs/domains/earnings.md` |
| budgets | 24, 25, 26, 42 | `docs/domains/budgets.md` |
| investments | 27, 28, 29, 30, 31, 32, 41 | `docs/domains/investments.md` |
| peers | 33, 34, 35, 40 | `docs/domains/peers.md` |
| notifications | 36, 37 | `docs/domains/notifications.md` |
| fx | (no dedicated slices — indirect participant) | `docs/domains/fx.md` |

## Execution Plan

**If `$ARGUMENTS` is a specific domain name**: process only that domain (single agent, foreground).

**If `$ARGUMENTS` is empty**: process all 12 domains. Launch agents in four parallel batches:

- **Batch A** (launch together): identity, accounts, statements
- **Batch B** (launch together): import_, transactions, categorization
- **Batch C** (launch together): earnings, budgets, investments
- **Batch D** (launch together): peers, notifications, fx

Wait for each batch to complete before launching the next.

After all domain agents finish, launch a **Review Agent** that audits all 12 output files for cross-domain consistency, completeness, and linkage correctness.

## Instructions for Each Domain Agent

Each domain agent receives a self-contained prompt (see template below). The agent must:

1. **Read all slice files** for its domain (see mapping above).
2. **Read the domain doc** for its domain.
3. **Read `docs/business-intent/{domain}.md`** for user perspective.
4. **Extract the business intent**: What does a user accomplish through this domain? What are the core invariants?
5. **Map each slice to test scenarios**: One slice = one or more scenarios (happy path + edge cases).
6. **Check for coverage gaps**: Are any user actions from the domain doc or business intent not covered by a slice? List them as TODOs.
7. **Check for inconsistencies**: Cross-reference the slice steps against the domain doc's table definitions, events, and service contracts. Flag any contradictions.
8. **Check relevant entries in `docs/business-intent/INCONSISTENCIES.md`**: list which numbered issues affect this domain.
9. **Write the test guide** to `docs/testing/{domain}-test-guide.md` using the Output Format below.

## Output Format

Each domain agent must write a file matching this exact structure:

```markdown
# {Domain} — E2E Test Guide

> Last generated: {YYYY-MM-DD}

## Business Intent

{One paragraph: what the user accomplishes through this domain and why it matters.}

## Domain Scope

| Item | Detail |
|------|--------|
| Tables owned | comma-separated list |
| Events published | comma-separated list |
| Events consumed | comma-separated list |
| Temporal workflows | comma-separated list (or "none") |
| Slices covered | comma-separated slice numbers |

## Test Scenarios

Each scenario maps to one or more slice steps.

---

### Scenario {N}: {Descriptive Title}

**Source slice**: `docs/slices/{XX}-{name}.md`  
**Business intent**: One sentence explaining why this path matters to the user.  
**Domains involved**: comma-separated domain names  

#### Preconditions
- ...

#### Steps
1. {API call or user action} → {expected DB state / response / event}
2. ...

#### Assertions
- **DB**: {what rows / columns to verify}
- **API response**: {status code, key fields}
- **Events**: {events published to outbox}
- **Side effects**: {downstream domain reactions if relevant}

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| {description} | {expected behavior} | [ ] |

---

(repeat for each scenario)

## Known Inconsistencies

List entries from `docs/business-intent/INCONSISTENCIES.md` that directly affect this domain. For each:

- **[N.N] {title}**: {one-sentence impact on testing}. Status: `flag-in-test` | `skip-pending-resolution` | `resolved-in-slice`.

## Coverage Gaps

List user actions or domain behaviours that are NOT covered by any slice. These are candidates for future slices or acceptance tests.

| Gap | Source | TODO |
|-----|--------|------|
| {description} | {domain doc / business intent reference} | [ ] write slice {proposed-name} |

## TODO

Unresolved items that blocked test scenario completion. Each item must name the blocker and a suggested next step.

- [ ] {description} — **Blocker**: {what's missing} — **Next step**: {action}
```

## Domain Agent Prompt Template

When launching each domain agent, use this prompt (fill in `{DOMAIN}` and `{SLICES}`):

---

```
You are writing E2E testing documentation for the "{DOMAIN}" domain of the Elixir personal finance app.

## Your Task

Read the following files (read all of them before writing anything):

1. docs/slices/{SLICES} — read each slice file listed
2. docs/domains/{DOMAIN}.md — domain reference
3. docs/business-intent/{DOMAIN}.md — user perspective (read if it exists; skip if missing)
4. docs/business-intent/INCONSISTENCIES.md — flag any entries that involve {DOMAIN}
5. docs/business-intent/index.md — overall application flow

Then write a file to: docs/testing/{DOMAIN}-test-guide.md

## Output Requirements

Follow the output format exactly as specified (see the skill file at .claude/commands/gen-test-docs.md for the template). Key requirements:

1. **Business Intent section** — summarise what the user accomplishes through this domain. Pull from business-intent/{DOMAIN}.md if it exists; otherwise derive from the domain doc.

2. **Domain Scope table** — fill in tables owned, events published/consumed, workflows, slices covered. Read these from the domain doc — do not invent.

3. **Test Scenarios** — one scenario per distinct user journey. For each:
   - Name the source slice.
   - List concrete preconditions (what DB rows must exist, what auth state is needed).
   - List API steps with expected responses (status codes, key response fields).
   - List DB assertions (which table, which row, which column value to verify).
   - List events published to the outbox (event_type value).
   - List edge cases from the slice's "Edge Cases & Failures" section — each as a row in the table.

4. **Known Inconsistencies** — scan docs/business-intent/INCONSISTENCIES.md for any item that mentions {DOMAIN}. List each one with its impact on testing.

5. **Coverage Gaps** — compare slice scenarios against the domain doc's Service Methods, Events, and Table columns. Identify any user-facing behaviour documented in the domain doc but not covered by a slice. List each as a table row with a TODO.

6. **TODO section** — if any step above could not be completed (e.g., a slice references a table column that doesn't exist in the domain doc, or an event is mentioned in a slice but not in the domain's events list), write a TODO item naming the exact blocker and a suggested next step.

## Quality Check Before Writing

Before writing the file, ask yourself:
- Does every scenario have at least one DB assertion?
- Does every Temporal workflow trigger have a scenario that covers the workflow happy path?
- Do all events published by this domain appear in at least one scenario's "Events" assertion?
- Are all edge cases from the slices represented in the edge case tables?

If any answer is "no", add the missing item or a TODO.

Do NOT invent information not present in the source files. If something is unclear, write a TODO.
```

---

## Review Agent Instructions

After all domain agents finish, launch one more agent with this prompt:

```
You are auditing the E2E test guide files in docs/testing/ for cross-domain correctness.

Read every file in docs/testing/ (all 12 domain test guides).

Then check:

1. **Cross-domain event linkage**: For every event in a "producer" domain's test guide, verify that the consuming domain's test guide has a corresponding scenario that handles that event. Flag any events that are published but never tested as consumed.

2. **Scenario precondition chains**: Some scenarios require rows from other domains (e.g., a statements scenario requires an active account). Verify that the preconditions in each scenario name the correct owning domain and the setup step is feasible.

3. **Inconsistency coverage**: Read docs/business-intent/INCONSISTENCIES.md. Verify that every numbered inconsistency is mentioned in at least one domain test guide's "Known Inconsistencies" section. List any that are not mentioned anywhere.

4. **TODO accumulation**: Collect all TODO items from all 12 test guides into a single file at docs/testing/TESTING-TODO.md. Group by domain. Add a priority column (High/Medium/Low) based on whether the gap would cause a silent regression in production.

Write the audit results to docs/testing/REVIEW.md using this format:

---
# E2E Test Guide — Cross-Domain Audit

## Event Linkage Gaps
| Producer domain | Event | Consumer domain | Status |
|----------------|-------|-----------------|--------|
| ... | ... | ... | Covered / Missing |

## Precondition Chain Issues
List any scenario where a precondition can't be satisfied by the named owning domain.

## Inconsistency Coverage
| Inconsistency | Covered in test guide? | Domain guide(s) |
|--------------|----------------------|-----------------|
| 1.1 | yes / no | {domain} |
...

## Summary
- Total test scenarios: N
- Total edge cases: N
- Total TODOs: N
- Inconsistencies covered: N / 26
---

Also write docs/testing/TESTING-TODO.md aggregating all TODOs.
```

## Completion Check

After the review agent finishes, verify:
- [ ] `docs/testing/` contains 12 domain files + REVIEW.md + TESTING-TODO.md
- [ ] No domain has an empty "Test Scenarios" section
- [ ] REVIEW.md lists no uncovered inconsistencies from INCONSISTENCIES.md
- [ ] TESTING-TODO.md exists and has all collected TODOs

Report the final count: total scenarios, total edge cases, total TODOs, inconsistencies covered.
