# Frontend Upgrade — Najwa News Feed, Mansa Budget Charts, DataAnalyst Excel

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live categorized NewsAPI feed to Najwa's Overview tab, redesign Mansa's budget panel with donut + bar charts, and add Excel output to the DataAnalyst crew — all with working frontend.

**Architecture:** Three independent feature areas sharing the same FastAPI server and JSX frontend. Backend endpoints serve data; SVG charts are rendered in pure JSX (no charting library needed); the DataAnalyst crew gains an openpyxl Excel tool run in parallel with the existing Python viz tool.

**Tech Stack:** FastAPI, Python 3.x, NewsAPI (`requests`), openpyxl, React 18 (CDN, no build step), SVG charts inline JSX.

---

## File Map

| File | Change |
|---|---|
| `server.py` | + `GET /api/news/feed`, + `GET /api/budget/analytics`, collect `.xlsx` in crew outputs |
| `tools/data_tools.py` | + `generate_excel_report` tool |
| `crewai_agents.py` | + `ExcelReportCrewTool`, update viz agent + viz task |
| `static/index/data.jsx` | + `newsFeedAPI`, `budgetAnalyticsAPI` helpers; export in `window.CLData` |
| `static/index/styles.css` | + news feed styles, budget chart styles |
| `static/index/views.jsx` | + `NewsFeedView` component, update `RightPanel` budget section with charts |
| `static/index/app.jsx` | Wire `NewsFeedView` into tab routing for `agKey === 'news'`; destructure it |
| `static/index/overlays.jsx` | Update `ResultModal` to show Excel download button |

---

## Task 1: Backend — `/api/news/feed` endpoint

**Files:**
- Modify: `server.py` (after `get_budget_summary`, around line 248)

- [ ] **Step 1: Add the NewsAPI endpoint to server.py**

Add this block after the `get_budget_summary` function:

```python
# ─── News Feed Endpoint ───────────────────────────────────────────────────────

_NEWS_CAT_MAP = {
    "technology": {"endpoint": "top-headlines", "category": "technology"},
    "finance":    {"endpoint": "top-headlines", "category": "business"},
    "politics":   {"endpoint": "everything",    "q": "politics"},
    "world":      {"endpoint": "top-headlines", "category": "general"},
    "science":    {"endpoint": "top-headlines", "category": "science"},
    "general":    {"endpoint": "top-headlines", "category": "general"},
}

import requests as _requests

@app.get("/api/news/feed")
async def news_feed(category: str = "general", q: str = "", page: int = 1):
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="NEWS_API_KEY not set in .env")

    mapping = _NEWS_CAT_MAP.get(category, _NEWS_CAT_MAP["general"])
    endpoint = mapping["endpoint"]

    params = {
        "apiKey":   api_key,
        "language": "en",
        "pageSize": 20,
        "page":     page,
        "sortBy":   "publishedAt",
    }
    if "category" in mapping:
        params["category"] = mapping["category"]
    if "q" in mapping:
        params["q"] = mapping["q"]
    if q:
        params["q"] = q  # user query overrides the default

    try:
        resp = _requests.get(
            f"https://newsapi.org/v2/{endpoint}",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
    except _requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"NewsAPI error: {e}")

    data = resp.json()
    articles = [
        {
            "title":        a["title"],
            "source":       a["source"]["name"],
            "url":          a["url"],
            "published_at": a["publishedAt"],
            "description":  a.get("description") or "",
            "category":     category,
        }
        for a in data.get("articles", [])
        if a.get("title") and "[Removed]" not in a.get("title", "")
    ]
    return {"articles": articles, "total": data.get("totalResults", 0), "category": category}
```

- [ ] **Step 2: Start server and test the endpoint**

```bash
# Windows
$env:PYTHONUTF8=1; python server.py
```

In another terminal:
```bash
curl "http://localhost:8000/api/news/feed?category=technology"
```

Expected: JSON with `articles` array containing `title`, `source`, `url`, `published_at`, `description`, `category` fields.

- [ ] **Step 3: Commit**

```bash
git add server.py
git commit -m "feat(server): add GET /api/news/feed endpoint via NewsAPI"
```

---

## Task 2: Backend — `/api/budget/analytics` endpoint

**Files:**
- Modify: `server.py` (after `get_budget_summary`)

- [ ] **Step 1: Add the budget analytics endpoint**

Add this block immediately after `get_budget_summary`:

```python
@app.get("/api/budget/analytics")
async def budget_analytics():
    try:
        data = json.loads(Path("data/budget.json").read_text(encoding="utf-8"))
    except Exception:
        return {"category_totals": {}, "monthly_trend": []}

    from collections import defaultdict
    cat_totals: dict = defaultdict(float)
    for t in data:
        if t.get("type") == "expense":
            cat_totals[t.get("category", "other")] += float(t.get("amount", 0))

    # 5-month rolling window (correct month arithmetic — no timedelta approximation)
    months = []
    now = datetime.now()
    for i in range(4, -1, -1):
        month_num = (now.month - 1 - i) % 12 + 1
        year      = now.year + ((now.month - 1 - i) // 12)
        ym        = f"{year}-{month_num:02d}"
        label     = datetime(year, month_num, 1).strftime("%b")
        monthly   = [t for t in data if t.get("date", "").startswith(ym)]
        months.append({
            "label":   label,
            "income":  sum(float(t.get("amount", 0)) for t in monthly if t.get("type") == "income"),
            "expense": sum(float(t.get("amount", 0)) for t in monthly if t.get("type") == "expense"),
        })

    return {"category_totals": dict(cat_totals), "monthly_trend": months}
```

- [ ] **Step 2: Test the endpoint**

```bash
curl "http://localhost:8000/api/budget/analytics"
```

Expected: JSON with `category_totals` (dict of category → float) and `monthly_trend` (5-element list, each with `label`, `income`, `expense`).

- [ ] **Step 3: Commit**

```bash
git add server.py
git commit -m "feat(server): add GET /api/budget/analytics with category + monthly trend"
```

---

## Task 3: Backend — `generate_excel_report` tool

**Files:**
- Modify: `tools/data_tools.py` (append after the `generate_viz_code` tool)

- [ ] **Step 1: Add generate_excel_report to data_tools.py**

Append this after the existing `generate_viz_code` tool:

```python
@tool
def generate_excel_report(filename: str = "") -> str:
    """Generate an Excel (.xlsx) report with a Summary sheet, Data sheet, Bar Chart sheet,
    and Distribution (Pie) chart sheet. Input: optional output filename."""
    err = _need_df()
    if err:
        return err
    try:
        import openpyxl
        from openpyxl.chart import BarChart, PieChart, Reference
        from openpyxl.utils.dataframe import dataframe_to_rows
    except ImportError:
        return "Error: openpyxl not installed. Run: pip install openpyxl"

    df = _session["df"]
    src = Path(_session.get("file_path") or "dataset.csv")
    out_name = filename.strip() or (src.stem + "_report.xlsx")
    if not out_name.endswith(".xlsx"):
        out_name += ".xlsx"
    out_path = _data_dir() / out_name

    wb = openpyxl.Workbook()

    # ── Sheet 1: Summary ──────────────────────────────────────
    ws_sum = wb.active
    ws_sum.title = "Summary"
    for row_data in [
        ["Dataset Summary", ""],
        ["Rows",             len(df)],
        ["Columns",          len(df.columns)],
        ["Missing values",   int(df.isnull().sum().sum())],
        ["Duplicates",       int(df.duplicated().sum())],
        [],
        ["Descriptive Statistics"],
    ]:
        ws_sum.append(row_data)

    desc = df.describe().reset_index()
    for row in dataframe_to_rows(desc, index=False, header=True):
        ws_sum.append(list(row))

    # ── Sheet 2: Cleaned Data ─────────────────────────────────
    ws_data = wb.create_sheet("Data")
    for row in dataframe_to_rows(df, index=False, header=True):
        ws_data.append(list(row))

    # ── Sheet 3: Bar Chart (first numeric column, top 10 rows) ─
    num_cols = df.select_dtypes(include="number").columns.tolist()
    if num_cols:
        ws_bar = wb.create_sheet("Bar Chart")
        col_name = num_cols[0]
        ws_bar.append(["Index", col_name])
        for i, val in enumerate(df[col_name].head(10).tolist(), start=1):
            ws_bar.append([i, float(val) if val == val else 0])

        chart = BarChart()
        chart.title = f"Top 10 — {col_name}"
        chart.y_axis.title = col_name
        chart.x_axis.title = "Row"
        data_ref = Reference(ws_bar, min_col=2, min_row=1, max_row=11)
        chart.add_data(data_ref, titles_from_data=True)
        ws_bar.add_chart(chart, "D2")

    # ── Sheet 4: Distribution Pie (first categorical column) ──
    cat_cols = df.select_dtypes(include="object").columns.tolist()
    if cat_cols:
        ws_pie = wb.create_sheet("Distribution")
        cat_col = cat_cols[0]
        vc = df[cat_col].value_counts().head(8)
        ws_pie.append([cat_col, "Count"])
        for label, count in vc.items():
            ws_pie.append([str(label), int(count)])

        pie = PieChart()
        pie.title = f"Distribution — {cat_col}"
        labels   = Reference(ws_pie, min_col=1, min_row=2, max_row=len(vc) + 1)
        data_ref = Reference(ws_pie, min_col=2, min_row=1, max_row=len(vc) + 1)
        pie.add_data(data_ref, titles_from_data=True)
        pie.set_categories(labels)
        ws_pie.add_chart(pie, "D2")

    wb.save(out_path)
    sheets = ["Summary", "Data"]
    if num_cols: sheets.append("Bar Chart")
    if cat_cols: sheets.append("Distribution")
    return (
        f"Excel report saved: {out_path}\n"
        f"Sheets: {', '.join(sheets)}\n"
        f"Open with Excel or Google Sheets.\n"
        f"Download: /api/dataanalyst/download/{out_name}"
    )
```

