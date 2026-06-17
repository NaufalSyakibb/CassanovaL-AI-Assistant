# CassanovaL Intelligence Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Mistral-synthesized learning report to Alfred's Overview tab, showing what CassanovaL has learned about the user by analyzing all agents' AutoResearch experiment logs — with a weekly auto-refresh and an on-demand refresh button.

**Architecture:** `tools/intelligence_tools.py` reads all agent `program.md` + `experiment_log.md` files (from `AI Data/<Agent>/`), compiles stats, and calls `mistral-large-latest` to generate a 3–5 paragraph Indonesian synthesis cached for 7 days in `data/intelligence_synthesis.json`. Two FastAPI endpoints expose the cached report and trigger on-demand refresh. The weekly job fires Sundays 08:30 WIB via the existing APScheduler. Alfred's Overview tab (already exists, already renders task stats) gets an `IntelligenceDashboard` component appended below those stats.

**Tech Stack:** Python 3.11, LangChain + `langchain-mistralai`, FastAPI `BackgroundTasks`, APScheduler (already installed), React 18 (browser Babel, no build step), CSS custom properties

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `tools/intelligence_tools.py` | CREATE | Parse experiment files, call Mistral, cache synthesis |
| `tests/test_intelligence_tools.py` | CREATE | Unit tests for parse functions |
| `server.py` | MODIFY | Add 2 endpoints + 1 scheduler job |
| `static/index/icons.jsx` | MODIFY | Add `IcoRefresh` |
| `static/index/data.jsx` | MODIFY | Add `intelligenceAPI`, `refreshIntelligenceAPI` → `window.CLData` |
| `static/index/styles.css` | MODIFY | Add `.intel-*` CSS classes |
| `static/index/views.jsx` | MODIFY | Add `IntelligenceDashboard`, `IntelAgentCard`, mount in Alfred's Overview |

---

## Task 1: `tools/intelligence_tools.py` — Parse functions

**Files:**
- Create: `tools/intelligence_tools.py`
- Create: `tests/test_intelligence_tools.py`

- [ ] **Step 1: Create `tools/intelligence_tools.py` with the agent folder map and two parse functions**

```python
# tools/intelligence_tools.py
from pathlib import Path
import os, json, re
from datetime import datetime, timedelta

# Defined here (not imported from autoresearch_tools) so we can include orwell
# and avoid depending on a private variable in another module.
_AGENT_FOLDER_MAP = {
    "task":        "TaskCore Agent",
    "notes":       "Notes Agent",
    "news":        "Najwa Agent",
    "coding":      "Linus Agent",
    "schedule":    "CalCore Agent",
    "budget":      "Mansa Agent",
    "research":    "Ferry Agent",
    "fitness":     "Lavoiser Agent",
    "journal":     "Dostoyevsky Agent",
    "davinci":     "Da Vinci Agent",
    "orwell":      "Orwell Agent",
    "dataanalyst": "DataAnalyst Agent",
}

_CACHE_FILE = Path("data/intelligence_synthesis.json")
_CACHE_TTL_DAYS = 7


def _get_agent_dir(agent_key: str) -> Path:
    folder = _AGENT_FOLDER_MAP.get(agent_key, f"{agent_key.capitalize()} Agent")
    vault = os.getenv("OBSIDIAN_VAULT_PATH")
    return Path(vault) / folder if vault else Path("AI Data") / folder


def _parse_experiment_log(log_path: Path) -> dict:
    """Count KEEP/DISCARD/INCONCLUSIVE verdicts in experiment_log.md."""
    if not log_path.exists():
        return {"KEEP": 0, "DISCARD": 0, "INCONCLUSIVE": 0, "total": 0}
    text = log_path.read_text(encoding="utf-8")
    counts = {v: text.count(f"**Verdict:** {v}") for v in ["KEEP", "DISCARD", "INCONCLUSIVE"]}
    counts["total"] = sum(counts.values())
    return counts


def _parse_program_md(program_path: Path) -> dict:
    """Extract Current Hypothesis section and updated date from program.md."""
    if not program_path.exists():
        return {"hypothesis": None, "updated": None}
    text = program_path.read_text(encoding="utf-8")
    hypothesis = None
    if "## Current Hypothesis" in text:
        start = text.index("## Current Hypothesis") + len("## Current Hypothesis")
        rest = text[start:].strip()
        end = rest.find("\n##")
        hypothesis = (rest[:end] if end != -1 else rest).strip()
    updated = next(
        (line.split(":", 1)[1].strip() for line in text.split("\n")
         if line.strip().startswith("updated:")),
        None,
    )
    return {"hypothesis": hypothesis, "updated": updated}
```

