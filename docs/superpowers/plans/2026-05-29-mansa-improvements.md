# Mansa Musa — Reliability & Responsiveness Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Mansa's wrong-tool-call bugs (phantom income transactions, balance not updating), add explicit prompt rules for correct tool selection, reduce dashboard poll from 30s to 5s, and surface a "Finance updated" notification in the chat UI.

**Architecture:** Three targeted changes — (1) upgrade budget agent model from `mistral-small-latest` to `mistral-large-latest` and add Tool Usage Rules to its system prompt; (2) reduce poll interval in `/finance` dashboard; (3) add `data_changed` flag to `/api/chat` response and render a dismissable banner in ChatView when Mansa responds.

**Tech Stack:** Python (FastAPI, LangChain, Mistral AI), vanilla JSX (React-via-CDN), static HTML/JS

---

## File Map

| File | Change |
|------|--------|
| `agents/budget_agent.py` | Model → `mistral-large-latest`, `max_tokens` → 4096, add Tool Usage Rules to SYSTEM_PROMPT |
| `static/finance/index.html` | Poll interval `30_000` → `5_000` (line 958) |
| `server.py` | `/api/chat` returns `data_changed: bool` (True when budget agent handled request) |
| `static/index/app.jsx` | Read `r.data_changed`, track `budgetUpdated` state, pass as prop to ChatView |
| `static/index/views.jsx` | ChatView accepts `financeUpdated` prop, shows dismissable banner for budget agent |
| `static/index/styles.css` | Add `.finance-notif` banner style |

---

## Task 1 — Model Upgrade + Prompt Rules (`agents/budget_agent.py`)

**Files:**
- Modify: `agents/budget_agent.py`

This is the highest-impact change. `mistral-small-latest` mis-calls `add_income` when the user says "set my balance to X", creating phantom income transactions. Upgrading to `mistral-large-latest` + adding explicit tool-use rules fixes the root cause.

- [ ] **Step 1: Add Tool Usage Rules section to SYSTEM_PROMPT**

In `agents/budget_agent.py`, the SYSTEM_PROMPT currently ends with:

```python
Tone: tegas, supportif, langsung ke angka — seperti CFO pribadi yang tidak pernah menghakimi."""
```

Replace that last line with:

```python
Tone: tegas, supportif, langsung ke angka — seperti CFO pribadi yang tidak pernah menghakimi.

## TOOL USAGE RULES

### Balance updates
- When the user says "set/make/change/update my balance to X": ALWAYS call `update_account_balance(account_name, X)`.
- NEVER call `add_income` to change a balance. `add_income` is ONLY for recording a new income event (salary received, freelance paid, etc.).
- NEVER call `add_expense` to reduce a balance. `add_expense` is ONLY for recording a new spending event.
- Example: "make my BCA balance 5 million" → `update_account_balance("BCA", 5000000)` — NOT `add_income`.

### Balance reporting
- Before answering any question about current account balance, call `list_accounts` first to read live data.
- Use `get_balance()` ONLY for all-time transaction summaries ("total income vs total expense ever recorded"). Do NOT use it to report an account's current balance — it sums all historical transactions and will appear inflated.
- Example: "what's my BCA balance?" → call `list_accounts`, then report the account's `balance` field.

### History awareness
- The conversation history contains prior transactions, balance changes, and stated goals. Always reference it.
- If the user mentioned salary, savings targets, or specific account names in earlier messages, use those figures without asking again.
- When comparing current vs. prior state (e.g., "savings went from 5M to 8M"), calculate from the conversation history."""
```

- [ ] **Step 2: Upgrade model and max_tokens**

Change the last line of `agents/budget_agent.py` (line 172):

```python
# Before:
return build_agent(SYSTEM_PROMPT, BUDGET_AGENT_TOOLS, model="mistral-small-latest", max_tokens=2048)

# After:
return build_agent(SYSTEM_PROMPT, BUDGET_AGENT_TOOLS, model="mistral-large-latest", max_tokens=4096)
```

- [ ] **Step 3: Smoke test — agent loads without error**

```powershell
$env:PYTHONUTF8=1; python -c "from agents.budget_agent import create_budget_agent, SYSTEM_PROMPT; print('SYSTEM_PROMPT length:', len(SYSTEM_PROMPT)); print('Rules present:', 'TOOL USAGE RULES' in SYSTEM_PROMPT); print('OK')"
```

Expected output:
```
SYSTEM_PROMPT length: <N>   # any number > 3000
Rules present: True
OK
```

- [ ] **Step 4: Confirm model name in agent**

```powershell
$env:PYTHONUTF8=1; python -c "
from agents.budget_agent import create_budget_agent
import inspect, agents.budget_agent as m
src = inspect.getsource(m)
assert 'mistral-large-latest' in src, 'Model not updated!'
assert 'mistral-small-latest' not in src, 'Old model still present!'
assert 'max_tokens=4096' in src, 'max_tokens not updated!'
print('Model checks passed')
"
```

Expected: `Model checks passed`

- [ ] **Step 5: Regression — all tests pass**

