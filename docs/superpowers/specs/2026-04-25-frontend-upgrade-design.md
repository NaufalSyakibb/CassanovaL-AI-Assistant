# Frontend Upgrade — Najwa News Feed, Mansa Budget Charts, DataAnalyst Excel

**Date:** 2026-04-25
**Status:** Approved

---

## Overview

Three coordinated upgrades to the CassanovaL web frontend and backend:

1. **Najwa (News)** — Replace plain chat Overview with a split-pane live news feed powered by NewsAPI, categorized by topic.
2. **Mansa (Budget)** — Redesign the right panel to include a donut chart (category breakdown) + monthly bar chart (5-month trend), replacing the static figure block.
3. **DataAnalyst Crew** — Add Excel (`.xlsx`) output alongside the existing Python visualization; confirm all crew agents use Mistral models.

---

## 1. Najwa — Categorized News Feed

### Behavior
- When the user opens Najwa and switches to the **Overview** tab, they see a split-pane view instead of the default dashboard.
- **Left pane (~60%)**: Live news feed. Category filter tabs at the top: `All · Technology · Finance · Politics · World · Science`. Clicking a tab filters the list. Each article shows: source name (colored by category), headline, and relative time (e.g. "2h ago").
- **Right pane (~40%)**: Najwa chat input. The user can ask questions about any headline or request a deeper briefing.
- The feed auto-loads on mount. A manual "Refresh" button in the header re-fetches.

### Backend — `GET /api/news/feed`
**Query params:** `category` (optional: `technology | business | politics | science | general`), `q` (optional search query), `page` (default 1).

**Implementation:**
```python
import requests

NEWS_CATEGORIES = {
    "technology": "technology",
    "finance":    "business",       # NewsAPI uses "business" for finance
    "politics":   "general",        # NewsAPI has no politics — use q="politics"
    "world":      "general",
    "science":    "science",
}

@app.get("/api/news/feed")
async def news_feed(category: str = "general", q: str = "", page: int = 1):
    api_key = os.getenv("NEWS_API_KEY")
    params = {
        "apiKey": api_key,
        "language": "en",
        "pageSize": 20,
        "page": page,
        "sortBy": "publishedAt",
    }
    # Map frontend category names to NewsAPI params
    newsapi_cat = NEWS_CATEGORIES.get(category, "general")
    if category == "politics":
        params["q"] = q or "politics"
        url = "https://newsapi.org/v2/everything"
    else:
        params["category"] = newsapi_cat
        if q:
            params["q"] = q
        url = "https://newsapi.org/v2/top-headlines"
    
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    articles = [
        {
            "title":       a["title"],
            "source":      a["source"]["name"],
            "url":         a["url"],
            "published_at": a["publishedAt"],
            "description": a.get("description", ""),
            "category":    category,
        }
        for a in data.get("articles", [])
        if a.get("title") and "[Removed]" not in a.get("title", "")
    ]
    return {"articles": articles, "total": data.get("totalResults", 0), "category": category}
```

### Frontend — `NewsFeedView` component (views.jsx)
- Rendered when `agKey === 'news'` and `tab === 'overview'`.
- Replaces `DashboardView` for the Najwa agent only.
- State: `activeCategory`, `articles`, `loading`, `chatMessages`, `chatLoading`.
- Category color map: Tech → `var(--hue-linus)` (blue), Finance → `var(--hue-mansa)` (gold), Politics → `var(--hue-lavoiser)` (red), World → `var(--ink-3)`, Science → `var(--hue-cicero)`.
- Article list renders with `source · category` colored badge, headline, relative time.
- Chat pane reuses the existing `chatAPI` helper, sends to `agent: 'news'`.
- Clicking an article headline appends its title to the chat input as a prompt suggestion.

### Data helper
```js
const newsFeedAPI = (category = 'general', q = '') =>
  apiFetch(`/api/news/feed?category=${category}&q=${encodeURIComponent(q)}`);
```
Added to `data.jsx` and exported via `window.CLData`.

---

## 2. Mansa — Budget Panel Redesign

### Layout (right panel when `agKey === 'budget'`)
```
┌─────────────────────────────────┐
│ VI · Finance · Mansa            │  ← panel header (gold accent)
│ Available Balance: Rp 18.4M     │
│ Income: +22.0M  │ Expense: −7.3M│
├──────────────────┬──────────────┤
│  Donut Chart     │  Bar Chart   │  ← 50/50, 90px tall
│  (by category)   │  (5 months)  │
├──────────────────┴──────────────┤
│  Scan Receipt  (dropzone)       │
├─────────────────────────────────┤
│  Recent Transactions            │
│  APR 23  Monthly salary  +22.0M │
│  APR 21  Rent, April    − 4.5M  │
│  APR 20  Groceries       −620K  │
└─────────────────────────────────┘
```