- [ ] **Step 2: Create `tests/test_intelligence_tools.py` with parse function tests**

```python
# tests/test_intelligence_tools.py
import pytest
from pathlib import Path
import sys, os
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_parse_experiment_log_counts_verdicts(tmp_path):
    log = tmp_path / "experiment_log.md"
    log.write_text(
        "---\nagent: task\n---\n\n"
        "## [2026-05-01 09:00] H-001\n**Verdict:** KEEP\n**Confidence:** HIGH\n\n"
        "## [2026-05-02 10:00] H-002\n**Verdict:** DISCARD\n**Confidence:** MEDIUM\n\n"
        "## [2026-05-03 11:00] H-003\n**Verdict:** KEEP\n**Confidence:** LOW\n\n"
        "## [2026-05-04 12:00] H-004\n**Verdict:** INCONCLUSIVE\n**Confidence:** LOW\n",
        encoding="utf-8",
    )
    from tools.intelligence_tools import _parse_experiment_log
    result = _parse_experiment_log(log)
    assert result == {"KEEP": 2, "DISCARD": 1, "INCONCLUSIVE": 1, "total": 4}


def test_parse_experiment_log_missing_file(tmp_path):
    from tools.intelligence_tools import _parse_experiment_log
    result = _parse_experiment_log(tmp_path / "nonexistent.md")
    assert result == {"KEEP": 0, "DISCARD": 0, "INCONCLUSIVE": 0, "total": 0}


def test_parse_program_md_extracts_hypothesis(tmp_path):
    prog = tmp_path / "program.md"
    prog.write_text(
        "---\nagent: task\nupdated: 2026-05-20\n---\n\n"
        "# Autoresearch Program\n\n"
        "## Current Hypothesis\nUser prefers bullet lists over prose.\n\n"
        "## Metric\nTask acceptance rate.\n",
        encoding="utf-8",
    )
    from tools.intelligence_tools import _parse_program_md
    result = _parse_program_md(prog)
    assert result["hypothesis"] == "User prefers bullet lists over prose."
    assert result["updated"] == "2026-05-20"


def test_parse_program_md_missing_file(tmp_path):
    from tools.intelligence_tools import _parse_program_md
    result = _parse_program_md(tmp_path / "nonexistent.md")
    assert result == {"hypothesis": None, "updated": None}


def test_parse_program_md_no_hypothesis_section(tmp_path):
    prog = tmp_path / "program.md"
    prog.write_text("---\nagent: task\n---\n\n# Autoresearch Program\n\n## Metric\nSomething.\n", encoding="utf-8")
    from tools.intelligence_tools import _parse_program_md
    result = _parse_program_md(prog)
    assert result["hypothesis"] is None
```

- [ ] **Step 3: Run the tests**

```
cd c:\Users\muham\OneDrive\Dokumen\Python\ai_python
$env:PYTHONUTF8=1; python -m pytest tests/test_intelligence_tools.py -v
```

Expected output:
```
PASSED tests/test_intelligence_tools.py::test_parse_experiment_log_counts_verdicts
PASSED tests/test_intelligence_tools.py::test_parse_experiment_log_missing_file
PASSED tests/test_intelligence_tools.py::test_parse_program_md_extracts_hypothesis
PASSED tests/test_intelligence_tools.py::test_parse_program_md_missing_file
PASSED tests/test_intelligence_tools.py::test_parse_program_md_no_hypothesis_section
5 passed
```