```powershell
$env:PYTHONUTF8=1; pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all tests green (no failures).

- [ ] **Step 6: Commit**

```powershell
git add agents/budget_agent.py
git commit -m "feat(mansa): upgrade to mistral-large-latest, add tool usage rules to prompt"
```

---

## Task 2 — Dashboard Faster Polling (`static/finance/index.html`)

**Files:**
- Modify: `static/finance/index.html` (line 958)

- [ ] **Step 1: Change poll interval from 30s to 5s**

Find line 958 in `static/finance/index.html`:

```javascript
// Before:
setInterval(() => loadDashboard(true), 30_000);

// After:
setInterval(() => loadDashboard(true), 5_000);
```

- [ ] **Step 2: Verify change**

```powershell
Select-String -Path "static/finance/index.html" -Pattern "setInterval.*loadDashboard"
```

Expected output should show `5_000` (not `30_000`).

- [ ] **Step 3: Commit**

```powershell
git add static/finance/index.html
git commit -m "feat(finance): reduce dashboard poll interval from 30s to 5s"
```

---

## Task 3 — `data_changed` Flag in `/api/chat` (`server.py`)

**Files:**
- Modify: `server.py` (lines 312–327)

The `/api/chat` endpoint currently returns `{"agent": ..., "response": ...}`. Add `data_changed: bool` that is `True` whenever the budget agent handles the request.

- [ ] **Step 1: Modify the chat endpoint**

Current code (lines 312–327):

```python
@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        supervisor = get_supervisor()
        if req.agent:
            agent_name, response = supervisor.chat_direct(req.agent, req.message)
        else:
            agent_name, response = supervisor.chat(req.message)

        agent_key = req.agent or agent_name.lower()
        _save_chat_history(agent_key, agent_name, req.message, response)
        _log_chat_wrap(agent_key, req.message)

        return {"agent": agent_name, "response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

Replace with:

```python
@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        supervisor = get_supervisor()
        if req.agent:
            agent_name, response = supervisor.chat_direct(req.agent, req.message)
        else:
            agent_name, response = supervisor.chat(req.message)

        agent_key = req.agent or agent_name.lower()
        _save_chat_history(agent_key, agent_name, req.message, response)
        _log_chat_wrap(agent_key, req.message)

        return {
            "agent": agent_name,
            "response": response,
            "data_changed": agent_key == "budget",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 2: Smoke test — server imports without error**

```powershell
$env:PYTHONUTF8=1; python -c "import server; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Verify `data_changed` field in response**

```powershell
$env:PYTHONUTF8=1; python -c "
import ast, inspect, server
# Just check the source contains the new key
src = inspect.getsource(server.chat)
assert 'data_changed' in src, 'data_changed not added!'
assert 'agent_key == \"budget\"' in src, 'budget check missing!'
print('data_changed field confirmed in chat endpoint')
"
```

Expected: `data_changed field confirmed in chat endpoint`

- [ ] **Step 4: Commit**

```powershell
git add server.py
git commit -m "feat(api): add data_changed flag to /api/chat response for budget agent"
```

---

## Task 4 — Finance Updated Banner (`static/index/app.jsx`, `static/index/views.jsx`, `static/index/styles.css`)

**Files:**
- Modify: `static/index/app.jsx` (around line 169)
- Modify: `static/index/views.jsx` (ChatView function, around line 165)
- Modify: `static/index/styles.css` (add `.finance-notif` style)

When Mansa responds, a small dismissable banner appears at the top of the chat area: "Finance data updated — [open dashboard →]". Auto-dismisses after 8 seconds.

- [ ] **Step 1: Add `budgetUpdated` state and prop in `app.jsx`**

In `app.jsx`, around line 159–183 (the `send` function), make two changes:

**Change A** — Add state near the top of the `App` function (after the existing `const [loading, setLoad]` line, around line ~85):

```javascript
const [budgetUpdated, setBudgetUpdated] = React.useState(false);
```

**Change B** — In the `send` callback (around line 169), after `setMsgs(...)`:

```javascript
// Before:
const r = await chatAPI(text, agKey);
setMsgs(p => ({ ...p, [agKey]: [...p[agKey], { role: 'assistant', content: r.response, ts: new Date().toISOString() }] }));
// Notify other open tabs (finance, fitness dashboards) that data changed
if (_syncBC) _syncBC.postMessage({ agent: agKey, ts: Date.now() });

// After:
const r = await chatAPI(text, agKey);
setMsgs(p => ({ ...p, [agKey]: [...p[agKey], { role: 'assistant', content: r.response, ts: new Date().toISOString() }] }));
if (r.data_changed) setBudgetUpdated(true);
// Notify other open tabs (finance, fitness dashboards) that data changed
if (_syncBC) _syncBC.postMessage({ agent: agKey, ts: Date.now() });
```

**Change C** — Pass `budgetUpdated` and `setBudgetUpdated` to ChatView (around line 210):

```javascript
// Before:
? <ChatView agKey={agKey} messages={msgs[agKey]} loading={loading} onSend={send}/>

// After:
? <ChatView agKey={agKey} messages={msgs[agKey]} loading={loading} onSend={send}
            financeUpdated={budgetUpdated} onFinanceDismiss={() => setBudgetUpdated(false)}/>
```

- [ ] **Step 2: Add `.finance-notif` CSS to `styles.css`**

Add to `static/index/styles.css` (append to the end of the file before any `/* end */` comment, or just at the very end):

```css
/* Finance updated banner */
.finance-notif {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  background: var(--accent-subtle, rgba(90,140,90,0.12));
  border-bottom: 1px solid var(--border2, #e0ddd6);
  font-size: 12px;
  color: var(--ink-2, #5a5040);
  animation: slideDown 0.2s ease;
}
.finance-notif a {
  color: var(--accent, #5B8C5A);
  text-decoration: none;
  font-weight: 600;
}
.finance-notif a:hover { text-decoration: underline; }
.finance-notif-close {
  margin-left: auto;
  cursor: pointer;
  font-size: 14px;
  color: var(--ink-4, #9b9078);
  background: none;
  border: none;
  padding: 0 4px;
  line-height: 1;
}
.finance-notif-close:hover { color: var(--ink-2, #5a5040); }
@keyframes slideDown {
  from { opacity: 0; transform: translateY(-6px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

- [ ] **Step 3: Update ChatView to accept and render the banner**

In `static/index/views.jsx`, change the `ChatView` function signature and add the banner (around line 165):

```javascript
// Before:
function ChatView({ agKey, messages, loading, onSend }) {
  const { AGENTS, CHIPS, renderMd, fmtTime, fmtIssue, MOCK } = window.CLData;
  const { IcoSend, IcoClip, IcoPlus, IcoReceipt, IcoMic, IcoMicOff } = window.Icons;
  const ag = AGENTS[agKey];
  const [val, setVal] = _useState('');
  const [listening, setListening] = _useState(false);
  const [voiceSupported] = _useState(() => !!(window.SpeechRecognition || window.webkitSpeechRecognition));
  const endRef = _useRef(null);
  const taRef = _useRef(null);
  const recRef = _useRef(null);
  const srRef = _useRef(null);

// After:
function ChatView({ agKey, messages, loading, onSend, financeUpdated, onFinanceDismiss }) {
  const { AGENTS, CHIPS, renderMd, fmtTime, fmtIssue, MOCK } = window.CLData;
  const { IcoSend, IcoClip, IcoPlus, IcoReceipt, IcoMic, IcoMicOff } = window.Icons;
  const ag = AGENTS[agKey];
  const [val, setVal] = _useState('');
  const [listening, setListening] = _useState(false);
  const [voiceSupported] = _useState(() => !!(window.SpeechRecognition || window.webkitSpeechRecognition));
  const endRef = _useRef(null);
  const taRef = _useRef(null);
  const recRef = _useRef(null);
  const srRef = _useRef(null);

  // Auto-dismiss finance banner after 8 seconds
  _useEffect(() => {
    if (!financeUpdated) return;
    const t = setTimeout(() => onFinanceDismiss?.(), 8000);
    return () => clearTimeout(t);
  }, [financeUpdated, onFinanceDismiss]);
```

Then, in the JSX return (around line 215–216), add the banner immediately inside `<div className="chat">` before `<div className="chat-scroll ...">`:

```javascript
// Before:
  return (
    <div className="chat" style={{ '--agent-hue': ag.hue }}>
      <div className="chat-scroll scroll">

// After:
  return (
    <div className="chat" style={{ '--agent-hue': ag.hue }}>
      {financeUpdated && (
        <div className="finance-notif">
          <span>Finance data updated —</span>
          <a href="/finance" target="_self">open dashboard →</a>
          <button className="finance-notif-close" onClick={onFinanceDismiss}>✕</button>
        </div>
      )}
      <div className="chat-scroll scroll">
```

- [ ] **Step 4: Smoke test — page loads without JS errors**

Start the server:
```powershell
$env:PYTHONUTF8=1; python server.py
```

Open `http://localhost:8000` in browser. Open browser DevTools console. Verify: no JS errors on page load. Switch to Mansa agent — no errors.

- [ ] **Step 5: Commit**

```powershell
git add static/index/app.jsx static/index/views.jsx static/index/styles.css
git commit -m "feat(mansa): show finance-updated banner in chat after Mansa responds"
```

---

## Final Verification

```powershell
# 1. All tests pass
$env:PYTHONUTF8=1; pytest tests/ -v --tb=short 2>&1 | tail -10

# 2. Server imports clean
$env:PYTHONUTF8=1; python -c "import server; print('OK')"

# 3. Model confirmed
$env:PYTHONUTF8=1; python -c "import inspect, agents.budget_agent as m; src = inspect.getsource(m); assert 'mistral-large-latest' in src; print('Model: OK')"

# 4. End-to-end (manual)
# Start: $env:PYTHONUTF8=1; python server.py
# Chat with Mansa: "make my BCA balance 5 million rupiah"
# Expected: Mansa calls update_account_balance (not add_income)
# Expected: "Finance data updated" banner appears above chat
# Expected: click "open dashboard →" → /finance loads with updated balance
# Expected: /finance auto-refreshes every 5s (watch Network tab in DevTools)
```