### Backend — `GET /api/budget/analytics`
Returns category totals and 5-month income/expense data.

```python
@app.get("/api/budget/analytics")
async def budget_analytics():
    data = json.loads(Path("data/budget.json").read_text(encoding="utf-8"))
    
    # Category breakdown (expenses only)
    from collections import defaultdict
    cat_totals = defaultdict(float)
    for t in data:
        if t["type"] == "expense":
            cat_totals[t.get("category", "other")] += t["amount"]
    
    # 5-month income/expense trend
    from datetime import datetime, timedelta
    months = []
    for i in range(4, -1, -1):
        d = datetime.now().replace(day=1) - timedelta(days=i*30)
        ym = d.strftime("%Y-%m")
        label = d.strftime("%b")
        monthly = [t for t in data if t.get("date", "").startswith(ym)]
        months.append({
            "label": label,
            "income":  sum(t["amount"] for t in monthly if t["type"] == "income"),
            "expense": sum(t["amount"] for t in monthly if t["type"] == "expense"),
        })
    
    return {
        "category_totals": dict(cat_totals),
        "monthly_trend":   months,
    }
```

### Frontend — Charts in RightPanel (views.jsx)
- Replace the `panel-figure` block in the budget panel with two inline SVG charts.
- **Donut chart**: Pure SVG, computed from `category_totals`. 5 segments max, overflow bucketed into "Other". Color palette: gold, blue, green, red, grey.
- **Bar chart**: Pure SVG, 5-month grouped bars (income blue, expense red). Height normalized to max value.
- Both rendered via a `useEffect` that calls `budgetAnalyticsAPI()` on mount.
- Scan Receipt dropzone remains below the charts.

### Data helper
```js
const budgetAnalyticsAPI = () => apiFetch('/api/budget/analytics');
```

---

## 3. DataAnalyst Crew — Excel Output + Mistral Confirmation

### Excel Report (new tool in `data_tools.py`)
```python
@tool
def generate_excel_report(filename: str = "") -> str:
    """Generate an Excel (.xlsx) report with data sheet + embedded charts.
    Creates: Summary sheet, Data sheet, and 3 chart sheets (bar, donut, trend)."""
    import openpyxl
    from openpyxl.chart import BarChart, PieChart, Reference
    ...
    # Sheet 1: Summary (stats)
    # Sheet 2: Cleaned data
    # Sheet 3: Bar chart (top categories by value)
    # Sheet 4: Pie chart (distribution)
    # Saved to DataAnalyst Agent folder as <stem>_report.xlsx
```

### Crew update (`crewai_agents.py`)
- `make_viz_agent()`: Add `generate_excel_report` tool alongside `_viz_tool`.
- `make_viz_task()`: Update description to instruct agent to call both `generate_visualization_code` and `generate_excel_report`.
- All models already use Mistral — no changes needed. Confirmed:
  - Cleaner: `llm_large` (mistral-large-latest)
  - Stats: `llm_large` (mistral-large-latest)
  - Viz: `llm_small` + `function_calling_llm=llm_large` (both Mistral)

### Server — collect Excel output
In `_run_crew_background`, add to the dataanalyst outputs collection:
```python
for rel in ("stats_report.md", "visualization.py"):  # existing
    ...
# Add:
for f in da_dir.glob("*_report.xlsx"):
    outputs[f.name] = f"✅ Excel report saved:\n{f}\n\nDownload: /api/dataanalyst/download/{f.name}"
```

### ResultModal — download link
When an output value starts with `✅ Excel report saved:`, render a download button instead of raw text.

---

## Files Changed

| File | Change |
|---|---|
| `server.py` | + `GET /api/news/feed`, + `GET /api/budget/analytics`, collect `.xlsx` in crew outputs |
| `tools/data_tools.py` | + `generate_excel_report` tool |
| `crewai_agents.py` | Update viz agent + viz task to include Excel generation |
| `static/index/data.jsx` | + `newsFeedAPI`, + `budgetAnalyticsAPI` helpers |
| `static/index/views.jsx` | + `NewsFeedView`, update `RightPanel` budget section |
| `static/index/overlays.jsx` | Update `ResultModal` to render Excel download button |
| `static/index/styles.css` | + styles for news feed, category tabs, chart containers |

---

## Out of Scope
- Real-time WebSocket news updates (RSS polling or manual refresh only)
- News article full-text fetch (headlines + description only)
- Budget forecasting / AI insights on spending trends
- Interactive Excel charts beyond static openpyxl charts