- [ ] **Step 4: Commit**

```
git add tools/intelligence_tools.py tests/test_intelligence_tools.py
git commit -m "feat(intelligence): add experiment log + program.md parse functions"
```

---

## Task 2: `get_all_agent_stats` and `generate_intelligence_synthesis`

**Files:**
- Modify: `tools/intelligence_tools.py` (append)
- Modify: `tests/test_intelligence_tools.py` (append)

- [ ] **Step 1: Add `get_all_agent_stats` to `tools/intelligence_tools.py`**

Append to end of `tools/intelligence_tools.py`:

```python
def get_all_agent_stats() -> list[dict]:
    """Read program.md + experiment_log.md for every agent. Returns list of stat dicts."""
    result = []
    for agent_key, folder_name in _AGENT_FOLDER_MAP.items():
        d = _get_agent_dir(agent_key)
        program = _parse_program_md(d / "program.md")
        exps    = _parse_experiment_log(d / "experiment_log.md")
        result.append({
            "agent_key":   agent_key,
            "folder":      folder_name,
            "hypothesis":  program["hypothesis"],
            "updated":     program["updated"],
            "experiments": exps,
        })
    return result
```

- [ ] **Step 2: Add test for `get_all_agent_stats`**

Append to `tests/test_intelligence_tools.py`:

```python
def test_get_all_agent_stats_returns_all_agents():
    from tools.intelligence_tools import get_all_agent_stats, _AGENT_FOLDER_MAP
    stats = get_all_agent_stats()
    assert len(stats) == len(_AGENT_FOLDER_MAP)
    keys = {s["agent_key"] for s in stats}
    assert "task" in keys
    assert "orwell" in keys
    assert "budget" in keys
    for s in stats:
        assert "experiments" in s
        assert "total" in s["experiments"]
```

- [ ] **Step 3: Run tests**

```
$env:PYTHONUTF8=1; python -m pytest tests/test_intelligence_tools.py -v
```

Expected: 6 tests PASSED

- [ ] **Step 4: Add `generate_intelligence_synthesis` to `tools/intelligence_tools.py`**

Append to end of `tools/intelligence_tools.py`:

```python
def generate_intelligence_synthesis(force: bool = False) -> dict:
    """
    Synthesize a learning report via mistral-large-latest.
    Caches to data/intelligence_synthesis.json for 7 days.
    Returns {"synthesis": str, "generated_at": ISO str, "agents": list[dict]}.
    """
    agents = get_all_agent_stats()

    # Return cached version if still fresh
    if not force and _CACHE_FILE.exists():
        try:
            cached = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            if datetime.fromisoformat(cached["generated_at"]) > datetime.now() - timedelta(days=_CACHE_TTL_DAYS):
                cached["agents"] = agents
                return cached
        except Exception:
            pass  # corrupt cache → regenerate

    # Build prompt
    lines = ["Kamu adalah analis sistem AI. Berikut adalah data eksperimen dari semua agent milik user:\n"]
    active_agents = [a for a in agents if a["experiments"]["total"] > 0]
    if not active_agents:
        synthesis = "Belum ada data eksperimen yang cukup. Gunakan CassanovaL lebih sering agar sistem dapat mulai belajar tentang preferensimu."
    else:
        for a in active_agents:
            lines += [
                f"### {a['folder']} ({a['agent_key']})",
                f"Hipotesis saat ini: {a['hypothesis'] or '(belum ada)'}",
                f"Eksperimen: {a['experiments']['KEEP']} KEEP, {a['experiments']['DISCARD']} DISCARD, {a['experiments']['INCONCLUSIVE']} INCONCLUSIVE\n",
            ]
        lines += [
            "\nTulis laporan ringkas dalam Bahasa Indonesia (3–5 paragraf) yang menjawab:",
            "1. Apa yang sudah dipelajari sistem tentang preferensi dan kebiasaan user?",
            "2. Agent mana yang paling aktif belajar, dan mana yang paling sedikit datanya?",
            "3. Pola apa yang muncul lintas agent (misalnya: gaya komunikasi, format respons)?",
            "4. Area konkret mana yang butuh lebih banyak eksperimen agar sistem bisa berkembang?",
        ]
        from langchain_mistralai import ChatMistralAI
        from langchain_core.messages import HumanMessage
        llm = ChatMistralAI(model="mistral-large-latest", temperature=0.3)
        synthesis = llm.invoke([HumanMessage(content="\n".join(lines))]).content

    result_to_cache = {
        "synthesis":    synthesis,
        "generated_at": datetime.now().isoformat(),
    }
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps(result_to_cache, ensure_ascii=False, indent=2), encoding="utf-8")

    return {**result_to_cache, "agents": agents}
```

