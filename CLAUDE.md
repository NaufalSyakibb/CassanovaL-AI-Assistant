# CLAUDE.md

## Project Overview
**Personal AI Multi-Agent Assistant** — A web + CLI personal assistant with 9 specialist AI agents powered by Mistral AI + LangChain. A supervisor router automatically directs chat messages to the right agent. A separate CrewAI-based pipeline system runs autonomous multi-agent research and data analysis jobs in the background, accessible via the web frontend's "Crew Mode".

---

## Chat Agents (LangChain / LangGraph)

| Key | Agent Name | Responsibility | Tools |
|-----|-----------|---------------|-------|
| `task` | Alfred | To-do list management | add/list/complete/delete/update tasks |
| `notes` | Cicero | Note-taking + wiki management | create/search/read notes, wiki tools |
| `news` | Najwa | Latest 24h news briefings | DuckDuckGo search (last 24h) |
| `coding` | Linus | Programming mentor & tutor | search docs, LLM reasoning |
| `schedule` | CalCore | Google Calendar management | list/create/update/delete events |
| `budget` | Mansa | Personal finance tracking | add income/expense, balance, monthly summary |
| `research` | Ferry | Deep autonomous research | deep web search, iterative search, URL fetch, wiki integration |
| `davinci` | Da Vinci | Creative thinking & brainstorming | LLM reasoning |
| `journal` | Dostoyevsky | Personal journaling | create/read/search journal entries |

---

## CrewAI Pipelines (Background Job System)

### Pipeline 1 — Ibn Al-Haytham Research Crew (7 agents)
Auto-detects research mode (academic / general / hybrid) and runs a phased pipeline:

```
Phase 1 — Sequential
  [1] Scout      → mistral-small-latest   topic map + [MODE: ACADEMIC/GENERAL/HYBRID]
  [2] Filter     → mistral-small-latest   source quality scoring, curate 10–15 sources

Phase 2 — Parallel (ThreadPoolExecutor)
  [3] IdeaGen    → mistral-large-latest  hypotheses + novel angles
  [4] Validator  → mistral-large-latest  cross-check claims, flag weak evidence [⚠]

Phase 3 — Sequential
  [5] Synthesizer→ mistral-large-latest  merge Phase 2 outputs into unified narrative
  [6] Critic     → mistral-large-latest  logic review, remove over-generalizations
  [7] Writer     → mistral-large-latest  final article with [Ref N] citations
```

**Output files** (saved to `AI Data/Ferry Agent/`):
- `task1_scout.txt` — topic map + mode tag
- `task2_filter.txt` — curated sources
- `task3a_ideas.txt` — hypotheses
- `task3b_validation.txt` — cross-checked claims
- `task4_synthesis.txt` — unified narrative
- `task5_critique.txt` — logic review
- `task6_final_report.md` — final article

### Pipeline 2 — DataAnalyst Crew (3 agents)
Cleans, analyzes, and visualizes CSV datasets:

```
[1] DataBot-Clean → mistral-small-latest  load + clean dataset
[2] DataBot-Stats → mistral-large-latest  statistical analysis
[3] DataBot-Viz   → mistral-small-latest  chart descriptions / visualization plan
```

---

## Architecture

### Chat Flow
```
User Input (browser or terminal)
    │
    ▼
router.py (SupervisorRouter)
    │   classifies intent with mistral-small-latest
    ▼
Correct Agent (lazy-loaded, LangGraph state machine)
    │   runs with its tools + chat history
    ▼
Response → browser / terminal
```

### Crew Flow
```
Browser (Crew Mode button) → POST /api/crew/kickoff
    │
    ▼
server.py starts background thread
    │
    ▼
crewai_agents.IbnAlHaythamPipeline.kickoff()
    │   Phase 1: Scout+Filter crew
    │   Phase 2: IdeaGen ‖ Validator (ThreadPoolExecutor)
    │   Phase 3: Synthesizer+Critic+Writer crew
    ▼
Output files written to AI Data/Ferry Agent/
    │
    ▼
GET /api/crew/status/{job_id} → browser polls until done
```

---

## Project Structure

