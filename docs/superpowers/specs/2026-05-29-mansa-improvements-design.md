# Mansa Musa — Reliability & Responsiveness Improvements Design Spec

**Date:** 2026-05-29
**Status:** Approved for implementation

---

## Context

Mansa is CassanovaL's personal finance agent. Users interact with it via the main chat interface (`/`) and view the resulting data on the Finance Dashboard (`/finance`). Three recurring problems have been reported:

1. **Wrong tool calls** — saying "make my balance 5 million" causes Mansa to call `add_income` (adding a phantom income transaction) instead of `update_account_balance`. The root cause is `mistral-small-latest`, which is less reliable at tool selection for complex natural-language commands.
2. **"Daily revenue" confusion** — `get_balance()` computes an all-time transaction net (total income minus total expenses). Mansa reports this figure as "current balance," which looks inflated because all historical income is included. Users see what appears to be revenue added when they spend.
3. **Dashboard staleness** — the Finance Dashboard polls every 30 seconds, so after a Mansa chat interaction, users may wait up to 30s to see updated data.
4. **No history awareness** — chat history (last 20 messages) is preserved in memory but the prompt doesn't instruct Mansa to reference it, so responses feel disconnected from prior sessions.

---

## Goal

After this improvement:
- Natural language balance commands ("set my bank to 5M", "change savings to 2.5 million") reliably call `update_account_balance`, not `add_income`.
- Mansa uses `list_accounts` for current balance reporting and reserves `get_balance` for historical summaries only.
- The Finance Dashboard refreshes within 5 seconds of a Mansa change.
- Mansa explicitly references conversation history in responses (prior balances, stated goals, past transactions).

---

## Changes

### 1. Model Upgrade — `agents/budget_agent.py`

**Change:** Replace `mistral-small-latest` with `mistral-large-latest`.

```python
# Before
return build_agent(SYSTEM_PROMPT, BUDGET_AGENT_TOOLS, model="mistral-small-latest", max_tokens=2048)

# After
return build_agent(SYSTEM_PROMPT, BUDGET_AGENT_TOOLS, model="mistral-large-latest", max_tokens=4096)
```

Also bump `max_tokens` from 2048 → 4096 since `mistral-large-latest` generates longer, richer responses.

---

### 2. Prompt Rules — `agents/budget_agent.py` SYSTEM_PROMPT

Add a dedicated **Tool Usage Rules** section to the existing prompt. Insert after the existing tool list, before any example interactions:

```
## Tool Usage Rules

### Balance updates
- When the user says "set/make/change/update my balance to X": ALWAYS call `update_account_balance(account_name, X)`.
- NEVER call `add_income` to change a balance. `add_income` is only for recording a new income transaction (salary, freelance payment, etc.).
- NEVER call `add_expense` to reduce a balance. `add_expense` is only for recording a new spending transaction.

### Balance reporting
- Before answering any question about current balance or account state, call `list_accounts` to read live data.
- Use `get_balance()` ONLY for all-time transaction summaries (e.g., "total income vs total expense ever recorded"). Do NOT use it to report the current balance of any account — it includes all historical transactions and will not match the account balance.

### History awareness
- The conversation history above contains prior interactions, balance changes, and stated goals. Always reference it.
- If the user mentioned their salary, savings target, or specific accounts in earlier messages, use those figures in your current response without asking again.
- When comparing current vs. prior state (e.g., "your savings went from 5M to 8M since last week"), calculate from history.
```

---

### 3. Dashboard Faster Polling — `static/finance/index.html`

**Change:** Reduce poll interval from 30 seconds to 5 seconds.

```javascript
// Before
setInterval(() => loadDashboard(true), 30_000);

// After
setInterval(() => loadDashboard(true), 5_000);
```

---

### 4. `data_changed` Signal — `server.py`

When the budget agent responds to a chat message, include a `data_changed: true` flag in the response so the main frontend can surface a "Finance updated" indicator.

**In `/api/chat` handler:** After the budget agent returns, check if the response text contains evidence of a tool call (or always set it for budget agent). Add to the JSON response body:

```json
{
  "response": "...",
  "agent": "budget",
  "data_changed": true
}
```

For non-budget agents, `data_changed` is `false` (or omitted).

**In `static/index/app.jsx` or `views.jsx`:** When a chat response arrives with `data_changed: true`, show a subtle inline notification near the agent header:

```
Finance data updated — open dashboard to see changes
```

This is informational only — no auto-navigation, no forced redirect.

---

## Architecture

```
User: "make my BCA balance 5 million"
    │
    ▼
router.py → Mansa (budget agent, mistral-large-latest)
    │
    ▼
Agent calls list_accounts() → sees current accounts
    │
    ▼
Agent calls update_account_balance("BCA", 5_000_000)
    │
    ▼
budget.json updated → account balance = 5,000,000
    │
    ▼
server.py returns {response: "...", data_changed: true}
    │
    ├──→ Chat UI shows "Finance data updated" notification
    │
    └──→ /finance dashboard polls every 5s → picks up change within 5s
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `mistral-large-latest` rate limit | `_invoke_with_retry` in `base.py` backs off; user sees delay, not crash |
| Account name not found in `update_account_balance` | Tool returns error message; Mansa asks user to clarify account name |
| `list_accounts` returns empty | Mansa informs user no accounts are set up yet |
| `data_changed` flag missing from response | Frontend treats it as `false`; no notification shown |

---

## Files to Modify

| File | Change |
|------|--------|
| `agents/budget_agent.py` | Model: `mistral-small-latest` → `mistral-large-latest`; `max_tokens`: 2048 → 4096; add Tool Usage Rules section to SYSTEM_PROMPT |
| `static/finance/index.html` | Poll interval: `30_000` → `5_000` |
| `server.py` | Add `data_changed: bool` to `/api/chat` response for budget agent |
| `static/index/` (app.jsx or views.jsx) | Show "Finance data updated" notification when `data_changed: true` |

No new files. No schema changes. No data migrations. Existing `data/budget.json` untouched.

---

## Verification

```powershell
# 1. Server starts without error
$env:PYTHONUTF8=1; python -c "import server; print('OK')"

# 2. Budget agent initializes with new model
$env:PYTHONUTF8=1; python -c "from agents.budget_agent import create_budget_agent; a = create_budget_agent(); print('OK')"

# 3. Regression — all existing tests pass
$env:PYTHONUTF8=1; pytest tests/ -v

# 4. End-to-end
# Start server: $env:PYTHONUTF8=1; python server.py
# Chat: "make my BCA balance 5 million rupiah"
# Verify: budget.json shows updated account balance (not a new income transaction)
# Open /finance — verify balance shows within 5 seconds
# Verify chat UI shows "Finance data updated" notification
```