- [ ] **Step 5: Verify synthesis runs (no API call expected if no experiment data exists)**

```
$env:PYTHONUTF8=1; python -c "
from tools.intelligence_tools import generate_intelligence_synthesis
r = generate_intelligence_synthesis(force=True)
print('Keys:', list(r.keys()))
print('Agents count:', len(r['agents']))
print('Synthesis preview:', r['synthesis'][:200])
"
```

Expected: prints keys `['synthesis', 'generated_at', 'agents']`, agents count = 12, synthesis is non-empty text.

- [ ] **Step 6: Commit**

```
git add tools/intelligence_tools.py tests/test_intelligence_tools.py
git commit -m "feat(intelligence): add agent stats aggregation and Mistral synthesis"
```

---

## Task 3: Server endpoints + scheduler job

**Files:**
- Modify: `server.py`

The existing file already has APScheduler with `_setup_scheduler()` and `_run_morning_brief()`, `_run_weekly_patterns()`, `_run_monthly_budget()` job functions. Add one new job and two endpoints.

- [ ] **Step 1: Add `_run_intelligence_synthesis` job function**

Find the block of `_run_*` job functions in `server.py` (near `_run_weekly_patterns`). Add after `_run_weekly_patterns`:

```python
def _run_intelligence_synthesis():
    """Weekly auto-refresh of the agent intelligence synthesis."""
    logger.info("[Intelligence] Generating weekly synthesis…")
    try:
        from tools.intelligence_tools import generate_intelligence_synthesis
        generate_intelligence_synthesis(force=True)
        logger.info("[Intelligence] Weekly synthesis complete.")
    except Exception as e:
        logger.error(f"[Intelligence] Error: {e}")
```

- [ ] **Step 2: Register the job in `_setup_scheduler()`**

Inside the `_setup_scheduler()` function, after the existing `add_job` calls, add:

```python
    scheduler.add_job(
        _run_intelligence_synthesis, "cron",
        day_of_week="sun", hour=8, minute=30,
        id="intelligence_synthesis", replace_existing=True,
    )
    logger.info("[Scheduler] Intelligence synthesis job registered — fires Sundays at 08:30 WIB")
```

- [ ] **Step 3: Add two new endpoints**

Find the block of Alfred endpoints (`/api/alfred/patterns`, `/api/alfred/contradictions`, etc.) in `server.py`. Append after them:

```python
@app.get("/api/alfred/intelligence")
async def get_intelligence():
    """Return cached intelligence synthesis + per-agent experiment stats."""
    try:
        from tools.intelligence_tools import generate_intelligence_synthesis
        return generate_intelligence_synthesis(force=False)
    except Exception as e:
        logger.error(f"[Intelligence] GET error: {e}")
        return {"synthesis": "", "generated_at": None, "agents": []}


@app.post("/api/alfred/intelligence/refresh", status_code=202)
async def refresh_intelligence(background_tasks: BackgroundTasks):
    """Trigger a fresh Mistral synthesis in the background. Returns 202 immediately."""
    from tools.intelligence_tools import generate_intelligence_synthesis
    background_tasks.add_task(generate_intelligence_synthesis, True)
    return {"status": "generating"}
```

