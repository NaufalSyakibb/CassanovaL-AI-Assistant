# PIXEL.AI — Full Codebase Documentation
### A Reverse Engineer's Guide to Every File, Function, and Data Flow

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture — The Big Picture](#2-architecture--the-big-picture)
3. [Directory Structure](#3-directory-structure)
4. [Data Flow — How a Message Travels](#4-data-flow--how-a-message-travels)
5. [Entry Points](#5-entry-points)
   - [main.py — CLI Mode](#mainpy--cli-mode)
   - [server.py — Web Mode](#serverpy--web-mode)
6. [The Brain — router.py](#6-the-brain--routerpy)
7. [Agent Factory — agents/base.py](#7-agent-factory--agentsbasepy)
8. [The Six Agents](#8-the-six-agents)
   - [task_agent.py](#task_agentpy)
   - [notes_agent.py](#notes_agentpy)
   - [news_agent.py](#news_agentpy)
   - [coding_agent.py](#coding_agentpy)
   - [schedule_agent.py](#schedule_agentpy)
   - [budget_agent.py](#budget_agentpy)
9. [Tools Layer](#9-tools-layer)
   - [task_tools.py](#task_toolspy)
   - [notes_tools.py](#notes_toolspy)
   - [news_tools.py](#news_toolspy)
   - [schedule_tools.py](#schedule_toolspy)
   - [budget_tools.py](#budget_toolspy)
10. [Data Storage](#10-data-storage)
11. [Frontend — static/index.html](#11-frontend--staticindexhtml)
12. [API Reference](#12-api-reference)
13. [Key Concepts Explained](#13-key-concepts-explained)
14. [Dependencies](#14-dependencies)
15. [Setup & Configuration](#15-setup--configuration)

---

## 1. Project Overview

This is a **multi-agent AI personal assistant** built in Python. It has six specialist AI agents, each an expert in one domain. A supervisor router reads your message and automatically sends it to the right agent. No need to switch modes or use commands — just talk naturally.

```
"add buy groceries to my tasks"         → goes to QUEST  (task agent)
"what's the tech news today?"           → goes to TICKER (news agent)
"explain Python decorators"             → goes to SENSEI (coding agent)
"add expense 50000 for lunch"           → goes to VAULT  (budget agent)
```

**Two ways to run it:**
- **CLI mode** → runs in your terminal (`python main.py`)
- **Web mode** → serves a browser UI at `http://localhost:8000` (`python server.py`)

---

## 2. Architecture — The Big Picture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER INPUT                           │
│        (terminal OR browser at localhost:8000)              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   ENTRY POINT                               │
│   main.py (CLI)          OR          server.py (Web)        │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              router.py — SupervisorRouter                   │
│                                                             │
│  Step 1: classify()  — asks mistral-small "which agent?"   │
│  Step 2: _load_agent() — lazy-loads the right agent        │
│  Step 3: agent.invoke() — sends message + history          │
└──────┬──────┬──────┬──────┬──────┬──────┬──────────────────┘
       │      │      │      │      │      │
       ▼      ▼      ▼      ▼      ▼      ▼
    task   notes  news  coding sched  budget
    agent  agent  agent agent  agent  agent
       │      │      │      │      │      │
       ▼      ▼      ▼      ▼      ▼      ▼
   TASK_  NOTES_ NEWS_  CODING SCHED_ BUDGET_
   TOOLS  TOOLS  TOOLS  TOOLS  TOOLS  TOOLS
       │      │      │      │      │      │
       ▼      ▼      ▼      ▼      ▼      │
  tasks.json notes.json  DuckDuckGo   budget.json
                                      Google Calendar
```

**Key design principle: every agent is independent.** Each agent has its own:
- System prompt (personality + instructions)
- Tool list (what it can DO)
- Chat history (last 20 messages, per agent)

---

## 3. Directory Structure

```
ai_python/
│
├── main.py              ← CLI entry point (terminal interface)
├── server.py            ← Web entry point (FastAPI server)
├── router.py            ← Supervisor: classifies and routes messages
│
├── agents/              ← One file per agent
│   ├── base.py          ← Shared factory function that builds any agent
│   ├── task_agent.py    ← QUEST: to-do list manager
│   ├── notes_agent.py   ← SCRIBE: note-taking + research
│   ├── news_agent.py    ← TICKER: 24h news briefings
│   ├── coding_agent.py  ← SENSEI: programming tutor
│   ├── schedule_agent.py← CLOCKWORK: Google Calendar
│   └── budget_agent.py  ← VAULT: personal finance
│
├── tools/               ← One file per tool group
│   ├── task_tools.py    ← add/list/complete/delete/update tasks
│   ├── notes_tools.py   ← create/read/search/update/delete notes + URL fetch
│   ├── news_tools.py    ← DuckDuckGo search (last 24h)
│   ├── schedule_tools.py← Google Calendar API (list/create/update/delete events)
│   └── budget_tools.py  ← add income/expense, balance, monthly summary
│
├── data/                ← JSON flat-file "database"
│   ├── tasks.json       ← list of task objects
│   ├── notes.json       ← list of note objects
│   └── budget.json      ← list of transaction objects
│
├── credentials/         ← Google OAuth (never commit these)
│   ├── credentials.json ← Downloaded from Google Cloud Console
│   └── token.pickle     ← Auto-generated after first OAuth login
│
├── static/
│   └── index.html       ← Entire React frontend (single file)
│
├── .env                 ← API keys (never commit)
├── requirements.txt     ← Python dependencies
└── CLAUDE.md            ← Project instructions
```

---

## 4. Data Flow — How a Message Travels

Let's trace exactly what happens when you type **"add task: buy milk"** in the browser.

### Step 1 — Browser sends HTTP POST
```
POST http://localhost:8000/api/chat
Body: { "message": "add task: buy milk", "agent": "task" }
```
The frontend always sends the currently-selected agent ID in the body.

### Step 2 — server.py receives the request
```python
@app.post("/api/chat")
async def chat(req: ChatRequest):
    supervisor = get_supervisor()
    agent_name, response = supervisor.chat_direct(req.agent, req.message)
    return {"agent": agent_name, "response": response}
```
Because `req.agent` is `"task"`, it calls `chat_direct()`, skipping auto-classification.

### Step 3 — router.py loads and calls the agent
```python
def chat_direct(self, agent_name, user_message):
    agent = self._load_agent("task")        # lazy-loads task agent on first call
    history = self._chat_histories["task"]  # [] initially, grows over session
    messages = history + [HumanMessage(content=user_message)]
    response = agent.invoke({"messages": messages})
    answer = response["messages"][-1].content
    # appends to history, trims to last 20
    return "task", answer
```

### Step 4 — LangGraph agent runs the tool loop
The agent (a `CompiledStateGraph` from LangChain 1.x) does:
1. Sends messages to `mistral-large-latest`
2. The LLM sees the system prompt + chat history + "add task: buy milk"
3. The LLM decides to call `add_task(title="buy milk", priority="medium")`
4. LangGraph executes the tool → writes to `data/tasks.json`
5. Tool returns: `"Task added! ID:ab3f1c2d | \"buy milk\" | Priority:medium"`
6. LLM formulates final reply: `"Done! I've added 'buy milk' to your task list."`

### Step 5 — Response travels back
```
agent.invoke() → router → server.py → HTTP 200 JSON → browser → React state → rendered in chat
```

---

## 5. Entry Points

### main.py — CLI Mode

**Purpose:** Runs the assistant as a terminal chatbot.

```python
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
```
> **Why this line?** Windows uses `cp1252` encoding by default. This forces `stdout` to UTF-8 so emoji and non-ASCII characters don't crash the terminal.

```python
router = SupervisorRouter()
```
> Creates the router. This connects to Mistral AI immediately (validates the API key).

```python
while True:
    user_input = input("You: ").strip()
    agent_name, answer = router.chat(user_input)
    icon = AGENT_ICONS.get(agent_name, "[ AGENT   ]")
    print(f"\n{icon}\n{answer}\n")
```
> The main loop. `router.chat()` does **auto-classification** (unlike the web mode which sends the agent explicitly). The icon shows which agent answered.

**Special commands recognized before routing:**
- `quit` / `exit` / `keluar` / `bye` → exits
- `help` → prints example commands
- Empty input → skipped

---

### server.py — Web Mode

**Purpose:** HTTP server that serves the React frontend AND exposes the AI as a REST API.

**Tech stack:** FastAPI + Uvicorn

```python
app = FastAPI(title="OmniSync API", version="1.0.0")
```

#### CORS Middleware
```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
```
> Allows requests from any origin. Required because the browser frontend and API are on the same origin normally, but this also allows testing from tools like Postman or a different port.

#### Lazy Supervisor
```python
_supervisor = None

def get_supervisor():
    global _supervisor
    if _supervisor is None:
        from router import SupervisorRouter
        _supervisor = SupervisorRouter()
    return _supervisor
```
> The supervisor is only created when the first request comes in. This prevents startup delay — the server starts instantly, and the AI initializes on the first message.

#### Endpoints

| Method | Path | What it does |
|--------|------|-------------|
| `POST` | `/api/chat` | Send message to AI agent, get response |
| `GET`  | `/api/tasks` | Get all tasks + stats (for sidebar panel) |
| `GET`  | `/api/notes` | Get recent notes + total count |
| `GET`  | `/api/budget/summary` | Get balance, monthly totals, recent transactions |
| `GET`  | `/{any_path}` | Serve `static/index.html` (SPA fallback) |

#### The SPA Catch-All Route
```python
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    return FileResponse("static/index.html")
```
> Any URL that doesn't match an API route (e.g. `/`, `/settings`, `/anything`) returns `index.html`. This is the standard pattern for single-page applications.

---

## 6. The Brain — router.py

**Purpose:** Decides which agent handles each message. Acts as a traffic cop.

### AGENT_REGISTRY
```python
AGENT_REGISTRY = {
    "task":     "Managing to-do lists, tasks, reminders, and deadlines",
    "notes":    "Writing notes, saving information, summarizing articles or research URLs",
    "news":     "Latest news, current events, headlines, recent updates",
    "coding":   "Programming help, code explanation, debugging, tutorials, tech questions",
    "schedule": "Calendar, meetings, events, appointments, schedule management",
    "budget":   "Money, expenses, income, spending, finance, budget, cashflow",
}
```
> This dictionary does two things:
> 1. Lists which agent names are valid
> 2. Provides descriptions used in the classification prompt

### SupervisorRouter Class

```python
self.llm = ChatMistralAI(model="mistral-small-latest", temperature=0.0)
```
> Uses the **small** Mistral model for routing because:
> - Classification is a simple task (pick one of six words)
> - `temperature=0.0` means completely deterministic — no randomness
> - Small model = faster + cheaper (routing happens on every message)

```python
self._agents: dict = {}
self._chat_histories: dict = {name: [] for name in AGENT_REGISTRY}
```
> - `_agents` starts empty — agents are created only when first needed (**lazy loading**)
> - `_chat_histories` stores a separate conversation history for each agent so context is preserved per-agent

### classify() — The Classifier
```python
def classify(self, message: str) -> str:
    agent_list = "\n".join(f"- {name}: {desc}" for name, desc in AGENT_REGISTRY.items())
    prompt = CLASSIFY_PROMPT.format(agent_list=agent_list, message=message)
    response = self.llm.invoke([HumanMessage(content=prompt)])
    agent_name = response.content.strip().lower().split()[0]
    return agent_name if agent_name in AGENT_REGISTRY else "task"
```
> Sends a prompt to Mistral that looks like:
> ```
> Available agents:
> - task: Managing to-do lists...
> - notes: Writing notes...
> ...
> User message: "what's bitcoin price today?"
> Agent:
> ```
> The LLM replies with just one word: `news`. If the reply isn't a valid agent name, it defaults to `task`.

### _load_agent() — Lazy Loading
```python
def _load_agent(self, name: str):
    if name not in self._agents:
        from agents.task_agent import create_task_agent
        self._agents[name] = create_task_agent()
    return self._agents[name]
```
> Python imports are cached by the interpreter. This pattern means:
> - First call to `_load_agent("task")` → imports module + creates agent
> - Subsequent calls → returns the already-created agent from `self._agents`
> - Agents you never use are never loaded (saves memory + API calls)

### chat() vs chat_direct()

| | `chat()` | `chat_direct()` |
|---|---|---|
| Classification | Yes (calls `classify()`) | No (uses agent name directly) |
| Used by | `main.py` (CLI) | `server.py` (web) |
| Why | Terminal doesn't show which agent is selected | Browser always shows which agent tab is active |

### Chat History Management
```python
history.append(HumanMessage(content=user_message))
history.append(AIMessage(content=answer))
if len(history) > 20:
    self._chat_histories[agent_name] = history[-20:]
```
> - History is stored as LangChain message objects (`HumanMessage`, `AIMessage`)
> - Capped at 20 messages to prevent infinite context growth (would slow API calls + cost more tokens)
> - Each agent has **isolated** history — switching from task to notes doesn't mix conversations

---

## 7. Agent Factory — agents/base.py

**Purpose:** One function that builds any agent. All six agents use this.

```python
from langchain.agents import create_agent

def build_agent(system_prompt: str, tools: list, temperature: float = 0.2):
    llm = ChatMistralAI(
        model="mistral-large-latest",
        temperature=temperature,
        mistral_api_key=api_key,
    )
    return create_agent(llm, tools, system_prompt=system_prompt)
```

**Why `mistral-large-latest` here but `mistral-small-latest` in the router?**
- The router just classifies (pick one word from six) → small model is fine
- The agents must understand nuanced requests, write code, manage data, format outputs → large model needed

**What does `create_agent()` return?**
It returns a `CompiledStateGraph` — a LangGraph state machine that:
1. Starts with the message list
2. Calls the LLM
3. If LLM wants to call a tool → executes it
4. Feeds tool result back to LLM
5. Repeats until LLM gives a final answer (no more tool calls)
6. Returns final state with all messages

**The `temperature` parameter:**
- `0.0` = fully deterministic (router)
- `0.1` = nearly deterministic (news — factual reporting)
- `0.2` = slight creativity (default for task, notes, schedule, budget)
- `0.3` = more varied (coding — allows multiple explanation styles)

---

## 8. The Six Agents

Each agent file has just two things: a **system prompt** and a **factory function**.

### task_agent.py
```python
SYSTEM_PROMPT = """You are a personal task management assistant...
Be concise and organized. Format task lists clearly.
If the user speaks in Indonesian, respond in Indonesian."""

def create_task_agent():
    return build_agent(SYSTEM_PROMPT, TASK_TOOLS)
```
- **Tools available:** `add_task`, `list_tasks`, `complete_task`, `delete_task`, `update_task`
- **Data store:** `data/tasks.json`
- **Bilingual:** responds in Indonesian if the user writes in Indonesian

### notes_agent.py
```python
SYSTEM_PROMPT = """You are a professional note-taking and research assistant, like Notion + a research summarizer.
...Use bullet points for key insights. Organize notes with relevant tags."""
```
- **Tools available:** `create_note`, `list_notes`, `read_note`, `search_notes`, `update_note`, `delete_note`, `fetch_and_summarize_url`
- **Special ability:** can fetch a URL and return text content for the LLM to summarize
- **Data store:** `data/notes.json`

### news_agent.py
```python
def create_news_agent():
    return build_agent(SYSTEM_PROMPT, NEWS_TOOLS, temperature=0.1)
```
- **Tools available:** `get_recent_news`, `get_top_headlines`
- **Data store:** none — uses live DuckDuckGo search
- **Low temperature (0.1):** news reporting should be factual, not creative
- **Time filter:** DuckDuckGo configured with `time="d"` (last 24 hours only)

### coding_agent.py
```python
# NOTE: This agent defines its own tool inline, not in tools/
@tool
def search_documentation(query: str) -> str:
    result = _web_search.run(f"{query} documentation site:docs.python.org OR ...")
    return result
```
- **Unique:** the only agent that defines its tool **inside its own file** rather than in `tools/`
- **Why?** The search tool is tightly coupled to coding context (specific site filters)
- **Temperature 0.3:** coding explanations benefit from some variation

### schedule_agent.py
```python
SYSTEM_PROMPT = """...Use Asia/Jakarta timezone by default..."""
```
- **Tools available:** `list_upcoming_events`, `get_today_schedule`, `create_event`, `delete_event`, `update_event`
- **Requires:** `credentials/credentials.json` from Google Cloud Console
- **Auth flow:** On first use, opens a browser for OAuth. Saves token to `credentials/token.pickle` — never needs re-auth unless token expires.

### budget_agent.py
```python
SYSTEM_PROMPT = """...use Rupiah (Rp) as the default currency..."""
```
- **Tools available:** `add_income`, `add_expense`, `get_balance`, `list_transactions`, `get_monthly_summary`, `delete_transaction`
- **Data store:** `data/budget.json`
- **Localized:** uses Rupiah by default, responds in Indonesian if addressed in Indonesian

---

## 9. Tools Layer

Tools are Python functions decorated with `@tool` from LangChain. The decorator:
1. Reads the function's docstring → becomes the tool description the LLM sees
2. Reads the type hints → tells the LLM what arguments to provide
3. Wraps the function → makes it callable by the LangGraph agent loop

### task_tools.py

**Pattern used by all JSON-based tools:**
```python
TASKS_FILE = "data/tasks.json"

def _load() -> list:
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(data: list):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
```
> `_load()` and `_save()` are private helpers (underscore prefix = convention for "internal use"). Every read operation loads the whole file; every write rewrites the whole file. Simple but works fine at personal-assistant scale.

**Task data structure:**
```json
{
  "id": "ab3f1c2d",
  "title": "buy milk",
  "priority": "medium",
  "due_date": "2025-04-10",
  "status": "pending",
  "created_at": "2025-04-04 10:30"
}
```

| Tool | What it does |
|------|-------------|
| `add_task(title, priority, due_date)` | Appends new task object with UUID ID |
| `list_tasks(filter_status, filter_priority)` | Filters and formats task list |
| `complete_task(task_id)` | Sets `status = "completed"` |
| `delete_task(task_id)` | Removes task by ID |
| `update_task(task_id, title, priority, due_date)` | Updates any field by ID |

**ID generation:**
```python
"id": str(uuid.uuid4())[:8]
```
> Generates a random UUID and takes the first 8 characters (e.g. `"ab3f1c2d"`). Short enough for the LLM to type in tool calls, unique enough for personal-scale data.

---

### notes_tools.py

**Note data structure:**
```json
{
  "id": "7e2a9b1f",
  "title": "Python async/await notes",
  "content": "async functions are coroutines...",
  "tags": ["python", "async", "programming"],
  "created_at": "2025-04-04 09:00",
  "updated_at": "2025-04-04 09:00"
}
```

| Tool | What it does |
|------|-------------|
| `create_note(title, content, tags)` | Creates note; tags is comma-separated string → split to list |
| `list_notes(tag_filter)` | Shows all notes or filtered by tag; truncates content at 80 chars |
| `read_note(note_id)` | Returns full content of one note |
| `search_notes(query)` | Case-insensitive search in title AND content |
| `update_note(note_id, ...)` | Updates any field + refreshes `updated_at` |
| `delete_note(note_id)` | Removes note |
| `fetch_and_summarize_url(url)` | Fetches page, strips HTML tags with regex, returns first 3000 chars |

**How URL fetching works:**
```python
import re
text = re.sub(r"<[^>]+>", " ", response.text)  # strip <html tags>
text = re.sub(r"\s+", " ", text).strip()         # collapse whitespace
return text[:3000]                                # LLM reads this and summarizes
```
> This is "dumb" HTML stripping — it removes tags but keeps all text including nav, footer etc. It works well enough for the LLM to extract the important content.

---

### news_tools.py

```python
_search = DuckDuckGoSearchAPIWrapper(time="d", max_results=8)
```
> `time="d"` = results from last day only. `max_results=8` = up to 8 results per query.

| Tool | What it does |
|------|-------------|
| `get_recent_news(topic)` | Searches `"{topic} news today"` |
| `get_top_headlines()` | Runs 3 searches: tech, world, business news today |

---

### schedule_tools.py

**Authentication flow:**
```python
def _get_calendar_service():
    creds = None
    if os.path.exists(TOKEN_FILE):          # 1. Try loading saved token
        creds = pickle.load(...)
    if not creds or not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())         # 2. Auto-refresh if expired
        else:
            flow = InstalledAppFlow(...)
            creds = flow.run_local_server()  # 3. Full OAuth (opens browser)
    pickle.dump(creds, open(TOKEN_FILE, "wb"))  # 4. Save for next time
    return build("calendar", "v3", credentials=creds)
```
> **Pickle** is Python's built-in serialization format. The OAuth credentials object (which isn't plain JSON) is saved/loaded as binary data.

| Tool | What it does |
|------|-------------|
| `list_upcoming_events(days=7)` | Lists next N days of events |
| `get_today_schedule()` | Today's events only |
| `create_event(title, start, end, description)` | Creates event in primary calendar |
| `delete_event(event_id)` | Finds event by ID prefix, then deletes |
| `update_event(event_id, ...)` | Patch update on found event |

**Timezone:** All events use `Asia/Jakarta` (UTC+7) by default.

**Partial ID matching:**
```python
for e in events:
    if e["id"].startswith(event_id):  # match partial ID
```
> Google Calendar event IDs are very long strings. The UI shows only the first 12 characters. Tools search for events whose full ID starts with the partial ID provided.

---

### budget_tools.py

**Transaction data structure:**
```json
{
  "id": "3c7d8e9a",
  "type": "expense",
  "amount": 50000.0,
  "category": "food",
  "description": "lunch at warung",
  "date": "2025-04-04",
  "created_at": "2025-04-04 12:30"
}
```

| Tool | What it does |
|------|-------------|
| `add_income(amount, category, description, date)` | Records income transaction |
| `add_expense(amount, category, description, date)` | Records expense transaction |
| `get_balance()` | `sum(income) - sum(expense)` across all time |
| `list_transactions(month, tx_type)` | Filter by month (YYYY-MM) and/or type |
| `get_monthly_summary(month)` | Grouped totals by category for a month |
| `delete_transaction(transaction_id)` | Remove a transaction |

**Number formatting:**
```python
f"+{amount:,.0f}"   # → "+50,000" (comma thousands separator, no decimals)
```

---

## 10. Data Storage

All data is stored as **JSON flat files** in `data/`. There is no database.

### Why JSON files?
- Zero setup (no database server to install)
- Human-readable and editable
- Sufficient for personal-assistant scale (hundreds or low thousands of records)
- Easy to backup, sync, or inspect

### File schemas

**data/tasks.json** — list of task objects
```json
[
  {
    "id": "string (8 chars)",
    "title": "string",
    "priority": "high | medium | low",
    "due_date": "YYYY-MM-DD | empty string",
    "status": "pending | completed",
    "created_at": "YYYY-MM-DD HH:MM"
  }
]
```

**data/notes.json** — list of note objects
```json
[
  {
    "id": "string (8 chars)",
    "title": "string",
    "content": "string (full text)",
    "tags": ["string", "..."],
    "created_at": "YYYY-MM-DD HH:MM",
    "updated_at": "YYYY-MM-DD HH:MM"
  }
]
```

**data/budget.json** — list of transaction objects
```json
[
  {
    "id": "string (8 chars)",
    "type": "income | expense",
    "amount": 50000.0,
    "category": "string",
    "description": "string",
    "date": "YYYY-MM-DD",
    "created_at": "YYYY-MM-DD HH:MM"
  }
]
```

---

## 11. Frontend — static/index.html

The entire frontend is a **single HTML file** with inline React (loaded via CDN). No build step, no `npm install`.

### Technology stack
| Technology | Version | How loaded |
|-----------|---------|-----------|
| React | 18 | CDN (`unpkg.com`) |
| ReactDOM | 18 | CDN |
| Babel Standalone | latest | CDN — compiles JSX in the browser |
| Press Start 2P | font | Google Fonts |
| VT323 | font | Google Fonts |

### Why single-file React with Babel?
Normally React needs a build tool (Vite, webpack). Babel Standalone compiles JSX to plain JavaScript **inside the browser at runtime**. This adds ~1-2 seconds of load time but eliminates any build process.

### Key Variables

```javascript
// Auto-detects if opened as file:// and falls back to localhost
const API = (
  window.location.protocol === 'file:' ||
  window.location.origin === 'null'
) ? 'http://localhost:8000' : window.location.origin;
```

```javascript
const P = { bg0:'#0a0a0f', grn:'#00ff41', ... }  // 8-bit color palette
const SP = { task: [[x,y,color], ...], ... }       // pixel sprite data
const AGENTS = { task: { name:'QUEST', ... }, ... } // agent config
```

### Component Tree
```
App
├── Sidebar            ← left panel, agent selector
│   └── Avatar         ← pixel art SVG sprite
├── div (main chat)
│   ├── header bar     ← shows active agent name + dot indicators
│   ├── div (messages) ← scrollable message area
│   │   ├── Bubble[]   ← one per message (user or agent)
│   │   └── TypingIndicator ← animated dots while waiting
│   └── ChatInput      ← textarea + send button
└── DataPanel          ← right panel, contextual data
    ├── TaskWidget      ← stats + pending tasks list
    ├── NotesWidget     ← recent notes list
    ├── BudgetWidget    ← balance + recent transactions
    ├── NewsWidget      ← quick topic buttons
    ├── CodingWidget    ← quick curriculum buttons
    └── ScheduleWidget  ← quick action buttons
```

### State Management
All state lives in the `App` component:

```javascript
const [activeAgent, setActiveAgent]         // which tab is selected
const [messagesByAgent, setMessagesByAgent] // { task: [msg,...], notes: [...], ... }
const [isLoading, setIsLoading]             // true while waiting for API response
const [panelData, setPanelData]             // { tasks:{}, notes:{}, budget:{} }
```

`messagesByAgent` is an object keyed by agent ID. Each agent has its own message array, so switching agents shows the conversation history for that agent — messages never mix.

### Pixel Art Sprites
```javascript
const Sprite = ({ pixels, size = 28 }) => (
  <svg viewBox="0 0 16 16" style={{ imageRendering:'pixelated' }}>
    {pixels.map(([x, y, color], i) => (
      <rect key={i} x={x} y={y} width={1} height={1} fill={color}/>
    ))}
  </svg>
);
```
Each sprite is a 16×16 grid. Pixels are stored as `[x, y, color]` tuples. The `imageRendering: pixelated` CSS property prevents the browser from anti-aliasing when the SVG is scaled up.

### Connection Health Check
```javascript
async function checkConnection() {
  try {
    const r = await fetch(`${API}/api/tasks`, { signal: AbortSignal.timeout(4000) });
    document.getElementById('conn-banner').style.display = r.ok ? 'none' : 'block';
  } catch {
    document.getElementById('conn-banner').style.display = 'block';
  }
}
checkConnection();           // run immediately on page load
setInterval(checkConnection, 15000); // recheck every 15 seconds
```
> Shows a red banner at the top if the backend is unreachable. Clears automatically when connection is restored.

### sendMessage() — The Core Function
```javascript
async function sendMessage(text) {
  // 1. Append user message to local state immediately (optimistic UI)
  setMessagesByAgent(prev => ({ ...prev, [activeAgent]: [...prev[activeAgent], userMsg] }));
  setIsLoading(true);

  // 2. POST to backend
  const res = await fetch(`${API}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: text, agent: activeAgent }),
  });

  // 3. Append agent response to state
  setMessagesByAgent(prev => ({ ...prev, [activeAgent]: [...prev[activeAgent], agentMsg] }));

  // 4. Refresh the data panel (tasks/notes/budget may have changed)
  await fetchPanelData(activeAgent);
}
```

---

## 12. API Reference

### POST /api/chat
Send a message and get an AI response.

**Request body:**
```json
{
  "message": "add task: finish report",
  "agent": "task"
}
```
> `agent` is optional. If omitted, the router auto-classifies. If provided, skips classification.

**Response:**
```json
{
  "agent": "task",
  "response": "Done! I've added 'finish report' to your task list with medium priority."
}
```

**Error (500):**
```json
{ "detail": "MISTRAL_API_KEY not found in .env file" }
```

---

### GET /api/tasks
Get all tasks with statistics.

**Response:**
```json
{
  "tasks": [ { "id": "...", "title": "...", "status": "pending", ... } ],
  "stats": { "total": 5, "pending": 3, "completed": 2, "high_priority": 1 }
}
```

---

### GET /api/notes
Get recent notes (latest 8, sorted by `updated_at`).

**Response:**
```json
{
  "notes": [ { "id": "...", "title": "...", "tags": [...], ... } ],
  "total": 23
}
```

---

### GET /api/budget/summary
Get financial summary.

**Response:**
```json
{
  "balance": 4500000,
  "total_income": 5000000,
  "total_expense": 500000,
  "monthly_income": 5000000,
  "monthly_expense": 500000,
  "recent_transactions": [ { "id": "...", "type": "income", "amount": 5000000, ... } ]
}
```

---

## 13. Key Concepts Explained

### What is a LangChain `@tool`?
```python
@tool
def add_task(title: str, priority: str = "medium") -> str:
    """Add a new task. Args: title, priority ('high'/'medium'/'low')."""
    ...
```
The `@tool` decorator wraps a regular Python function so that:
1. The LLM can "see" it — the docstring becomes the tool's description
2. The LLM can "call" it — the type hints tell the LLM what arguments to provide
3. The agent framework can execute it — result is fed back to the LLM

The LLM never runs Python code. It generates a structured JSON object like:
```json
{ "tool": "add_task", "args": { "title": "buy milk", "priority": "high" } }
```
LangGraph sees this, runs the actual `add_task()` function, and returns the result to the LLM.

### What is a `CompiledStateGraph`?
LangChain 1.x replaced `AgentExecutor` with LangGraph. An agent is now a graph (state machine):

```
START
  │
  ▼
[call_model] ──── LLM decides: call a tool? ────→ [execute_tools] ──┐
     ▲                                                               │
     └───────────────────────────────────────────────────────────────┘
                       │
                       │ LLM decides: done
                       ▼
                     END
```

The loop runs until the LLM produces a message with no tool calls. You invoke it with:
```python
result = agent.invoke({"messages": [HumanMessage("add task: buy milk")]})
answer = result["messages"][-1].content
```

### What is Lazy Loading?
```python
self._agents: dict = {}

def _load_agent(self, name):
    if name not in self._agents:
        # expensive operation — only do it once
        self._agents[name] = create_task_agent()
    return self._agents[name]
```
The agent object (including the LLM connection) is only created the first time that agent is needed. If you only ever talk to the task agent, the other 5 agents are never initialized. This saves startup time and memory.

### What is Chat History?
```python
history = [
    HumanMessage(content="add task: buy milk"),
    AIMessage(content="Done! Added 'buy milk' with medium priority."),
    HumanMessage(content="actually make it high priority"),
    AIMessage(content="Updated! 'buy milk' is now high priority."),
]
```
Every message is passed to the LLM on the next call. This is how the LLM "remembers" what was said earlier. Without history, every message would be a fresh conversation.

The `HumanMessage` / `AIMessage` classes are LangChain wrappers around the standard chat message format that all LLM APIs use.

---

## 14. Dependencies

```
langchain          — Core framework, @tool decorator, create_agent
langchain-mistralai — ChatMistralAI class (connects to Mistral API)
langchain-community — DuckDuckGoSearchRun, DuckDuckGoSearchAPIWrapper
langchain-core     — HumanMessage, AIMessage, PromptTemplate
langgraph          — CompiledStateGraph (installed with langchain 1.x)
python-dotenv      — Reads .env file into os.environ
requests           — HTTP client (used in fetch_and_summarize_url)
duckduckgo-search  — DuckDuckGo search without an API key
google-api-python-client  — Google Calendar API client
google-auth-httplib2      — HTTP adapter for Google auth
google-auth-oauthlib      — OAuth 2.0 flow for Google APIs
fastapi            — Web framework (routes, middleware, request models)
uvicorn[standard]  — ASGI server that runs FastAPI
python-multipart   — Required by FastAPI for form data
```

---

## 15. Setup & Configuration

### Environment Variables (.env)
```
MISTRAL_API_KEY=your_key_here
```
Get a key at: https://console.mistral.ai/

### Initial data files
The `data/` folder needs three empty JSON arrays to start:
```
data/tasks.json  → []
data/notes.json  → []
data/budget.json → []
```

### Google Calendar (one-time setup)
1. Go to https://console.cloud.google.com/
2. Create project → Enable **Google Calendar API**
3. Create **OAuth 2.0 Client ID** (type: Desktop App)
4. Download JSON → rename to `credentials.json` → place in `credentials/`
5. First time you use the Schedule agent, a browser opens for authorization
6. After authorization, `credentials/token.pickle` is saved automatically

### Running the project
```bash
# Install dependencies
pip install -r requirements.txt

# Create data files if they don't exist
echo [] > data/tasks.json
echo [] > data/notes.json
echo [] > data/budget.json

# CLI mode
$env:PYTHONUTF8=1; python main.py

# Web mode

cd "c:\Users\muham\OneDrive\Dokumen\Python\ai_python"
$env:PYTHONUTF8=1; python server.py
# Then open: http://localhost:8000
```

### Why `$env:PYTHONUTF8=1`?
Windows uses `cp1252` (Windows-1252) as the default terminal encoding. This environment variable forces Python to use UTF-8 everywhere — required for emoji, Indonesian characters (é, ñ, etc.), and any non-ASCII text in the AI responses.

---

*Documentation generated for PIXEL.AI — Multi-Agent Personal Assistant*
*Stack: Python 3.12 · LangChain 1.x · LangGraph · Mistral AI · FastAPI · React 18*
