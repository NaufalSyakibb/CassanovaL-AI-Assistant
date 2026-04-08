# CLAUDE.md

## Project Overview
**Personal AI Multi-Agent Assistant** — A CLI-based personal assistant with 7 specialist AI agents, all powered by Mistral AI + LangChain. Each agent handles a specific domain; a supervisor router automatically directs messages to the right one.

## Agents
| Agent | Responsibility | Tools |
|-------|---------------|-------|
| Task | To-do list management | add/list/complete/delete/update tasks |
| Notes | Note-taking + research summary | create/search/read notes, fetch & summarize URLs |
| News | Latest 24h news briefings | DuckDuckGo search (last 24h) |
| Coding | Programming mentor & tutor | search docs, LLM reasoning |
| Schedule | Google Calendar management | list/create/update/delete events |
| Budget | Personal finance tracking | add income/expense, balance, monthly summary |
| Research | Deep autonomous research & paper summarization | deep web search, iterative multi-angle search, fetch & read URLs, multi-source synthesis, compile report |

## Architecture
```
User Input
    │
    ▼
router.py (SupervisorRouter)
    │   classifies intent with mistral-small-latest
    ▼
Correct Agent (lazy-loaded)
    │   runs with its tools + chat history
    ▼
Response
```

## Project Structure
```
ai_python/
├── main.py              # CLI entry point
├── router.py            # Supervisor router (intent classifier)
├── agents/
│   ├── base.py          # Shared agent builder
│   ├── task_agent.py
│   ├── notes_agent.py
│   ├── news_agent.py
│   ├── coding_agent.py
│   ├── schedule_agent.py
│   └── budget_agent.py
├── tools/
│   ├── task_tools.py
│   ├── notes_tools.py
│   ├── news_tools.py
│   ├── schedule_tools.py
│   └── budget_tools.py
├── data/
│   ├── tasks.json
│   ├── notes.json
│   └── budget.json
├── credentials/         # Google Calendar OAuth files (never commit)
│   ├── credentials.json # Download from Google Cloud Console
│   └── token.pickle     # Auto-generated after first auth
├── .env                 # API keys (never commit)
├── requirements.txt
└── CLAUDE.md
```

## Environment Variables (`.env`)
```
MISTRAL_API_KEY=your_mistral_key_here
```

## How to Run

### CLI Mode (terminal)
```bash
$env:PYTHONUTF8=1; python main.py
```

### Web Mode (browser)
```bash
# Install dependencies
pip install -r requirements.txt

# Start the web server
$env:PYTHONUTF8=1; python server.py

# Open in browser
# http://localhost:8000
```

## Google Calendar Setup (One-time)
1. Go to https://console.cloud.google.com/
2. Create a project → Enable **Google Calendar API**
3. Go to **Credentials** → Create **OAuth 2.0 Client ID** (Desktop App)
4. Download the JSON file → rename to `credentials.json`
5. Place it in the `credentials/` folder
6. First run of the schedule agent will open a browser for authorization
7. After auth, `token.pickle` is saved automatically — no need to re-auth

## Key Conventions
- All JSON data stored in `data/` folder
- Agents are lazy-loaded (only initialized when first used)
- Each agent maintains its own chat history (last 20 messages)
- Router uses `mistral-small-latest` (fast) for classification
- Specialist agents use `mistral-large-latest` for quality responses
- Windows UTF-8 fix applied in `main.py`

## Dependencies
```bash
pip install langchain langchain-mistralai langchain-community langchain-core \
            python-dotenv requests duckduckgo-search \
            google-api-python-client google-auth-httplib2 google-auth-oauthlib
```