- [ ] **Step 4: Verify server starts and endpoints respond**

```
$env:PYTHONUTF8=1; python server.py
```

In a second terminal:
```
curl http://localhost:8000/api/alfred/intelligence
```
Expected: JSON with keys `synthesis`, `generated_at`, `agents` (list of 12 dicts).

```
curl -X POST http://localhost:8000/api/alfred/intelligence/refresh
```
Expected: `{"status":"generating"}`

- [ ] **Step 5: Commit**

```
git add server.py
git commit -m "feat(intelligence): add /api/alfred/intelligence endpoints + weekly scheduler job"
```

---

## Task 4: `icons.jsx` + `data.jsx` additions

**Files:**
- Modify: `static/index/icons.jsx`
- Modify: `static/index/data.jsx`

- [ ] **Step 1: Add `IcoRefresh` to `icons.jsx`**

In `static/index/icons.jsx`, add before the `window.Icons = {` line (after `IcoMicOff`):

```javascript
const IcoRefresh    = ({size=14})=> <S size={size}><path d="M1 4v6h6"/><path d="M23 20v-6h-6"/><path d="M20.5 9A9 9 0 0 0 5.2 5.2L1 10M23 14l-4.2 4.8A9 9 0 0 1 3.5 15"/></S>;
```

Add `IcoRefresh` to the `window.Icons` export object:

```javascript
window.Icons = {
  IcoSend, IcoSearch, IcoClock, IcoFile, IcoCmd, IcoUsers, IcoX, IcoClip,
  IcoRocket, IcoPanelClose, IcoPanelOpen, IcoSun, IcoMoon, IcoPixel, IcoDownload,
  IcoArrowRight, IcoPlus, IcoUpload, IcoCheck, IcoReceipt, IcoSparkle,
  IcoDashboard, IcoChat, IcoLeaf, IcoFeather, IcoNewspaper, IcoCode,
  IcoCalendar, IcoCoin, IcoHeart, IcoBook, IcoLamp, IcoCandlestick,
  IcoChart, IcoTrend, IcoBell, IcoMic, IcoMicOff, IcoRefresh,
};
```

- [ ] **Step 2: Add API helpers to `data.jsx`**

In `static/index/data.jsx`, add after `const journalDashAPI` line (line 160):

```javascript
const intelligenceAPI        = () => apiFetch('/api/alfred/intelligence');
const refreshIntelligenceAPI = () => fetch('/api/alfred/intelligence/refresh', { method: 'POST' }).then(r => r.json());
```

Add both to the `window.CLData` export (line 214–216 area):

```javascript
window.CLData = {
  AGENTS, AGENT_ORDER, AGENT_CLUSTERS, CLUSTER_ORDER, CHIPS, MOCK,
  SCRAPER_PLATFORMS,
  fmtTime, fmtDate, fmtLongDate, fmtMoney, fmtIssue,
  renderMd,
  chatAPI, tasksAPI, notesAPI, budgetAPI, daFilesAPI,
  uploadDAAPI, receiptAPI, crewKick, crewPoll,
  patternsAPI, contradictionsAPI, fitnessDashAPI, newsFeedAPI, journalDashAPI,
  intelligenceAPI, refreshIntelligenceAPI,
};
```

- [ ] **Step 3: Verify in browser console**

Start server, open `http://localhost:8000`, open DevTools console, run:

```javascript
window.CLData.intelligenceAPI().then(r => console.log(Object.keys(r)))
// Expected: ['synthesis', 'generated_at', 'agents']

window.CLData.refreshIntelligenceAPI().then(r => console.log(r))
// Expected: {status: 'generating'}

console.log(typeof window.Icons.IcoRefresh)
// Expected: 'function'
```

- [ ] **Step 4: Commit**

