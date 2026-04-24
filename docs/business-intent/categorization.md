# Business Intent: categorization

## Why This Domain Exists

Raw transaction descriptions from bank statements — "UPI/123456/ZOMATOORD", "NEFT/HDFC/SALARY" — are machine-readable strings that mean nothing to a user at a glance. The categorization domain turns those strings into meaningful labels: "Food & Dining", "Salary", "Self Transfer". It provides the taxonomy every other part of the app depends on (budgets, earnings, spending summaries), and it lets users teach the system to recognise merchants they encounter every day.

---

## What It Provides

- A **default category set** — 15 expense, 6 income, and 1 transfer category that work out of the box for any Indian user, with no setup required.
- **Custom categories** — users can create categories the default set doesn't cover (e.g., "Pet Care", "Side Project").
- **Categorisation rules** — users can define patterns ("any transaction containing 'Swiggy' → Food & Dining") that fire automatically before the AI is consulted, making future imports faster and requiring less user confirmation.
- **AI-powered classification** — for transactions that don't match any user rule, the Google ADK agent suggests a category with a confidence score. High-confidence suggestions are applied automatically; low-confidence ones are sent to the user for review.
- **Category management** — users can browse, enable, disable, and organise their category list.

---

## How a User Interacts With It

| Action | What the user does | What happens |
|---|---|---|
| Browse categories | Opens the category list | Sees all default and custom categories grouped by kind (expense / income) |
| Create custom category | Names a new category and picks a kind | Category is added to their list and becomes available for transactions and budgets |
| Disable a category | Hides a custom category they created and no longer use | Category disappears from dropdowns and suggestions |
| Create a rule | Types "Swiggy" + selects "contains" + picks "Food & Dining" | Future Swiggy transactions are classified instantly without AI or manual review |
| Manage rules | Views, reorders, disables, or deletes existing rules | Rule changes take effect on the next import; existing transactions are not retroactively changed |
| Auto-classify (background) | Uploads a statement | Rules run first; AI runs for unmatched rows; result surfaces to user for review |

---

## User Stories

- As a new user, I want a set of sensible default categories so I can start tracking expenses without any setup.
- As a user, I want to create a "Pet Care" category because the default set doesn't include it.
- As a user, I want to create a rule that always tags Swiggy transactions as "Food & Dining" so I never have to confirm that classification again.
- As a user, I want to hide categories I never use so my category picker stays clean.
- As a user, I want the AI to handle unfamiliar merchants automatically, and only ask me when it's genuinely unsure.

---

## What It Does Not Do

- System default categories cannot be hidden or deactivated by end users. Only custom categories the user created can be hidden.
- Does not apply rules retroactively to past transactions. Changing or creating a rule only affects future imports.
- Does not merge or rename categories once transactions are linked to them (would require migrating all associated transaction items).
- Does not infer categories from amounts alone. Description is the primary signal; amount is supporting context.
- Does not share categories across users. Default categories are shared implicitly (one DB row), but custom categories are strictly per-user.

---

## Key Constraint

Rules run before AI — deterministic and free. The AI is only consulted when no rule matches. This means a well-trained rule set makes classification nearly instant and requires minimal user confirmation over time.
