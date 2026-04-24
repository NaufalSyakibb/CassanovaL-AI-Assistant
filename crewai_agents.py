"""
Multi-Agent System with CrewAI + Mistral AI
============================================

Pipeline 1 — Research (2 agents):  Researcher → Writer
Pipeline 2 — DataAnalyst (3 agents): DataBot-Clean → DataBot-Stats → DataBot-Viz

Usage:
  python crewai_agents.py
  python crewai_agents.py --topic "Quantum Computing"
"""

import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

from crewai import Agent, Task, Crew, LLM
from crewai_tools import SerperDevTool, FileWriterTool
from langchain_community.tools import DuckDuckGoSearchRun
from crewai.tools import BaseTool
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

# ── LLMs ──────────────────────────────────────────────────────────────────────

def _make_mistral_llm(model: str = "mistral-large-latest", temperature: float = 0.2) -> LLM:
    """Create a Mistral LLM for CrewAI via LiteLLM.

    base_url is set explicitly so LiteLLM always resolves api.mistral.ai correctly
    on Windows (avoids getaddrinfo failures caused by ambiguous provider routing).
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY not found in .env file")
    return LLM(
        model=f"mistral/{model}",
        api_key=api_key,
        base_url="https://api.mistral.ai/v1",
        temperature=temperature,
        max_tokens=2048,
    )


def _make_gemma_llm(model: str, api_key_env: str, temperature: float = 0.2) -> LLM:
    """Create a Gemma LLM via Google AI Studio (LiteLLM gemini/ provider).

    Model names follow Google AI Studio naming, e.g.:
      'gemma-4'      — Gemma 4 (main / large variant)
      'gemma-4-2b-it' — Gemma 4 2B instruction-tuned
    Override model names via env vars GEMMA4_MODEL / GEMMA4_2_MODEL.
    """
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise ValueError(f"{api_key_env} not found in .env file")
    return LLM(
        model=f"gemini/{model}",
        api_key=api_key,
        temperature=temperature,
        max_tokens=2048,
    )


# ── Mistral LLMs (cloud) ───────────────────────────────────────────────────────
llm_large = _make_mistral_llm("mistral-large-latest", temperature=0.3)
llm_small = _make_mistral_llm("mistral-small-latest", temperature=0.1)


# ── Gemma4 LLMs (Google AI Studio) ────────────────────────────────────────────
# Model names can be overridden via .env: GEMMA4_MODEL / GEMMA4_2_MODEL
_gemma4_model   = os.getenv("GEMMA4_MODEL",   "gemma-4")
_gemma4_2_model = os.getenv("GEMMA4_2_MODEL", "gemma-4-2b-it")

# Lazy with Mistral fallback — Gemma4 keys are optional.
# Created at module level but wrapped so a missing key doesn't crash the import.
def _get_gemma4_llm() -> LLM:
    """Gemma4 large, falls back to mistral-large-latest if GEMMA4_API_KEY is absent."""
    try:
        return _make_gemma_llm(_gemma4_model, "GEMMA4_API_KEY", temperature=0.3)
    except ValueError:
        print("[WARN] GEMMA4_API_KEY not found — DataAnalyst Stats agent will use Mistral large.")
        return _make_mistral_llm("mistral-large-latest", temperature=0.3)

def _get_gemma4_2_llm() -> LLM:
    """Gemma4 2B, falls back to mistral-small-latest if GEMMA4_2_API_KEY is absent."""
    try:
        return _make_gemma_llm(_gemma4_2_model, "GEMMA4_2_API_KEY", temperature=0.1)
    except ValueError:
        print("[WARN] GEMMA4_2_API_KEY not found — DataAnalyst Viz agent will use Mistral small.")
        return _make_mistral_llm("mistral-small-latest", temperature=0.1)

llm_gemma4   = _get_gemma4_llm()
llm_gemma4_2 = _get_gemma4_2_llm()


# ── Tools ─────────────────────────────────────────────────────────────────────

# LinkUp deep search tool — used by Ibnu Al-Haytham research crew
class LinkUpSearchTool(BaseTool):
    name: str = "LinkUp Deep Search"
    description: str = (
        "Perform a deep web search using LinkUp. Returns full source content. "
        "Input should be a concise search query string."
    )

    def _run(self, query: str) -> str:
        from linkup import LinkupClient
        client = LinkupClient(api_key=os.getenv("LINKUP_API_KEY", ""))
        response = client.search(
            query=query,
            depth="deep",
            output_type="sourcedAnswer",
        )
        return str(response)


# Search tool priority: LinkUp > Serper > DuckDuckGo
_linkup_key = os.getenv("LINKUP_API_KEY", "")
_serper_key  = os.getenv("SERPER_API_KEY", "")

if _linkup_key:
    research_search_tool = LinkUpSearchTool()
elif _serper_key:
    research_search_tool = SerperDevTool()
else:
    _ddg = DuckDuckGoSearchRun()

    class DuckDuckGoTool(BaseTool):
        name: str = "DuckDuckGo Search"
        description: str = (
            "Search the web for current information. "
            "Input should be a concise search query string."
        )

        def _run(self, query: str) -> str:
            return _ddg.run(query)

    research_search_tool = DuckDuckGoTool()

# DataAnalyst crew still uses DuckDuckGo (no deep search needed there)
_serper_key_da = os.getenv("SERPER_API_KEY", "")
if _serper_key_da:
    search_tool = SerperDevTool()
else:
    if not _linkup_key:
        search_tool = research_search_tool  # reuse DuckDuckGo instance
    else:
        _ddg_da = DuckDuckGoSearchRun()

        class DuckDuckGoToolDA(BaseTool):
            name: str = "DuckDuckGo Search"
            description: str = "Search the web. Input: concise query string."

            def _run(self, query: str) -> str:
                return _ddg_da.run(query)

        search_tool = DuckDuckGoToolDA()

file_writer = FileWriterTool()


# ── Research Output Directory ──────────────────────────────────────────────────

def _research_dir() -> Path:
    """Return the directory where research output files are written.

    Priority:
      1. $OBSIDIAN_VAULT_PATH/Ferry Agent/  (OBSIDIAN_VAULT_PATH already points
         to the 'AI Data' folder, so we only append the agent subfolder)
      2. Project root / AI Data / Ferry Agent  (fallback if env var not set)
    """
    vault = os.getenv("OBSIDIAN_VAULT_PATH", "")
    if vault:
        p = Path(vault) / "Ferry Agent"
        p.mkdir(parents=True, exist_ok=True)
        return p
    p = Path(__file__).parent / "AI Data" / "Ferry Agent"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── Agent Factory ─────────────────────────────────────────────────────────────
#
# Ibn Al-Haytham — 7-Agent Hybrid Research Pipeline
#
# Phase 1 (sequential): Scout → Filter
# Phase 2 (parallel):   IdeaGen ‖ Validator  (ThreadPoolExecutor)
# Phase 3 (sequential): Synthesizer → Critic → Writer


def _read_phase_output(fname: str) -> str:
    """Read a phase output file from research dir; return empty string if missing."""
    p = _research_dir() / fname
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ── Crew Builder ──────────────────────────────────────────────────────────────

def build_crew(topic: str, step_cb=None, task_cb=None) -> Crew:
    """Build the 2-agent Ibnu Al-Haytham self-critique pipeline.

    Agent 1 (Drafter)  — researches the topic and writes a first draft,
                         flagging weak spots with [⚠ PERLU DIKUATKAN].
    Agent 2 (Critic)   — critiques the draft's logic and evidence,
                         then produces the refined final article.
    """
    drafter = make_drafter(topic)
    critic  = make_critic(topic)

    draft_task    = make_draft_task(topic, drafter)
    critique_task = make_critique_task(topic, critic, draft_task)

    return Crew(
        agents=[drafter, critic],
        tasks=[draft_task, critique_task],
        verbose=step_cb is None,   # verbose only in standalone CLI mode
        step_callback=step_cb,
        task_callback=task_cb,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE 2 — DATA ANALYST CREW  (Clean → Stats → Viz)
# ══════════════════════════════════════════════════════════════════════════════

class DataCleanCrewTool(BaseTool):
    """Load + fully clean a dataset using the shared data_tools session."""
    name: str = "run_data_cleaning_pipeline"
    description: str = (
        "Load and fully clean a dataset file. "
        "Input: the filename, e.g. 'sales.csv'. "
        "Runs: load → fix column names → drop high-null rows/cols → fill missing → remove duplicates → save."
    )

    def _run(self, filename: str) -> str:
        from tools.data_tools import (
            _reset_session,
            load_dataset, fix_column_names, drop_missing,
            fill_missing, remove_duplicates, save_dataset, cleaning_log,
        )
        _reset_session()   # clear stale state from any previous run
        parts = []
        try:
            parts.append(load_dataset.invoke({"file_path": filename.strip()}))
            parts.append(fix_column_names.invoke({}))
            parts.append(drop_missing.invoke({}))
            parts.append(fill_missing.invoke({}))
            parts.append(remove_duplicates.invoke({}))
            parts.append(save_dataset.invoke({"filename": ""}))
            parts.append(cleaning_log.invoke({}))
        except Exception as exc:
            parts.append(f"Error during cleaning: {exc}")
        return "\n\n".join(p for p in parts if p)


class StatsAnalysisCrewTool(BaseTool):
    """Run descriptive stats + correlation analysis on the already-loaded dataset."""
    name: str = "run_statistical_analysis"
    description: str = (
        "Run full statistical analysis on the currently loaded dataset. "
        "Computes descriptive stats, Pearson correlation matrix, and top correlations. "
        "Input: any string (ignored — works on the in-memory dataset)."
    )

    def _run(self, query: str = "") -> str:
        from tools.data_tools import (
            descriptive_stats, correlation_matrix, top_correlations, save_report,
        )
        parts = []
        try:
            parts.append(descriptive_stats.invoke({}))
            parts.append(correlation_matrix.invoke({}))
            parts.append(top_correlations.invoke({"threshold": 0.3}))
            report_text = "\n\n".join(p for p in parts if p)
            save_report.invoke({"content": report_text, "filename": "stats_report.md"})
        except Exception as exc:
            parts.append(f"Error during stats: {exc}")
        return "\n\n".join(p for p in parts if p)


class VizGeneratorCrewTool(BaseTool):
    """Generate runnable Python visualization code for the loaded dataset."""
    name: str = "generate_visualization_code"
    description: str = (
        "Generate complete Python visualization code (matplotlib + seaborn) for the dataset. "
        "Creates: correlation heatmap, distributions, pairplot, bar chart. "
        "Input: any string (ignored — works on the in-memory dataset)."
    )

    def _run(self, query: str = "") -> str:
        from tools.data_tools import generate_viz_code
        try:
            return generate_viz_code.invoke({"charts": "all"})
        except Exception as exc:
            return f"Error generating viz code: {exc}"


_data_clean_tool = DataCleanCrewTool()
_stats_tool      = StatsAnalysisCrewTool()
_viz_tool        = VizGeneratorCrewTool()


def make_data_cleaner() -> Agent:
    """Agent 1 — Mistral large: reliable cloud LLM for structured cleaning pipeline."""
    return Agent(
        llm=llm_large,
        function_calling_llm=llm_small,
        role="Data Cleaning Specialist",
        goal="Load and thoroughly clean the target dataset — standardize columns, handle nulls, remove duplicates",
        backstory=(
            "You are a meticulous data engineer with 10 years of experience cleaning messy datasets. "
            "You never skip steps and always report before/after statistics so stakeholders know exactly what changed."
        ),
        tools=[_data_clean_tool],
        allow_delegation=False,
        verbose=True,
        max_iter=4,
    )


def make_stats_analyst_agent() -> Agent:
    """Agent 2 — Gemma4: strong analytical reasoning for statistical interpretation."""
    return Agent(
        llm=llm_gemma4,
        # function_calling_llm defaults to llm (llm_gemma4) — no need to set explicitly
        role="Statistical Analysis Specialist",
        goal="Discover meaningful statistical patterns, correlations, and insights in the cleaned dataset",
        backstory=(
            "You are a senior data scientist specialising in exploratory data analysis. "
            "You don't just print numbers — you interpret them, flag multicollinearity, "
            "and deliver a ranked list of actionable insights."
        ),
        tools=[_stats_tool],
        allow_delegation=False,
        verbose=True,
        max_iter=4,
    )


def make_viz_agent() -> Agent:
    """Agent 3 — Gemma4:2b for generation; Gemma4 for reliable tool-calling decisions."""
    return Agent(
        llm=llm_gemma4_2,
        function_calling_llm=llm_gemma4,   # use larger model for tool-use decisions
        role="Data Visualization Engineer",
        goal="Generate production-quality Python visualization code that reveals the dataset's story",
        backstory=(
            "You are a Python visualization expert who turns raw numbers into compelling charts. "
            "You write clean, well-commented matplotlib + seaborn code that runs out of the box."
        ),
        tools=[_viz_tool],
        allow_delegation=False,
        verbose=True,
        max_iter=4,
    )


def make_clean_task(filename: str, agent: Agent) -> Task:
    return Task(
        description=(
            f"Load the file **'{filename}'** and run the full data cleaning pipeline:\n\n"
            f"1. Load the file using `run_data_cleaning_pipeline('{filename}')`\n"
            "2. The tool will automatically: fix column names, drop rows/cols with >50% nulls, "
            "fill remaining missing values (median for numeric, mode for categorical), "
            "remove duplicate rows, and save a `_cleaned.csv` snapshot.\n\n"
            "Output a concise summary: shape before/after, columns, operations performed, saved filename."
        ),
        expected_output=(
            "A structured cleaning report: rows before/after, columns, null counts, "
            "operations performed, and the path of the saved cleaned file."
        ),
        agent=agent,
        output_file="task1_data_clean.txt",
    )


def make_stats_task(agent: Agent, clean_task: Task) -> Task:
    return Task(
        description=(
            "The dataset has been cleaned and is loaded in memory. "
            "Run `run_statistical_analysis('')` to perform:\n\n"
            "1. Descriptive statistics (mean, std, quartiles, skewness, kurtosis)\n"
            "2. Pearson correlation matrix\n"
            "3. Top correlations above threshold 0.3\n\n"
            "Interpret the results — don't just print numbers. "
            "Flag strong correlations (|r| > 0.7), skewed distributions, and multicollinearity. "
            "End with a ranked list of the **top 5 most interesting findings**."
        ),
        expected_output=(
            "Statistical analysis report with: descriptive stats table, correlation matrix, "
            "top correlations, interpretation of key findings, and top-5 insight list. "
            "Report is auto-saved to stats_report.md."
        ),
        agent=agent,
        context=[clean_task],
        output_file="task2_stats_analysis.txt",
    )


def make_viz_task(agent: Agent, stats_task: Task) -> Task:
    return Task(
        description=(
            "The dataset is cleaned and analyzed. "
            "Call `generate_visualization_code('')` to create a full visualization script.\n\n"
            "The tool generates: correlation heatmap, feature distributions, "
            "scatter matrix (pairplot), and categorical bar chart.\n\n"
            "After the tool runs, explain:\n"
            "1. What each figure shows and how to read it\n"
            "2. The file path of the saved `visualization.py`\n"
            "3. How to run it: `python visualization.py`\n"
            "4. Which packages need to be installed: `pip install matplotlib seaborn pandas`"
        ),
        expected_output=(
            "Description of each chart, the visualization.py file path, run instructions, "
            "and package install command."
        ),
        agent=agent,
        context=[stats_task],
        output_file="task3_visualization.txt",
    )


def build_data_crew(filename: str, step_cb=None, task_cb=None) -> Crew:
    """Build a 3-agent sequential DataAnalyst crew with mixed LLMs.

    Agent assignment:
      Agent 1 — Data Cleaner     → Mistral large (cloud, reliable structured output)
      Agent 2 — Stats Analyst    → Gemma4        (Google AI Studio, strong reasoning)
      Agent 3 — Viz Engineer     → Gemma4:2b     (Google AI Studio, fast code generation)
    """
    print(f"\n{'='*60}")
    print(f"  CrewAI DataAnalyst Crew — Multi-LLM")
    print(f"  File: {filename}")
    print(f"  Agents:")
    print(f"    [1] Data Cleaner    → mistral-large-latest  (Mistral Cloud)")
    print(f"    [2] Stats Analyst   → {_gemma4_model:<20} (Google AI Studio)")
    print(f"    [3] Viz Engineer    → {_gemma4_2_model:<20} (Google AI Studio)")
    print(f"{'='*60}\n")

    cleaner  = make_data_cleaner()
    stats    = make_stats_analyst_agent()
    viz      = make_viz_agent()

    clean_task = make_clean_task(filename, cleaner)
    stats_task = make_stats_task(stats, clean_task)
    viz_task   = make_viz_task(viz, stats_task)

    return Crew(
        agents=[cleaner, stats, viz],
        tasks=[clean_task, stats_task, viz_task],
        verbose=step_cb is None,   # verbose only in standalone CLI mode
        step_callback=step_cb,
        task_callback=task_cb,
    )


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CrewAI multi-agent research pipeline")
    parser.add_argument(
        "--topic", "-t",
        default="Artificial Intelligence in Healthcare",
        help="Research topic (default: 'Artificial Intelligence in Healthcare')",
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  CrewAI — Ibnu Al-Haytham Self-Critique Pipeline")
    print(f"  Topic: {args.topic}")
    search_provider = "LinkUp (deep)" if _linkup_key else ("Serper" if _serper_key else "DuckDuckGo (free)")
    print(f"  Search: {search_provider}")
    print(f"  Pipeline:")
    print(f"    [1] Drafter  → mistral-large-latest  (research + first draft)")
    print(f"    [2] Critic   → mistral-large-latest  (self-critique + refine)")
    print(f"{'='*60}\n")

    crew = build_crew(args.topic)
    result = crew.kickoff()

    print(f"\n{'='*60}")
    print("  FINAL OUTPUT")
    print(f"{'='*60}")
    print(result)
    print(f"\nFiles saved:")
    print("  task1_research.txt  — first draft (with flagged weak spots)")
    print("  task2_report.md     — critique notes + final refined article")


if __name__ == "__main__":
    main()