```
git add static/index/icons.jsx static/index/data.jsx
git commit -m "feat(intelligence): add IcoRefresh icon + intelligence API helpers to window.CLData"
```

---

## Task 5: CSS for the intelligence section

**Files:**
- Modify: `static/index/styles.css`

- [ ] **Step 1: Add intelligence CSS classes at end of `styles.css`**

Append to the very end of `static/index/styles.css`:

```css
/* ── Intelligence Dashboard ───────────────────────────────── */
.intel-section {
  margin-top: 32px;
  padding-top: 28px;
  border-top: 1px solid var(--rule);
}
.intel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.intel-header-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ink-4);
}
.intel-date {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--ink-4);
  margin-left: auto;
}
.intel-refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 9px;
  border-radius: 6px;
  border: 1px solid var(--rule);
  background: transparent;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: var(--ink-3);
  cursor: pointer;
  letter-spacing: 0.04em;
  transition: background 0.15s, color 0.15s;
}
.intel-refresh-btn:hover { background: var(--hover); color: var(--ink); }
.intel-refresh-btn svg  { transition: transform 0.6s ease; }
.intel-refresh-btn.spinning svg { animation: intel-spin 0.8s linear infinite; }
@keyframes intel-spin { to { transform: rotate(360deg); } }

.intel-synthesis {
  font-family: 'Instrument Serif', serif;
  font-size: 17px;
  line-height: 1.75;
  color: var(--ink-2);
  margin-bottom: 24px;
}
.intel-synthesis h2 { font-size: 20px; margin: 20px 0 8px; color: var(--ink); }
.intel-synthesis h3 { font-size: 17px; margin: 16px 0 6px; color: var(--ink); }
.intel-synthesis ul { padding-left: 20px; margin: 8px 0; }
.intel-synthesis li { margin: 4px 0; }
.intel-synthesis p  { margin: 0 0 12px; }

.intel-agents-toggle {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ink-4);
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 14px;
}
.intel-agents-toggle:hover { color: var(--ink-2); }

.intel-agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}

.intel-agent-card {
  background: var(--surface-2);
  border: 1px solid var(--rule-soft);
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.intel-agent-head {
  display: flex;
  align-items: center;
  gap: 6px;
}
.intel-agent-name {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  color: var(--ink);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.intel-agent-hypothesis {
  font-family: 'Instrument Serif', serif;
  font-size: 13px;
  color: var(--ink-3);
  line-height: 1.5;
  margin: 0;
}
.intel-agent-pills {
  display: flex;
  gap: 4px;
  margin-top: 2px;
}

.intel-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.intel-dot--green  { background: #4caf50; }
.intel-dot--yellow { background: #ffc107; }
.intel-dot--red    { background: #ef5350; }
.intel-dot--grey   { background: var(--rule); }

.intel-pill {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 4px;
  letter-spacing: 0.02em;
}
.intel-pill--k { background: rgba(76,175,80,.13);  color: #4caf50; }
.intel-pill--d { background: rgba(239,83,80,.13);  color: #ef5350; }
.intel-pill--i { background: rgba(255,193,7,.13);  color: #cc9900; }

.intel-no-data {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--ink-4);
  padding: 16px 0;
  text-align: center;
}
```

- [ ] **Step 2: Visual check**

Start the server, open Alfred's Overview tab in browser. The new CSS classes won't affect the page yet (components not wired), but verify no CSS syntax errors by checking the browser console — it should be clean.

- [ ] **Step 3: Commit**

```
git add static/index/styles.css
git commit -m "feat(intelligence): add .intel-* CSS classes for dashboard section"
```

---

## Task 6: `IntelAgentCard` and `IntelligenceDashboard` components

**Files:**
- Modify: `static/index/views.jsx`

The `AgentOverview` component lives around line 540 in `views.jsx`. Add two new components directly before it.

- [ ] **Step 1: Add `IntelAgentCard` component to `views.jsx`**

Find the line `/* ── Agent Overview Tab ───────────────────────────────────── */` (around line 540). Insert the following TWO components immediately above that comment:

