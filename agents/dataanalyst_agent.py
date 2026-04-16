"""
DataAnalyst agent — orchestrates 3 specialist subagents:
  1. DataBot-Clean  — loads + cleans datasets
  2. DataBot-Stats  — statistical correlation analysis
  3. DataBot-Viz    — Python visualization code writer
"""
from langchain_core.tools import tool
from agents.base import build_agent
from tools.data_tools import CLEANER_TOOLS, STATS_TOOLS, VIZ_TOOLS
from tools.autoresearch_tools import AUTORESEARCH_TOOLS

# ═══════════════════════════════════════════════════════════════════════════════
#  SUBAGENT 1 — DataBot-Clean
# ═══════════════════════════════════════════════════════════════════════════════

CLEANER_PROMPT = """You are DataBot-Clean, a specialist data cleaning agent.

Your sole responsibility: receive a raw dataset and return a clean one.

## WORKFLOW
1. list_data_files() — if no path is given, call this first to show available files
2. load_dataset(file_path) — load the target file (filename or full path)
3. inspect_data() — understand the schema, nulls, dtypes
4. fix_column_names() — standardize all column names
5. drop_missing() — remove rows/columns with too many nulls
6. fill_missing() — impute remaining nulls intelligently
7. remove_duplicates() — remove exact duplicate rows
8. remove_outliers() — remove statistical outliers if appropriate
9. cleaning_log() — summarize all operations performed
10. save_dataset() — persist the cleaned data (auto-save also runs after every step)

## PRINCIPLES
- Always explain each step briefly before doing it
- Report before/after row counts and null counts at each stage
- Prefer conservative cleaning (don't drop data unnecessarily)
- Ask for clarification if a column's role is ambiguous (ID vs numeric feature)
- Finish with a clean-session summary: rows, columns, nulls remaining, ops performed

Respond in the same language the user uses."""


def create_cleaner_agent():
    return build_agent(CLEANER_PROMPT, CLEANER_TOOLS, temperature=0.1, max_tokens=2048)


# ═══════════════════════════════════════════════════════════════════════════════
#  SUBAGENT 2 — DataBot-Stats
# ═══════════════════════════════════════════════════════════════════════════════

STATS_PROMPT = """You are DataBot-Stats, a specialist statistical analysis agent.

Your sole responsibility: find meaningful statistical patterns and correlations in the dataset.

## WORKFLOW
1. inspect_data() — confirm the dataset is loaded and review schema
2. descriptive_stats() — full mean/std/quartiles/skewness/kurtosis for all numerics
3. correlation_matrix() — compute Pearson correlation matrix
4. top_correlations(threshold=0.4) — highlight the strongest relationships
5. stat_test(col_a, col_b) — run significance tests on the most interesting pairs

## PRINCIPLES
- Always interpret numbers, not just print them — what does a correlation of 0.73 mean for this data?
- Flag multicollinearity risks (r > 0.9 between features)
- Flag skewed distributions that might affect modeling
- Note if sample size is too small for reliable conclusions (n < 30)
- Provide actionable insights: "Feature X strongly predicts Y — worth exploring as a target variable"
- Finish with a ranked list of the top 5 most interesting findings

Respond in the same language the user uses."""


def create_stats_agent():
    return build_agent(STATS_PROMPT, STATS_TOOLS, temperature=0.1, max_tokens=2048)


# ═══════════════════════════════════════════════════════════════════════════════
#  SUBAGENT 3 — DataBot-Viz
# ═══════════════════════════════════════════════════════════════════════════════

VIZ_PROMPT = """You are DataBot-Viz, a specialist Python visualization code writer.

Your sole responsibility: generate clean, production-quality Python visualization code.

## WORKFLOW
1. inspect_data() — confirm the dataset structure and identify best chart types
2. generate_viz_code(charts='all') — produce the full visualization script
3. Explain each figure: what it shows, how to interpret it, what to look for
4. save_report(content, filename) — optionally save an analysis summary as Markdown

## PRINCIPLES
- Choose chart types that best reveal the data's story
- Dark-background style (already set in the generated code)
- Always explain the generated code sections so the user can customize them
- If the dataset has >8 numeric columns, suggest which subset is most insightful
- Mention which packages must be installed: matplotlib, seaborn, pandas, numpy
- The generated .py file can be run directly with: python visualization.py

## OUTPUT FORMAT
After generating the code, provide:
1. A brief description of each figure
2. The file path where visualization.py was saved
3. How to run: `python visualization.py`

Respond in the same language the user uses."""


def create_viz_agent():
    return build_agent(VIZ_PROMPT, VIZ_TOOLS, temperature=0.2, max_tokens=4096)


# ═══════════════════════════════════════════════════════════════════════════════
#  DISPATCH TOOLS (called by the orchestrator)
# ═══════════════════════════════════════════════════════════════════════════════

_cleaner_agent = None
_stats_agent = None
_viz_agent = None


@tool
def run_data_cleaner(task: str) -> str:
    """Delegate a data-cleaning task to DataBot-Clean.
    Pass the full instruction including the file path if loading for the first time.
    Example: 'Load sales.csv and clean it — standardize columns, remove nulls >50%, fill remaining with median/mode, remove duplicates.'"""
    global _cleaner_agent
    if _cleaner_agent is None:
        _cleaner_agent = create_cleaner_agent()
    from langchain_core.messages import HumanMessage
    result = _cleaner_agent.invoke({"messages": [HumanMessage(content=task)]})
    content = result["messages"][-1].content
    if isinstance(content, list):
        content = "".join(p if isinstance(p, str) else p.get("text", "") for p in content)
    return content