- [ ] **Step 2: Commit**

```bash
git add tools/data_tools.py
git commit -m "feat(data_tools): add generate_excel_report tool (openpyxl, 4 sheets)"
```

---

## Task 4: DataAnalyst crew — Excel integration

**Files:**
- Modify: `crewai_agents.py` (viz agent, viz task, ExcelReportCrewTool)
- Modify: `server.py` (collect .xlsx in crew outputs)

- [ ] **Step 1: Add ExcelReportCrewTool to crewai_agents.py**

After the `VizGeneratorCrewTool` class (around line 764), add:

```python
class ExcelReportCrewTool(BaseTool):
    """Generate an Excel report (.xlsx) with data sheets and embedded charts."""
    name: str = "generate_excel_report"
    description: str = (
        "Generate an Excel (.xlsx) report for the loaded dataset. "
        "Creates: Summary stats sheet, Data sheet, Bar Chart sheet, Distribution (Pie) sheet. "
        "Input: any string (ignored — works on the in-memory dataset)."
    )

    def _run(self, query: str = "") -> str:
        from tools.data_tools import generate_excel_report
        try:
            return generate_excel_report.invoke({"filename": ""})
        except Exception as exc:
            return f"Error generating Excel report: {exc}"


_excel_tool = ExcelReportCrewTool()
```

- [ ] **Step 2: Update make_viz_agent to include Excel tool**

Find `make_viz_agent()` (around line 803) and change its `tools` line:

```python
def make_viz_agent() -> Agent:
    """Agent 3 — generates Python viz code AND Excel report."""
    return Agent(
        llm=llm_small,
        function_calling_llm=llm_large,
        role="Data Visualization Engineer",
        goal="Generate production-quality Python visualization code AND an Excel report for the dataset",
        backstory=(
            "You are a Python visualization expert who turns raw numbers into compelling charts. "
            "You write clean matplotlib + seaborn code AND produce Excel reports stakeholders can open directly."
        ),
        tools=[_viz_tool, _excel_tool],   # <-- add _excel_tool here
        allow_delegation=False,
        verbose=True,
        max_iter=6,   # increased from 4 — two tools to call
    )
```

- [ ] **Step 3: Update make_viz_task description**

Find `make_viz_task()` (around line 863) and replace its `description` string:

```python
def make_viz_task(agent: Agent, stats_task: Task) -> Task:
    return Task(
        description=(
            "The dataset is cleaned and analyzed. Run BOTH tools in order:\n\n"
            "STEP 1 — Python visualization:\n"
            "Call `generate_visualization_code('')` to create a full visualization script.\n"
            "The tool generates: correlation heatmap, feature distributions, scatter matrix, bar chart.\n\n"
            "STEP 2 — Excel report:\n"
            "Call `generate_excel_report('')` to create an .xlsx file with:\n"
            "  - Summary sheet (row count, missing values, descriptive stats)\n"
            "  - Data sheet (full cleaned dataset)\n"
            "  - Bar Chart sheet (top 10 rows of first numeric column)\n"
            "  - Distribution sheet (pie chart of first categorical column)\n\n"
            "After both tools run, report:\n"
            "1. What each Python figure shows and how to run it (`python visualization.py`)\n"
            "2. The Excel file path and how to open it\n"
            "3. Packages needed: `pip install matplotlib seaborn pandas openpyxl`"
        ),
        expected_output=(
            "Description of Python charts + run instructions, and Excel file path + open instructions."
        ),
        agent=agent,
        context=[stats_task],
        output_file="task3_visualization.txt",
    )
```

- [ ] **Step 4: Collect .xlsx outputs in server.py**

In `_run_crew_background`, find the block that collects `stats_report.md` and `visualization.py` (around line 300). Add xlsx collection right after:

```python
            # Existing: stats_report.md + visualization.py
            for rel in ("stats_report.md", "visualization.py"):
                fp = da_dir / rel
                if fp.exists():
                    outputs[rel] = fp.read_text(encoding="utf-8")
            # New: collect any *_report.xlsx files
            for xlsx_file in da_dir.glob("*_report.xlsx"):
                outputs[xlsx_file.name] = (
                    f"✅ Excel report saved:\n{xlsx_file}\n\n"
                    f"Sheets: Summary, Data, Bar Chart, Distribution\n"
                    f"Download: /api/dataanalyst/download/{xlsx_file.name}"
                )
```

- [ ] **Step 5: Commit**

```bash
git add crewai_agents.py server.py
git commit -m "feat(crew): add Excel report tool to DataAnalyst viz agent"
```

---

## Task 5: Frontend — API helpers in data.jsx