```javascript
/* ── Intelligence Dashboard (inside Alfred Overview) ─────── */
function IntelAgentCard({ agent }) {
  const { KEEP: k, DISCARD: d, INCONCLUSIVE: i, total } = agent.experiments;
  const dot = total === 0         ? 'grey'
            : k / total >= 0.6   ? 'green'
            : d / total >= 0.6   ? 'red'
            : 'yellow';
  const name = agent.folder.replace(' Agent', '').replace('TaskCore', 'Alfred');
  const hyp  = agent.hypothesis
    ? (agent.hypothesis.length > 95 ? agent.hypothesis.slice(0, 95) + '…' : agent.hypothesis)
    : 'No experiments yet.';
  return (
    <div className="intel-agent-card">
      <div className="intel-agent-head">
        <span className={`intel-dot intel-dot--${dot}`} />
        <span className="intel-agent-name">{name}</span>
      </div>
      <p className="intel-agent-hypothesis">{hyp}</p>
      <div className="intel-agent-pills">
        <span className="intel-pill intel-pill--k">{k}K</span>
        <span className="intel-pill intel-pill--d">{d}D</span>
        <span className="intel-pill intel-pill--i">{i}I</span>
      </div>
    </div>
  );
}

function IntelligenceDashboard() {
  const { intelligenceAPI, refreshIntelligenceAPI, renderMd, fmtDate } = window.CLData;
  const { IcoRefresh } = window.Icons;
  const [intel,     setIntel]     = _useState(null);
  const [loading,   setLoading]   = _useState(true);
  const [spinning,  setSpinning]  = _useState(false);
  const [expanded,  setExpanded]  = _useState(false);

  _useEffect(() => {
    intelligenceAPI()
      .then(setIntel)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleRefresh = async () => {
    setSpinning(true);
    await refreshIntelligenceAPI();
    // Poll until generated_at changes (max 30s)
    const prev = intel?.generated_at;
    for (let i = 0; i < 10; i++) {
      await new Promise(r => setTimeout(r, 3000));
      try {
        const fresh = await intelligenceAPI();
        if (fresh.generated_at !== prev) { setIntel(fresh); break; }
      } catch {}
    }
    setSpinning(false);
  };

  return (
    <div className="intel-section">
      <div className="intel-header">
        <span className="intel-header-label">CassanovaL Intelligence</span>
        {intel?.generated_at && (
          <span className="intel-date">Last analyzed: {fmtDate(intel.generated_at)}</span>
        )}
        <button
          className={`intel-refresh-btn${spinning ? ' spinning' : ''}`}
          onClick={handleRefresh}
          disabled={spinning}
          type="button"
        >
          <IcoRefresh size={12} />
          {spinning ? 'Generating…' : 'Refresh'}
        </button>
      </div>

      {loading && (
        <div>
          <div className="skeleton skeleton-line" style={{width:'90%', marginBottom:10}}/>
          <div className="skeleton skeleton-line" style={{width:'75%', marginBottom:10}}/>
          <div className="skeleton skeleton-line" style={{width:'85%'}}/>
        </div>
      )}

      {!loading && intel?.synthesis && (
        <div
          className="intel-synthesis"
          dangerouslySetInnerHTML={{ __html: renderMd(intel.synthesis) }}
        />
      )}

      {!loading && !intel?.synthesis && (
        <p className="intel-no-data">
          No synthesis yet. Click Refresh or wait for Sunday's auto-run.
        </p>
      )}

      {!loading && intel?.agents?.length > 0 && (
        <>
          <div className="intel-agents-toggle" onClick={() => setExpanded(e => !e)}>
            <span>{expanded ? '▾' : '▸'}</span>
            Per-agent details
          </div>
          {expanded && (
            <div className="intel-agents-grid">
              {intel.agents.map(a => <IntelAgentCard key={a.agent_key} agent={a} />)}
            </div>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Mount `IntelligenceDashboard` inside Alfred's task branch in `AgentOverview`**

In the `AgentOverview` function, find the closing fragment tag of the `agKey === 'task'` branch. It currently ends around line 616–617 as:

```javascript
      {!loading && agKey === 'task' && data && (
        <>
          ...existing stat grid and task list...
        </>
      )}
