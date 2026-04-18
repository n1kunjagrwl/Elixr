# ADR-0004: Google ADK for AI Categorisation

**Date**: 2026-04-18  
**Status**: Accepted

---

## Context

Categorising financial transactions from raw statement descriptions is a core feature of Elixir. The description `"UPI/20260315123456/POS/BIGBASKET ONLINE/918888"` must become "Groceries". The description `"NEFT CREDIT: ACME SOLUTIONS PVT LTD"` must become "Salary" or prompt the user to classify it.

A **rules engine alone** handles known merchants well but fails on:
- New merchants the user has not seen before
- Ambiguous descriptions (is `"AMAZON"` shopping, digital subscriptions, or Amazon Web Services?)
- Multi-word, multi-part descriptions with reference numbers mixed in
- Context-dependent classification (the same merchant might be Food or Entertainment depending on the category)

A **single LLM API call** (e.g., direct Gemini API) handles novel descriptions well but lacks:
- Tool use: the ability to look up the user's actual category list (rather than guessing at category names)
- Session state: when processing 200 transactions in one job, the agent should be consistent — if it classified 5 Swiggy transactions as "Food & Dining", it should not switch to "Food" for transaction 6
- Multi-turn reasoning: for genuinely ambiguous transactions, the agent should be able to ask a clarifying question and incorporate the answer

---

## Decision

Use **Google ADK** for the categorisation agent. ADK supports tool-use (function calling), multi-turn stateful sessions, and integrates natively with Gemini models.

The agent is instantiated once per statement processing job and given three tools:

1. `get_user_categories(user_id)` — fetches the user's full category list (defaults + custom)
2. `get_similar_transactions(description, user_id)` — fetches the last 5 similar transactions and how they were categorised (for consistency)
3. `request_user_clarification(description, options)` — signals to the Temporal workflow that this row needs user input

The agent outputs a structured response per transaction:
```json
{
  "category_id": "uuid",
  "confidence": 0.92,
  "item_suggestions": ["Food delivery", "Delivery fee"],
  "needs_user_input": false
}
```

If `needs_user_input: true`, the Temporal workflow pauses until the user classifies the transaction and sends a signal.

---

## Consequences

### Positive

- **Tool use enables precise category matching.** The agent calls `get_user_categories()` and references actual UUID category IDs from the user's taxonomy — not guessed category names. This eliminates the mapping step between "the AI said 'groceries'" and "which category row does that correspond to?"
- **Stateful multi-turn session.** ADK manages session state across all transactions in one job. The agent sees what it has classified so far and can be consistent.
- **Structured output.** ADK's tool-use model produces structured JSON responses rather than freeform text that must be parsed. Confidence scores and `needs_user_input` flags are first-class fields.
- **Native Gemini integration.** Google ADK is the first-party SDK for Gemini — no translation layer. Model upgrades (Gemini → Gemini 2) require a version bump, not an API change.

### Negative / Trade-offs

- **API cost.** Each transaction classification consumes Gemini API tokens. For a 200-row statement, this is ~200 agent calls. Cost is mitigated by: (1) running the rules engine first (eliminating known merchants at zero cost), (2) batching transactions in a single prompt where context allows.
- **Latency.** Each ADK call adds 200–800ms per transaction. For a 200-transaction statement, this adds 40–160 seconds of processing time. Mitigated by: streaming results to the frontend as they are classified (the user sees progress), and by batching multiple transactions per ADK call where appropriate.
- **Google ADK is a newer framework.** APIs may change between minor versions. Pin the dependency version and maintain a test suite against mock ADK responses.
- **Vendor dependency.** Switching from Gemini to another model provider requires updating the ADK client configuration and potentially the tool schema format.

---

## Alternatives Considered

**Direct Gemini API calls**: No framework, just `google-generativeai` library. Simpler initially, but requires custom implementation of: session state across transactions, tool routing, structured output parsing, retry logic. ADK provides all of this. Ruled out for the added maintenance burden.

**OpenAI function calling**: Equivalent capability to ADK but on a different vendor. Would require switching from Gemini to GPT-4 models. No technical advantage — ruled out to stay on the Google ecosystem (already using Google ADK in `pyproject.toml`).

**Local LLM (Ollama, Llama)**: No API cost, full privacy (transaction data never leaves the server). Classification quality is lower than Gemini at the sizes that can run locally, and deployment adds significant infrastructure complexity (GPU requirements, model management). Ruled out for quality and deployment cost at this stage. Worth revisiting if Gemini costs become significant at scale.

**Pure rules engine**: Fast, deterministic, zero cost. Cannot handle novel merchants or ambiguous descriptions. Ruled out as the sole classifier — retained as the first-pass filter before ADK is consulted.