**Files:**
- Modify: `static/index/data.jsx`

- [ ] **Step 1: Add two API helpers**

After the `crewPoll` line (line 129), add:

```js
const newsFeedAPI       = (category = 'general', q = '') =>
  apiFetch(`/api/news/feed?category=${encodeURIComponent(category)}&q=${encodeURIComponent(q)}`);
const budgetAnalyticsAPI = () => apiFetch('/api/budget/analytics');
```

- [ ] **Step 2: Export the new helpers in window.CLData**

Find the `window.CLData = {` block (line 163) and add both helpers:

```js
window.CLData = {
  AGENTS, AGENT_ORDER, CHIPS, MOCK,
  fmtTime, fmtDate, fmtLongDate, fmtMoney, fmtIssue,
  renderMd,
  chatAPI, tasksAPI, notesAPI, budgetAPI, daFilesAPI,
  uploadDAAPI, receiptAPI, crewKick, crewPoll,
  newsFeedAPI, budgetAnalyticsAPI,   // <-- add these
};
```

- [ ] **Step 3: Commit**

```bash
git add static/index/data.jsx
git commit -m "feat(frontend): add newsFeedAPI and budgetAnalyticsAPI helpers"
```

---

## Task 6: Frontend — CSS styles for news feed and budget charts

**Files:**
- Modify: `static/index/styles.css` (append at the end)

- [ ] **Step 1: Append new styles to styles.css**

Add the following block at the very end of `styles.css`:

```css
/* ── News Feed View ─────────────────────────────────────────── */
.news-feed-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.news-cat-tabs {
  display: flex;
  gap: 6px;
  padding: 10px 24px;
  border-bottom: 1px solid var(--rule);
  flex-wrap: wrap;
  align-items: center;
  flex-shrink: 0;
  background: var(--paper);
}

.news-cat-tab {
  font-family: 'Departure Mono', monospace;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 4px 12px;
  border: 1px solid var(--rule);
  border-radius: 2px;
  background: transparent;
  color: var(--ink-4);
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}

.news-cat-tab:hover {
  color: var(--ink-2);
  border-color: var(--ink-3);
}

.news-cat-tab.active {
  color: var(--tab-color, var(--agent-hue));
  border-color: var(--tab-color, var(--agent-hue));
  background: color-mix(in srgb, var(--tab-color, var(--agent-hue)) 8%, transparent);
}

.news-cat-tab.news-refresh {
  margin-left: auto;
  font-size: 14px;
  padding: 2px 10px;
}

.news-split-body {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.news-list-pane {
  flex: 1.3;
  border-right: 1px solid var(--rule);
  overflow-y: auto;
}

.news-item {
  padding: 12px 20px;
  border-bottom: 1px solid var(--rule);
  cursor: pointer;
  transition: background 0.1s;
}

.news-item:hover {
  background: color-mix(in srgb, var(--ink-1) 4%, transparent);
}

.news-item-source {
  font-family: 'Departure Mono', monospace;
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}

.news-item-headline {
  font-family: 'Instrument Serif', serif;
  font-size: 14px;
  color: var(--ink-1);
  line-height: 1.4;
  margin-bottom: 4px;
}

.news-item-meta {
  font-family: 'Departure Mono', monospace;
  font-size: 9px;
  color: var(--ink-4);
}

.news-loading {
  padding: 32px 20px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.news-empty {
  padding: 32px 20px;
  color: var(--ink-3);
  font-style: italic;
  font-family: 'Instrument Serif', serif;
  font-size: 16px;
}

.news-chat-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.news-chat-head {
  padding: 10px 16px;
  font-size: 9px;
  color: var(--ink-4);
  border-bottom: 1px solid var(--rule);
  flex-shrink: 0;
  background: var(--paper);
}

.news-chat-msgs {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  min-height: 0;
}

.news-chat-empty {
  color: var(--ink-3);
  font-style: italic;
  font-family: 'Instrument Serif', serif;
  font-size: 14px;
  line-height: 1.6;
}

.news-chat-input-row {
  display: flex;
  gap: 6px;
  align-items: flex-end;
  padding: 10px 12px;
  border-top: 1px solid var(--rule);
  flex-shrink: 0;
  background: var(--paper);
}

/* ── Budget Charts ──────────────────────────────────────────── */
.budget-chart-row {
  display: flex;
  border-bottom: 1px solid var(--rule);
}

.budget-chart-box {
  flex: 1;
  padding: 10px 14px;
}

.budget-chart-box + .budget-chart-box {
  border-left: 1px solid var(--rule);
}

.budget-chart-label {
  font-family: 'Departure Mono', monospace;
  font-size: 8px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ink-4);
  margin-bottom: 8px;
}
```

- [ ] **Step 2: Commit**

```bash
git add static/index/styles.css
git commit -m "feat(styles): add news feed and budget chart CSS"
```

---

## Task 7: Frontend — NewsFeedView component (views.jsx)