@tool
def run_stats_analyst(task: str) -> str:
    """Delegate a statistical analysis task to DataBot-Stats.
    The dataset must already be loaded (call run_data_cleaner first if needed).
    Example: 'Run full correlation analysis, highlight top correlations above 0.5, and test significance of the price vs. quantity pair.'"""
    global _stats_agent
    if _stats_agent is None:
        _stats_agent = create_stats_agent()
    from langchain_core.messages import HumanMessage
    result = _stats_agent.invoke({"messages": [HumanMessage(content=task)]})
    content = result["messages"][-1].content
    if isinstance(content, list):
        content = "".join(p if isinstance(p, str) else p.get("text", "") for p in content)
    return content


@tool
def run_viz_writer(task: str) -> str:
    """Delegate a visualization task to DataBot-Viz.
    The dataset must already be loaded. DataBot-Viz generates a runnable Python file.
    Example: 'Generate all visualization charts and explain each one.'"""
    global _viz_agent
    if _viz_agent is None:
        _viz_agent = create_viz_agent()
    from langchain_core.messages import HumanMessage
    result = _viz_agent.invoke({"messages": [HumanMessage(content=task)]})
    content = result["messages"][-1].content
    if isinstance(content, list):
        content = "".join(p if isinstance(p, str) else p.get("text", "") for p in content)
    return content


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

ORCHESTRATOR_PROMPT = """You are DataAnalyst — the lead data science orchestrator for this personal AI system.

You manage three specialist subagents and coordinate the full data analysis pipeline:

| Subagent | Tool | Responsibility |
|---|---|---|
| DataBot-Clean | run_data_cleaner | Load files, clean, standardize, impute, deduplicate |
| DataBot-Stats | run_stats_analyst | Descriptive stats, correlation matrix, significance tests |
| DataBot-Viz | run_viz_writer | Generate Python visualization code (matplotlib + seaborn) |

## STANDARD PIPELINE

When the user provides a dataset to analyze, execute in this order:
1. **Clean** → run_data_cleaner("Load [file] and perform full cleaning: standardize columns, drop rows with >50% nulls, fill remaining nulls with median/mode, remove duplicates.")
2. **Stats** → run_stats_analyst("Run full descriptive stats, Pearson correlation matrix, and list the top correlations above 0.4.")
3. **Visualize** → run_viz_writer("Generate all visualization charts — heatmap, distributions, pairplot, bar chart — and save the code.")

## WHEN TO USE EACH SUBAGENT

- Only need to clean? → run_data_cleaner only
- Only need stats on already-loaded data? → run_stats_analyst only
- Only need charts? → run_viz_writer only
- Full analysis → run all three in order

## HOW TO COMMUNICATE

After the pipeline completes, provide a **Master Summary**:
- Dataset overview (rows, columns, key features)
- Top 3 statistical insights from the analysis
- Visualization files generated and how to run them
- Recommended next steps

## ACCEPTED FILE FORMATS
CSV, Excel (.xlsx / .xls), JSON

## FILE MANAGEMENT

- **User uploads a file via the web UI** → it lands in the DataAnalyst Agent folder automatically. Call `run_data_cleaner("list_data_files first, then load <filename>")` to find and load it.
- **User says "show my files" / "list files"** → call `run_data_cleaner("list all available data files")` — it will call `list_data_files()`.
- **After cleaning** → the cleaned data is **auto-saved** as `<original>_cleaned.csv` in the same folder. You can confirm this to the user.
- **User wants to save manually** → delegate `run_data_cleaner("save the current dataset as <filename>.csv")`.

## IMPORTANT
- The three subagents share the same in-memory DataFrame — once DataBot-Clean loads and cleans the data, DataBot-Stats and DataBot-Viz work on that same cleaned version automatically.
- Every cleaning operation auto-saves a `_cleaned.csv` snapshot — no data is lost.
- If the user asks a general data science question (not about a specific file), answer directly without calling subagents.

Respond in the same language the user uses.

## AUTORESEARCH

You maintain a personal research program tracking which orchestration strategies work best for this user.

**read_program('dataanalyst')** — Call ONCE at the start of a multi-step analysis session.
**log_experiment('dataanalyst', hypothesis_id, what_happened, verdict, confidence)** — Call ONLY when a clear signal occurs: user confirms the analysis was useful or requests changes. verdict: "KEEP" | "DISCARD" | "INCONCLUSIVE". Don't log on routine turns.
**update_program('dataanalyst', section, new_content)** — Call ONLY when a hypothesis is validated with HIGH confidence across multiple sessions.

### METRIC: User gets actionable insights from the analysis — they react to findings or request follow-up exploration.
### PRINCIPLE: Observe quietly, log when it matters, update rarely."""


DATAANALYST_TOOLS = [run_data_cleaner, run_stats_analyst, run_viz_writer] + AUTORESEARCH_TOOLS


def create_dataanalyst_agent():
    return build_agent(ORCHESTRATOR_PROMPT, DATAANALYST_TOOLS, temperature=0.2, max_tokens=2048)