```

Add `<IntelligenceDashboard />` as the last item inside that fragment, directly before the closing `</>`:

```javascript
      {!loading && agKey === 'task' && data && (
        <>
          <div className="overview-grid">
            {/* ...existing 3 stat cards... */}
          </div>
          <div className="overview-bar-section">
            {/* ...existing next-up task list... */}
          </div>
          <IntelligenceDashboard />
        </>
      )}
```

- [ ] **Step 3: Test in browser**

```
$env:PYTHONUTF8=1; python server.py
```

Open `http://localhost:8000`, navigate to Alfred, click the **Overview** tab.

Expected:
- The existing 3 stat cards (Pending / High Priority / Done Today) appear at top
- Below: "Next up" task list
- Below: a horizontal rule separator and "CASSANOVAL INTELLIGENCE" header with "Refresh" button
- Either skeleton loaders → then synthesis text, or "No synthesis yet" message
- A "▸ Per-agent details" toggle — clicking it expands 12 agent cards in a grid
- Each card shows: colored dot, agent name (uppercase), hypothesis excerpt, K/D/I pills

- [ ] **Step 4: Test the Refresh button**

Click "Refresh" in the intelligence section. Expected:
- Button shows spinner + "Generating…" text
- After 5–10 seconds (Mistral latency), synthesis text updates with a new `generated_at` date

- [ ] **Step 5: Commit**

```
git add static/index/views.jsx
git commit -m "feat(intelligence): add IntelligenceDashboard + IntelAgentCard components to Alfred Overview"
```

---

## Self-Review

**Spec coverage:**
- ✅ `tools/intelligence_tools.py` with `_parse_experiment_log`, `_parse_program_md`, `get_all_agent_stats`, `generate_intelligence_synthesis` — Tasks 1 & 2
- ✅ `data/intelligence_synthesis.json` cache with 7-day TTL — Task 2
- ✅ `GET /api/alfred/intelligence` endpoint — Task 3
- ✅ `POST /api/alfred/intelligence/refresh` (202 async) — Task 3
- ✅ Weekly scheduler job Sundays 08:30 WIB — Task 3
- ✅ `IcoRefresh` icon — Task 4
- ✅ `intelligenceAPI`, `refreshIntelligenceAPI` in `window.CLData` — Task 4
- ✅ `.intel-*` CSS classes — Task 5
- ✅ `IntelAgentCard` with traffic-light dot + K/D/I pills — Task 6
- ✅ `IntelligenceDashboard` with synthesis + refresh button + collapsible agent cards — Task 6
- ✅ Alfred's Overview tab: task stats (already existed) + `IntelligenceDashboard` below — Task 6
- ✅ Orwell included in `_AGENT_FOLDER_MAP` — Task 1
- ✅ `task/status === 'done'` filter for ring (spec clarification) — already handled by existing code

**Placeholder check:** No TBDs, TODOs, or incomplete steps found.

**Type consistency:**
- `generate_intelligence_synthesis` returns `dict` with keys `synthesis`, `generated_at`, `agents` in all code paths ✅
- `_parse_experiment_log` always returns `{"KEEP", "DISCARD", "INCONCLUSIVE", "total"}` ✅
- `IntelAgentCard` expects `agent.experiments.{KEEP, DISCARD, INCONCLUSIVE, total}` — matches `_parse_experiment_log` output ✅
- `intelligenceAPI()` returns same shape as `generate_intelligence_synthesis()` ✅
- `fmtDate` is already in `window.CLData` (confirmed in `data.jsx` line 213) ✅
- `renderMd` is already in `window.CLData` (confirmed in `data.jsx` line 213) ✅