**Files:**
- Modify: `static/index/views.jsx` (add before the `window.CLViews` export line)

- [ ] **Step 1: Add NewsFeedView component to views.jsx**

Insert the following before the final `window.CLViews = ...` line:

```jsx
/* ── News Feed View ───────────────────────────────────────────── */
function NewsFeedView({ agKey, messages, loading, onSend }) {
  const { AGENTS, newsFeedAPI, fmtTime, renderMd } = window.CLData;
  const ag = AGENTS[agKey];

  const CATEGORIES = ['all', 'technology', 'finance', 'politics', 'world', 'science'];
  const CAT_COLORS = {
    all:        'var(--ink-3)',
    technology: 'var(--hue-linus)',
    finance:    'var(--hue-mansa)',
    politics:   'var(--hue-lavoiser)',
    world:      'var(--ink-2)',
    science:    'var(--hue-cicero)',
  };

  const [activeCategory, setActiveCategory] = _useState('all');
  const [articles, setArticles]             = _useState([]);
  const [feedLoading, setFeedLoading]       = _useState(false);
  const [val, setVal]   = _useState('');
  const endRef = _useRef(null);
  const taRef  = _useRef(null);

  const fetchFeed = _useCallback(async (cat) => {
    setFeedLoading(true);
    try {
      const d = await newsFeedAPI(cat === 'all' ? 'general' : cat);
      setArticles(d.articles || []);
    } catch { setArticles([]); }
    setFeedLoading(false);
  }, []);

  _useEffect(() => { fetchFeed(activeCategory); }, [activeCategory, fetchFeed]);
  _useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, loading]);

  const send = _useCallback(() => {
    const t = val.trim(); if (!t || loading) return;
    setVal(''); if (taRef.current) taRef.current.style.height = 'auto';
    onSend(t);
  }, [val, loading, onSend]);

  const onKey   = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } };
  const onInput = e => {
    setVal(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  };

  const relTime = iso => {
    if (!iso) return '';
    const diff = Date.now() - new Date(iso).getTime();
    const h = Math.floor(diff / 3600000);
    if (h < 1) return `${Math.max(1, Math.floor(diff / 60000))}m ago`;
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  };

  const firstName = ag.name.split(' ')[0];

  return (
    <div className="news-feed-view" style={{ '--agent-hue': ag.hue }}>
      <div className="news-cat-tabs">
        {CATEGORIES.map(cat => (
          <button key={cat}
            className={`news-cat-tab${activeCategory === cat ? ' active' : ''}`}
            style={activeCategory === cat ? { '--tab-color': CAT_COLORS[cat] } : {}}
            onClick={() => setActiveCategory(cat)}>
            {cat.charAt(0).toUpperCase() + cat.slice(1)}
          </button>
        ))}
        <button className="news-cat-tab news-refresh"
          onClick={() => fetchFeed(activeCategory)} title="Refresh feed">
          ↻
        </button>
      </div>

      <div className="news-split-body">
        {/* Left — article list */}
        <div className="news-list-pane scroll">
          {feedLoading ? (
            <div className="news-loading">
              <span className="spinner"/>
              <span style={{ color: 'var(--ink-3)', fontStyle: 'italic', fontFamily: "'Instrument Serif', serif", fontSize: 15 }}>
                Pulling the wires…
              </span>
            </div>
          ) : articles.length === 0 ? (
            <div className="news-empty">No stories found for this category.</div>
          ) : (
            articles.map((a, i) => (
              <div key={i} className="news-item"
                onClick={() => setVal(`Tell me more about: "${a.title}"`)}>
                <div className="news-item-source"
                  style={{ color: CAT_COLORS[a.category] || 'var(--ink-3)' }}>
                  {a.source} · {a.category}
                </div>
                <div className="news-item-headline">{a.title}</div>
                <div className="news-item-meta">{relTime(a.published_at)}</div>
              </div>
            ))
          )}
        </div>

        {/* Right — chat pane */}
        <div className="news-chat-pane">
          <div className="news-chat-head small-caps">Ask {firstName}</div>
          <div className="news-chat-msgs scroll">
            {messages.length === 0 ? (
              <div className="news-chat-empty">
                Click any headline to ask about it, or type a question below.
              </div>
            ) : (
              messages.map((m, i) => {
                const isUser = m.role === 'user';
                return (
                  <article key={i} className={`msg ${isUser ? 'user' : 'agent'}`}>
                    <div className="msg-head">
                      <span className="msg-author">{isUser ? 'You' : firstName}</span>
                      <span className="msg-role">{isUser ? 'Correspondent' : ag.sub}</span>
                      <span className="msg-time">{m.ts ? fmtTime(m.ts) : ''}</span>
                    </div>
                    <div className="msg-body"
                      dangerouslySetInnerHTML={{ __html: `<p>${renderMd(m.content)}</p>` }}/>
                  </article>
                );
              })
            )}
            {loading && (
              <div className="typing">
                <div className="typing-dots">
                  <div className="typing-dot"/><div className="typing-dot"/><div className="typing-dot"/>
                </div>
                <span style={{ fontStyle: 'italic', fontSize: 13, color: 'var(--ink-3)' }}>
                  {firstName} is composing…
                </span>
              </div>
            )}
            <div ref={endRef}/>
          </div>
          <div className="news-chat-input-row">
            <textarea ref={taRef} className="composer-input" rows="1"
              placeholder={`Ask ${firstName}…`}
              value={val} onChange={onInput} onKeyDown={onKey}
              style={{ fontSize: 13 }}/>
            <button className="composer-btn composer-send"
              onClick={send} disabled={!val.trim() || loading}>
              {loading ? <span className="spinner"/> : '→'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add NewsFeedView to the exports**

Change the final export line from:
```js
window.CLViews = { Sidebar, Masthead, ChatView, DashboardView, RightPanel };
```
to:
```js
window.CLViews = { Sidebar, Masthead, ChatView, DashboardView, RightPanel, NewsFeedView };
```

- [ ] **Step 3: Commit**

```bash
git add static/index/views.jsx
git commit -m "feat(views): add NewsFeedView component for Najwa Overview tab"
```

---

## Task 8: Frontend — Mansa budget panel charts (views.jsx)

**Files:**
- Modify: `static/index/views.jsx` — `RightPanel` component (budget section, lines 399–463)

- [ ] **Step 1: Add BudgetDonut and BudgetBarChart sub-components**

Insert these two components directly before the `RightPanel` function definition:

```jsx
/* ── Budget Donut Chart ─────────────────────────────────────── */
function BudgetDonut({ categoryTotals }) {
  const { fmtMoney } = window.CLData;
  const total = Object.values(categoryTotals).reduce((a, b) => a + b, 0);
  if (total === 0) return (
    <div style={{ color: 'var(--ink-4)', fontSize: 11, fontStyle: 'italic' }}>No expense data</div>
  );

  const COLORS = [
    'var(--hue-mansa)', 'var(--hue-linus)', 'var(--hue-miyamoto)',
    'var(--hue-lavoiser)', 'var(--ink-3)',
  ];
  const entries = Object.entries(categoryTotals).sort((a, b) => b[1] - a[1]).slice(0, 5);

  let cumAngle = -Math.PI / 2;
  const segs = entries.map(([cat, amt], i) => {
    const frac  = amt / total;
    const angle = frac * 2 * Math.PI;
    const x1 = 28 + 24 * Math.cos(cumAngle);
    const y1 = 28 + 24 * Math.sin(cumAngle);
    cumAngle += angle;
    const x2    = 28 + 24 * Math.cos(cumAngle);
    const y2    = 28 + 24 * Math.sin(cumAngle);
    const large = angle > Math.PI ? 1 : 0;
    return { cat, amt, frac, color: COLORS[i], x1, y1, x2, y2, large };
  });

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <svg width="56" height="56" viewBox="0 0 56 56" style={{ flexShrink: 0 }}>
        {segs.map((s, i) => (
          <path key={i}
            d={`M28,28 L${s.x1},${s.y1} A24,24 0 ${s.large},1 ${s.x2},${s.y2} Z`}
            fill={s.color} opacity="0.9"/>
        ))}
        <circle cx="28" cy="28" r="13" fill="var(--paper)"/>
        <text x="28" y="32" textAnchor="middle" fill="var(--ink-3)"
          fontSize="7" fontFamily="monospace">{fmtMoney(total)}</text>
      </svg>
      <div style={{ flex: 1 }}>
        {segs.map((s, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 3 }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: s.color, display: 'inline-block', flexShrink: 0,
            }}/>
            <span style={{
              fontSize: 9, color: 'var(--ink-3)',
              textTransform: 'capitalize', flex: 1,
            }}>{s.cat}</span>
            <span style={{ fontSize: 9, color: 'var(--ink-2)', fontFamily: 'monospace' }}>
              {Math.round(s.frac * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Budget Bar Chart ───────────────────────────────────────── */
function BudgetBarChart({ monthlyTrend }) {
  if (!monthlyTrend || monthlyTrend.length === 0) return null;
  const maxVal = Math.max(...monthlyTrend.flatMap(m => [m.income, m.expense]), 1);
  const H = 48;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: H, borderBottom: '1px solid var(--rule)' }}>
        {monthlyTrend.map((m, i) => (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
            <div style={{
              width: '100%',
              height: Math.max(2, Math.round((m.income / maxVal) * H)) + 'px',
              background: 'var(--hue-miyamoto)', opacity: 0.6,
              borderRadius: '2px 2px 0 0',
            }}/>
            <div style={{
              width: '100%',
              height: Math.max(2, Math.round((m.expense / maxVal) * H)) + 'px',
              background: 'var(--hue-lavoiser)',
              borderRadius: '2px 2px 0 0',
            }}/>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
        {monthlyTrend.map((m, i) => (
          <div key={i} style={{ flex: 1, textAlign: 'center', fontSize: 7, color: 'var(--ink-4)' }}>{m.label}</div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
          <span style={{ width: 7, height: 7, background: 'var(--hue-miyamoto)', opacity: 0.6, borderRadius: 1, display: 'inline-block' }}/>
          <span style={{ fontSize: 8, color: 'var(--ink-4)' }}>Income</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
          <span style={{ width: 7, height: 7, background: 'var(--hue-lavoiser)', borderRadius: 1, display: 'inline-block' }}/>
          <span style={{ fontSize: 8, color: 'var(--ink-4)' }}>Expense</span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Update the RightPanel budget section**

Find the budget panel block inside `RightPanel` (starts with `if (agKey === 'budget') return (`).

Replace the entire `panel-figure` div and everything up to (but not including) the Scan Receipt section with this:

Replace this block (lines ~407–420):
```jsx
        <div className="panel-figure">
          <div className="panel-figure-value"><span className="unit">Rp</span>{fmtMoney(dash.budget?.balance)}</div>
          <div className="panel-figure-label small-caps">Available Balance</div>
          <div className="panel-figure-grid">
            <div>
              <div className="panel-mini-label small-caps">Income</div>
              <div className="panel-mini-value" style={{color:'var(--hue-miyamoto)'}}>+{fmtMoney(dash.budget?.monthly_income)}</div>
            </div>
            <div>
              <div className="panel-mini-label small-caps">Expense</div>
              <div className="panel-mini-value" style={{color:'var(--hue-lavoiser)'}}>−{fmtMoney(dash.budget?.monthly_expense)}</div>
            </div>
          </div>
        </div>
```

With this (also adds analytics state at the top of the budget panel):

First, add state and effect at the top of `RightPanel` (after `const [daFiles, setDAFiles] = _useState([]);`):

```jsx
  const [analytics, setAnalytics] = _useState({ category_totals: {}, monthly_trend: [] });

  _useEffect(() => {
    if (agKey === 'budget') {
      const { budgetAnalyticsAPI } = window.CLData;
      budgetAnalyticsAPI().then(d => setAnalytics(d)).catch(() => {});
    }
  }, [agKey]);
```

Then replace the `panel-figure` block with:

```jsx
        {/* Balance header */}
        <div className="panel-figure" style={{ paddingBottom: 10 }}>
          <div className="panel-figure-value"><span className="unit">Rp</span>{fmtMoney(dash.budget?.balance)}</div>
          <div className="panel-figure-label small-caps">Available Balance</div>
          <div className="panel-figure-grid">
            <div>
              <div className="panel-mini-label small-caps">Income</div>
              <div className="panel-mini-value" style={{ color: 'var(--hue-miyamoto)' }}>+{fmtMoney(dash.budget?.monthly_income)}</div>
            </div>
            <div>
              <div className="panel-mini-label small-caps">Expense</div>
              <div className="panel-mini-value" style={{ color: 'var(--hue-lavoiser)' }}>−{fmtMoney(dash.budget?.monthly_expense)}</div>
            </div>
          </div>
        </div>

        {/* Charts row */}
        <div className="budget-chart-row">
          <div className="budget-chart-box">
            <div className="budget-chart-label">By Category</div>
            <BudgetDonut categoryTotals={analytics.category_totals}/>
          </div>
          <div className="budget-chart-box">
            <div className="budget-chart-label">Monthly Trend</div>
            <BudgetBarChart monthlyTrend={analytics.monthly_trend}/>
          </div>
        </div>
```

- [ ] **Step 3: Commit**

```bash
git add static/index/views.jsx
git commit -m "feat(views): add BudgetDonut and BudgetBarChart to Mansa right panel"
```

---

## Task 9: Frontend — ResultModal Excel download (overlays.jsx)

**Files:**
- Modify: `static/index/overlays.jsx` — `ResultModal` component (around line 322)

- [ ] **Step 1: Add Excel detection helpers and update the result body render**

Find the `ResultModal` function. After the `const content = outputs[activeFile] || '';` line, add:

```jsx
  const isExcelOutput = content.startsWith('✅ Excel report saved:');
  const excelDownloadUrl = (() => {
    const m = content.match(/Download: (\/api\/dataanalyst\/download\/[^\n]+)/);
    return m ? m[1].trim() : null;
  })();
```

Then find the result body render block (around line 360):
```jsx
          <div className="result-body scroll">
            {mode === 'rendered'
              ? <div className="result-article" dangerouslySetInnerHTML={{__html: `<p>${renderMd(content)}</p>`}}/>
              : <pre className="result-raw">{content}</pre>}
          </div>
```

Replace it with:

```jsx
          <div className="result-body scroll">
            {isExcelOutput ? (
              <div style={{ padding: '40px 32px', textAlign: 'center' }}>
                <div style={{ fontFamily: "'Instrument Serif', serif", fontSize: 24, marginBottom: 12, color: 'var(--ink-1)' }}>
                  Excel Report Ready
                </div>
                <div style={{ color: 'var(--ink-3)', fontSize: 14, marginBottom: 8, fontStyle: 'italic' }}>
                  {content.split('\n').filter(l => l.startsWith('Sheets:')).join('')}
                </div>
                <div style={{ color: 'var(--ink-4)', fontSize: 12, marginBottom: 28 }}>
                  Open with Excel, LibreOffice, or Google Sheets — includes bar and pie charts.
                </div>
                {excelDownloadUrl && (
                  <a href={excelDownloadUrl} download
                    style={{
                      display: 'inline-block', padding: '10px 28px',
                      background: 'var(--hue-miyamoto)', color: '#fff',
                      borderRadius: 3, fontFamily: 'monospace', fontSize: 13,
                      textDecoration: 'none', letterSpacing: '0.04em',
                    }}>
                    ↓ Download .xlsx
                  </a>
                )}
              </div>
            ) : mode === 'rendered'
              ? <div className="result-article" dangerouslySetInnerHTML={{__html: `<p>${renderMd(content)}</p>`}}/>
              : <pre className="result-raw">{content}</pre>}
          </div>
```

- [ ] **Step 2: Commit**

```bash
git add static/index/overlays.jsx
git commit -m "feat(overlays): add Excel download card in ResultModal"
```

---

## Task 10: Frontend — Wire NewsFeedView into app.jsx

**Files:**
- Modify: `static/index/app.jsx`

- [ ] **Step 1: Destructure NewsFeedView at the top of app.jsx**

Change line 4 from:
```js
const { Sidebar, Masthead, ChatView, DashboardView, RightPanel } = window.CLViews;
```
to:
```js
const { Sidebar, Masthead, ChatView, DashboardView, RightPanel, NewsFeedView } = window.CLViews;
```

- [ ] **Step 2: Update the tab routing in App render**

Find lines 133–135 in `app.jsx`:
```jsx
        {tab === 'chat'
          ? <ChatView agKey={agKey} messages={msgs[agKey]} loading={loading} onSend={send}/>
          : <DashboardView dash={dash} setAgent={switchAgent}/>}
```

Replace with:
```jsx
        {tab === 'chat'
          ? <ChatView agKey={agKey} messages={msgs[agKey]} loading={loading} onSend={send}/>
          : agKey === 'news'
            ? <NewsFeedView agKey={agKey} messages={msgs[agKey]} loading={loading} onSend={send}/>
            : <DashboardView dash={dash} setAgent={switchAgent}/>}
```

- [ ] **Step 3: Restart server and do full smoke test**

```bash
$env:PYTHONUTF8=1; python server.py
```

Open `http://localhost:8000` and verify:

1. Click **Najwa** in the sidebar → switch to **Overview** tab → news feed loads with "All" category articles
2. Click **Technology** tab → feed filters to tech news
3. Click any headline → it populates the chat input
4. Click **Mansa** in the sidebar → open the right panel (panel icon top right) → donut chart and monthly bar chart appear
5. On the Crew Mode drawer → run a DataAnalyst pipeline → after completion, click "View full output" → Excel download button appears for the `.xlsx` file

- [ ] **Step 4: Commit**

```bash
git add static/index/app.jsx
git commit -m "feat(app): wire NewsFeedView for Najwa Overview tab"
```

---

## Self-Review

**Spec coverage check:**
- ✅ `GET /api/news/feed` — Task 1
- ✅ `GET /api/budget/analytics` — Task 2
- ✅ `generate_excel_report` tool — Task 3
- ✅ DataAnalyst viz agent + task + server output collection — Task 4
- ✅ `newsFeedAPI`, `budgetAnalyticsAPI` in data.jsx — Task 5
- ✅ News feed CSS — Task 6
- ✅ `NewsFeedView` component — Task 7
- ✅ `BudgetDonut` + `BudgetBarChart` + updated panel — Task 8
- ✅ ResultModal Excel download — Task 9
- ✅ App routing for Najwa Overview — Task 10

**No placeholders found.** All steps contain complete code.

**Type consistency check:**
- `newsFeedAPI` defined in Task 5, consumed in Task 7 — matches
- `budgetAnalyticsAPI` defined in Task 5, consumed in Task 8 — matches
- `analytics.category_totals` passed to `BudgetDonut` as `categoryTotals` — prop name consistent
- `analytics.monthly_trend` passed to `BudgetBarChart` as `monthlyTrend` — prop name consistent
- `_excel_tool` instantiated in Task 4, added to `make_viz_agent()` tools list in same task — consistent
- `generate_excel_report` output format (starts with `✅ Excel report saved:`, contains `Download: /api/...`) matches the detection logic in Task 9 — consistent