```
ai_python/
├── main.py              # CLI entry point (LangChain agents)
├── server.py            # FastAPI web server (chat + crew endpoints)
├── router.py            # Supervisor router (intent classifier)
├── crewai_agents.py     # CrewAI pipelines: Ibn Al-Haytham (7-agent) + DataAnalyst (3-agent)
│
├── agents/              # LangChain agents
│   ├── base.py          # Shared agent builder
│   ├── task_agent.py    # Alfred — task management
│   ├── notes_agent.py   # Cicero — notes + wiki
│   ├── news_agent.py    # Najwa — news briefings
│   ├── coding_agent.py  # Linus — programming help
│   ├── schedule_agent.py# CalCore — Google Calendar
│   ├── budget_agent.py  # Mansa — personal finance
│   ├── research_agent.py# Ferry — deep research
│   ├── davinci_agent.py # Da Vinci — creative thinking
│   └── journal_agent.py # Dostoyevsky — journaling
│
├── tools/               # LangChain tool definitions
│   ├── task_tools.py
│   ├── notes_tools.py
│   ├── news_tools.py
│   ├── schedule_tools.py
│   ├── budget_tools.py
│   ├── research_tools.py
│   ├── wiki_tools.py    # Obsidian-style wiki (query/write/lint/ingest)
│   └── autoresearch_tools.py  # Persistent research program tracker
│
├── static/
│   ├── index.html       # Old single-file frontend (unused — redirect only)
│   ├── index/           # Current multi-file React frontend
│   │   ├── index.html   # HTML shell (loads all JSX + CSS)
│   │   ├── app.jsx      # Root App component, state, keyboard shortcuts
│   │   ├── views.jsx    # ChatView, DashboardView, Sidebar, RightPanel, Masthead
│   │   ├── overlays.jsx # CommandPalette, CrewDrawer, ResultModal
│   │   ├── data.jsx     # AGENTS config, MOCK data, API helper functions
│   │   ├── icons.jsx    # SVG icon components
│   │   └── styles.css   # All styles (CSS variables, components)
│   ├── avatars/         # Agent avatar images (JPG/PNG per agent)
│   └── uploads/         # File uploads for DataAnalyst crew
│
├── data/                # JSON flat-file storage
│   ├── tasks.json
│   ├── notes.json
│   └── budget.json
│
├── credentials/         # Google Calendar OAuth (never commit)
│   ├── credentials.json # Download from Google Cloud Console
│   └── token.pickle     # Auto-generated after first auth
│
├── docs/superpowers/    # Design specs and implementation plans
│   ├── specs/
│   └── plans/
│
├── AI Data/             # Agent output files (wiki, research reports, logs)
│   └── Ferry Agent/     # Ibn Al-Haytham pipeline output files
│
├── .env                 # API keys (never commit)
├── requirements.txt
├── CLAUDE.md            # This file
└── DOCUMENTATION.md     # Full codebase reference
```

---

## Environment Variables (`.env`)

```env
# Required
MISTRAL_API_KEY=your_mistral_key_here

# Search providers (priority: LinkUp > Serper > DuckDuckGo fallback)
LINKUP_API_KEY=your_linkup_key_here
SERPER_API_KEY=your_serper_key_here

# Optional
OBSIDIAN_VAULT_PATH=path/to/your/vault        # for wiki tools
```

If `LINKUP_API_KEY` is absent, falls back to Serper. If both absent, uses DuckDuckGo (free).

---

## How to Run

### Web Mode (recommended)
```bash
# Install dependencies
pip install -r requirements.txt

# Start the server
$env:PYTHONUTF8=1; python server.py

# Open in browser
# http://localhost:8000
```

### CLI Mode (chat agents only)
```bash
$env:PYTHONUTF8=1; python main.py
```

### Run Ibn Al-Haytham Pipeline directly (CLI)
```bash
$env:PYTHONUTF8=1; python crewai_agents.py --topic "CRISPR gene editing"
$env:PYTHONUTF8=1; python crewai_agents.py -t "Strategi pemasaran TikTok 2025"
```

---

## API Endpoints (server.py)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Send message to AI agent |
| `GET`  | `/api/tasks` | Tasks list + stats |
| `GET`  | `/api/notes` | Recent notes |
| `GET`  | `/api/budget/summary` | Financial summary |
| `POST` | `/api/crew/kickoff` | Start a CrewAI pipeline (research or dataanalyst) |
| `GET`  | `/api/crew/status/{job_id}` | Poll pipeline job status + outputs |
| `GET`  | `/api/crew/files` | List uploadable CSV files for DataAnalyst |
| `POST` | `/api/upload` | Upload CSV for DataAnalyst pipeline |

---

## Google Calendar Setup (One-time)
1. Go to https://console.cloud.google.com/
2. Create a project → Enable **Google Calendar API**
3. Go to **Credentials** → Create **OAuth 2.0 Client ID** (Desktop App)
4. Download the JSON → rename to `credentials.json` → place in `credentials/`
5. First run of the schedule agent opens a browser for authorization
6. After auth, `token.pickle` is saved automatically — no need to re-auth

---

## Key Conventions
- JSON data stored in `data/` (tasks, notes, budget)
- Agent output files stored in `AI Data/<Agent Name>/`
- Chat agents are lazy-loaded (only initialized when first used)
- Each chat agent maintains its own history (last 20 messages)
- Router uses `mistral-small-latest` (fast, `temperature=0.0`) for classification
- Chat agents use `mistral-large-latest` (quality responses)
- CrewAI pipeline LLMs: mistral-small (Phase 1), mistral-large (Phase 2 + Phase 3)
- Windows UTF-8 fix: always run with `$env:PYTHONUTF8=1`

---

## Dependencies
```bash
pip install -r requirements.txt
# Key packages:
# langchain langchain-mistralai langchain-community langchain-core langgraph
# crewai crewai-tools
# fastapi uvicorn[standard] python-multipart
# python-dotenv requests duckduckgo-search linkup-sdk
# google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **CassanovaL-AI-Assistant** (1839 symbols, 2482 relationships, 69 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/CassanovaL-AI-Assistant/context` | Codebase overview, check index freshness |
| `gitnexus://repo/CassanovaL-AI-Assistant/clusters` | All functional areas |
| `gitnexus://repo/CassanovaL-AI-Assistant/processes` | All execution flows |
| `gitnexus://repo/CassanovaL-AI-Assistant/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
