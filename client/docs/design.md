# Frontend Design Specification

## Design Principles

- **Minimal, not sparse** — every element earns its place; no decorative chrome
- **Scannable** — users should answer "where did my money go this month?" in under 5 seconds
- **Mobile-first** — designed for a 390px viewport, enhanced for tablet and desktop
- **Customizable** — dashboard layout, theme, and categories are all user-controlled
- **Non-alarming** — financial stress is real; avoid red/danger framing for normal overspending; use neutral language

---

## Navigation

### Bottom Tab Bar (always visible)

```
[ Home ] [ Transactions ] [ Investments ] [ Peers ] [ More ]
```

- Active tab uses accent color; inactive tabs use muted text
- Home tab shows a badge count when there are items needing attention (unreviewed transactions, budget alerts)
- "More" tab opens a full-screen menu listing: Budgets, Earnings, Accounts, Categories, Settings

### Header

- Each page has a minimal header: page title (left) + optional action icon (right, e.g., filter, search)
- No persistent app-level header — the bottom nav is the primary orientation anchor

---

## Floating Action Button (FAB)

A single FAB lives in the bottom-right corner, above the tab bar, on all main pages.

On tap it expands into three labelled actions:
1. **Upload Statement** — triggers the file picker → statement upload flow
2. **Add Transaction** — opens a bottom sheet for manual transaction entry
3. **Add Investment** — opens a bottom sheet to log a holding, FD, or SIP

The FAB is hidden inside detail pages and settings to avoid clutter.

---

## Home Screen (Dashboard)

The home screen is a vertically scrollable list of widget cards. The default order and visibility can be changed in Settings → Dashboard.

### Default Widget Order

| # | Widget | What it shows |
|---|---|---|
| 1 | Attention Strip | Unreviewed transactions count, active budget alerts, unread notifications — dismissable per item |
| 2 | Net Position | This month: total income vs. total expenses, net delta, prior month comparison |
| 3 | Spending Breakdown | Category donut chart + top 3 spending categories with amounts |
| 4 | Budget Status | Progress bars for all active budgets; over-budget budgets shown first |
| 5 | Recent Transactions | Last 5 transactions, tappable to open detail |
| 6 | Investment Snapshot | Total portfolio value (current), day/week change |
| 7 | Peer Balances | Compact list: who owes you, whom you owe |

### Widget Customization

- Users can reorder widgets via drag-and-drop in Settings → Dashboard
- Any widget can be hidden
- Widget preferences are persisted in Zustand and synced to localStorage

### Date Range

- Default time window: current calendar month
- A date range picker at the top of the home screen changes the window for all widgets simultaneously
- Preset options: This Month, Last Month, Last 3 Months, This Year, Custom

---

## AI Classification Review (Attention Flow)

When the backend has one or more transactions with low-confidence classifications:

1. A modal/bottom sheet appears automatically on home screen load
2. Header: "X transactions need your review"
3. Each row shows: description, date, amount, AI-suggested category + confidence indicator
4. User can: Accept the suggestion, pick a different category, or skip
5. A "Don't ask again for this merchant" checkbox creates a categorization rule
6. Dismissing the modal without acting leaves the badge count on the Home tab

The modal does not auto-appear more than once per session to avoid repeated interruption.

---

## Transactions Page

- Searchable, filterable list of transactions
- Filters: date range, account, category, type (debit/credit), amount range
- Each row: merchant name, category icon, date, amount (debit = muted, credit = accent)
- Tapping a row opens a detail sheet: full description, account, category, edit option
- Unreviewed transactions are visually marked (e.g., a small dot or "Needs review" label)
- Bulk actions: select multiple → assign category, delete

---

## Investments Page

- Tab strip at the top: Overview | Holdings | SIPs | FDs
- **Overview**: total portfolio value, allocation donut (equity/debt/crypto/gold/cash), absolute and percentage return
- **Holdings**: list by instrument with current value, units, avg buy price, P&L
- **SIPs**: active SIPs with next instalment date and amount
- **FDs**: active FDs with maturity date, interest rate, maturity amount

---

## Peers Page

- List of peer contacts with net balance (green = they owe you, amber = you owe them)
- Tapping a contact shows full balance history and settlements
- "Log Balance" and "Record Settlement" actions per contact

---

## More Menu

Full-screen sheet listing secondary sections:

- Budgets
- Earnings
- Accounts
- Categories & Rules
- Settings

Each section opens its own page with a back button.

---

## Settings

Sections:
- **Profile** — name, phone (read-only)
- **Dashboard** — widget reorder + visibility
- **Appearance** — Light / Dark / System toggle; accent color picker (5 presets)
- **Accounts** — add, edit, deactivate bank accounts and credit cards
- **Categories** — browse, create, edit custom categories and categorization rules
- **Notifications** — in-app notification preferences
- **Data** — import history, delete import batch

---

## Visual Design Direction

- **Color mode**: Light and dark, defaulting to system preference
- **Accent color**: Single configurable accent (default: a calm blue-teal); used for active states, CTAs, positive values
- **Negative amounts**: muted red — never alarming, just distinct
- **Positive/credit amounts**: accent color or muted green
- **Typography**: System font stack (`-apple-system`, `Segoe UI`, `Roboto`) — no custom font to load
- **Radius**: consistent medium radius (8–12px) on cards; full-radius on pills/badges
- **Elevation**: minimal — 1px border + subtle background tint instead of drop shadows
- **Spacing**: 4px base unit grid (Tailwind default); generous vertical padding on tap targets (min 44px)

---

## Responsive Behaviour

| Breakpoint | Layout |
|---|---|
| < 640px (mobile) | Single column, bottom tab nav, full-width cards |
| 640–1024px (tablet) | Two-column widget grid on home; bottom nav or sidebar |
| > 1024px (desktop) | Persistent left sidebar nav; three-column widget grid |

The PWA is designed mobile-first. Tablet and desktop layouts are progressively enhanced, not redesigned.
