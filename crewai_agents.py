"""
Multi-Agent System with CrewAI + Mistral AI
============================================

Pipeline 1 — Research (7 agents):  Scout → Filter → [IdeaGen ‖ Validator] → Synthesizer → Critic → Writer
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
if _serper_key:
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
    """Read a phase output file from research dir; return empty string if missing or unreadable."""
    p = _research_dir() / fname
    try:
        return p.read_text(encoding="utf-8") if p.exists() else ""
    except OSError:
        return ""


def make_scout(topic: str) -> Agent:
    """Phase 1-A: broad survey + auto-detect research mode."""
    return Agent(
        llm=llm_small,
        function_calling_llm=llm_small,
        role="Ibn Al-Haytham — Research Scout",
        goal=(
            f"Analyze the topic '{topic}', declare the research mode "
            "(ACADEMIC / GENERAL / HYBRID), then perform a broad initial survey "
            "to map the landscape."
        ),
        backstory=(
            "You are Ibn Al-Haytham in reconnaissance mode. Before deep research begins, "
            "you survey the terrain.\n\n"
            "Your first decision is the research mode:\n"
            "  [MODE: ACADEMIC] — topic is scientific, medical, mathematical, or engineering\n"
            "  [MODE: GENERAL]  — topic is business, culture, current events, or social\n"
            "  [MODE: HYBRID]   — topic spans both (AI, tech policy, digital health, etc.)\n\n"
            "After declaring the mode, run 3–5 broad searches:\n"
            "- Key players, institutions, and authors in this space\n"
            "- Major debates, controversies, or open questions\n"
            "- Timeline: when did this emerge, what are recent developments?\n"
            "- ACADEMIC mode: which databases have coverage (arXiv, PubMed, IEEE)?\n"
            "- GENERAL mode: which outlets cover this best (news, industry, think-tanks)?\n\n"
            "Output a structured topic map:\n"
            "1. [MODE: X] declaration — first line, always\n"
            "2. Landscape summary — 5–8 bullet points\n"
            "3. Key search terms for deeper research — 6–10 terms\n"
            "4. Initial sources found — URL + title + one-line note"
        ),
        tools=[research_search_tool],
        allow_delegation=False,
        verbose=True,
        max_iter=8,
    )


def make_filter_agent(topic: str) -> Agent:
    """Phase 1-B: evaluate Scout sources, curate 10–15 best."""
    return Agent(
        llm=llm_small,
        function_calling_llm=llm_small,
        role="Ibn Al-Haytham — Source Curator",
        goal=(
            f"Evaluate the sources discovered by Scout for '{topic}', "
            "score each by relevance and quality, and curate the 10–15 strongest."
        ),
        backstory=(
            "You are Ibn Al-Haytham's quality gate. You evaluate what Scout found "
            "and select only the best. You may run additional targeted searches if "
            "Scout found fewer than 10 quality sources.\n\n"
            "Scoring criteria:\n"
            "  - Relevance to the specific topic (1–5)\n"
            "  - Source tier: [PRIMARY] peer-reviewed/official, "
            "[SECONDARY] expert commentary, [TERTIARY] blogs/forums\n"
            "  - Recency: prefer < 3 years unless foundational\n"
            "  - ACADEMIC mode: prioritise peer-reviewed papers\n"
            "  - GENERAL mode: prioritise authoritative outlets and recent reports\n\n"
            "Output format:\n"
            "## Curated Sources (10–15)\n"
            "[SOURCE N] Title | URL | [TIER] | Relevance: X/5 | One-line summary\n\n"
            "## Research Focus\n"
            "[3–4 bullet points: the most important angles to investigate next]"
        ),
        tools=[research_search_tool],
        allow_delegation=False,
        verbose=True,
        max_iter=6,
    )


def make_idea_gen(topic: str) -> Agent:
    """Phase 2-A (parallel): generate novel angles and hypotheses."""
    return Agent(
        llm=llm_gemma4,
        role="Ibn Al-Haytham — Idea Generator",
        goal=(
            f"Based on curated sources about '{topic}', generate 4–6 novel research "
            "angles, hypotheses, and non-obvious connections."
        ),
        backstory=(
            "You are Ibn Al-Haytham's creative mind. You read the curated sources and ask:\n"
            "- What is the most interesting question this research hasn't answered yet?\n"
            "- What connection between two sources hasn't been made explicit?\n"
            "- What hypothesis, if true, would change how we think about this topic?\n"
            "- What angle is conspicuously absent from mainstream coverage?\n\n"
            "For each idea:\n"
            "IDEA N: [Title]\n"
            "Type: [Novel connection / Research gap / Hypothesis / Counter-narrative]\n"
            "Argument: [2–3 sentences explaining the idea]\n"
            "Evidence basis: [which SOURCE N supports this, even partially]\n"
            "Confidence: [High / Medium / Speculative]\n\n"
            "Produce 4–6 ideas. Label speculative ideas clearly. "
            "Do not hedge excessively — the Validator checks evidence independently."
        ),
        tools=[research_search_tool],
        allow_delegation=False,
        verbose=True,
        max_iter=8,
    )


def make_validator_agent(topic: str) -> Agent:
    """Phase 2-B (parallel): cross-check claims, flag weak evidence."""
    return Agent(
        llm=llm_gemma4,
        role="Ibn Al-Haytham — Evidence Validator",
        goal=(
            f"Cross-check claims in the curated sources about '{topic}', "
            "flag weak evidence with [⚠], and identify contradictions."
        ),
        backstory=(
            "You are Ibn Al-Haytham's skeptic. You read the same curated sources as "
            "IdeaGen but your job is the opposite: find what is NOT well-supported.\n\n"
            "For each major claim, ask:\n"
            "- Is this corroborated by at least 2 independent sources?\n"
            "- Is the methodology sound?\n"
            "- Does this contradict another source? Which is more credible?\n"
            "- Is this outdated — superseded by newer research?\n\n"
            "Output format:\n"
            "## VALIDATED CLAIMS\n"
            "[✓] Claim | Source N, Source M | Confidence\n\n"
            "## WEAK / CONTESTED CLAIMS\n"
            "[⚠] Claim | Why weak | What would strengthen it\n\n"
            "## CONTRADICTIONS\n"
            "[↔] Source A says X vs Source B says Y | Recommended resolution\n\n"
            "## DATA GAPS\n"
            "[?] Important question with no good source\n\n"
            "Never validate a claim that appears in only one source. "
            "If you cannot verify, flag [⚠]. Do not fabricate validation."
        ),
        tools=[research_search_tool],
        allow_delegation=False,
        verbose=True,
        max_iter=8,
    )


def make_synthesizer(topic: str) -> Agent:
    """Phase 3-A: merge IdeaGen + Validator outputs into unified narrative."""
    return Agent(
        llm=llm_large,
        role="Ibn Al-Haytham — Synthesizer",
        goal=(
            f"Merge the IdeaGen and Validator outputs about '{topic}' into a unified, "
            "coherent narrative that honours both creativity and evidentiary rigour."
        ),
        backstory=(
            "You bridge Ibn Al-Haytham's two parallel minds — creative IdeaGen and "
            "skeptical Validator. Weave their outputs into a single coherent narrative.\n\n"
            "Process:\n"
            "1. For each IDEA from IdeaGen, check what Validator said about underlying claims:\n"
            "   - VALIDATED claims → present confidently\n"
            "   - WEAK [⚠] claims → hedge ('suggests', 'may indicate', 'in some cases')\n"
            "   - CONTRADICTED claims → resolve explicitly or drop the idea\n"
            "2. Include all DATA GAPS from Validator as an Open Questions section\n"
            "3. Write a flowing memo (not a list): overview → key findings → "
            "contested areas → novel angles → open questions\n\n"
            "The synthesis will be critiqued next — be honest about uncertainty. "
            "This memo should read like a well-structured research brief, not a list."
        ),
        tools=[],
        allow_delegation=False,
        verbose=True,
        max_iter=8,
    )


def make_critic_agent(topic: str) -> Agent:
    """Phase 3-B: logic review + self-critique of synthesis."""
    return Agent(
        llm=llm_large,
        role="Ibn Al-Haytham — Logic Critic",
        goal=(
            f"Review the synthesized narrative about '{topic}' for logical gaps, "
            "over-generalizations, and residual unsupported claims. Output critique "
            "notes + refined synthesis."
        ),
        backstory=(
            "You are Ibn Al-Haytham's most demanding peer reviewer. You've just read "
            "the synthesis and now you read it again as a skeptic.\n\n"
            "Check every paragraph for:\n"
            "- Logical leaps (A → C without establishing B)\n"
            "- Over-generalizations: 'always', 'all', 'never', 'obviously', 'clearly'\n"
            "- Residual [⚠] weak claims that still appear as facts\n"
            "- Missing perspectives or systematic blind spots\n"
            "- Structural breaks in reading flow\n\n"
            "Format your output:\n"
            "## CATATAN KRITIK\n"
            "[Issue N]: [location] → [problem] → [fix applied]\n\n"
            "---\n\n"
            "## SINTESIS YANG DISEMPURNAKAN\n"
            "[Full refined synthesis with all issues corrected]\n\n"
            "Key rule: soften, do not remove. Replace 'X causes Y' with "
            "'X is associated with Y' where causation is unproven."
        ),
        tools=[],
        allow_delegation=False,
        verbose=True,
        max_iter=6,
    )


def make_writer(topic: str) -> Agent:
    """Phase 3-C: write final article with inline citations and reference list."""
    return Agent(
        llm=llm_large,
        role="Ibn Al-Haytham — Academic Writer",
        goal=(
            f"Write the final article about '{topic}' with inline citations [Ref N] "
            "and a complete reference list. Save it using file_writer."
        ),
        backstory=(
            "You are Ibn Al-Haytham at the writing desk. Research is done, logic is "
            "checked — now you write the definitive article.\n\n"
            "Structure:\n"
            "# [Descriptive title]\n"
            "**Research Mode:** [ACADEMIC / GENERAL / HYBRID]\n"
            "**Date:** [today's date]\n"
            "**Confidence:** [High / Medium / Low] — [one-line rationale]\n\n"
            "## Ringkasan Eksekutif\n"
            "[3–5 sentences answering the core question directly]\n\n"
            "## Temuan Utama\n"
            "[Numbered: bold claim → explanation → [Ref N]]\n\n"
            "## [Thematic sections — 2–4, based on the synthesis]\n"
            "[Flowing prose, every factual claim cited with [Ref N]]\n\n"
            "## Pertanyaan Terbuka & Celah Riset\n"
            "[From Validator's DATA GAPS — what remains unknown or contested]\n\n"
            "## Referensi\n"
            "[N] Author. 'Title'. Journal/Outlet, Year. URL: <full clickable URL>\n\n"
            "Rules:\n"
            "- 800–1200 words for the main body\n"
            "- Minimum 8 references, 5+ must be primary sources with full URLs\n"
            "- Every factual claim must have [Ref N]\n"
            "- Language: Bahasa Indonesia if topic was asked in Indonesian, English otherwise"
        ),
        tools=[file_writer],
        allow_delegation=False,
        verbose=True,
        max_iter=8,
    )


# ── Task Factories ───────────────────────────────────────────────────────────

def make_scout_task(topic: str, agent: Agent) -> Task:
    """Phase 1-A task: survey + mode declaration."""
    return Task(
        description=(
            f"Survey **{topic}** and produce a structured topic map.\n\n"
            "STEP 1 — DECLARE MODE (first output line, always):\n"
            f"Is '{topic}' primarily academic/scientific → [MODE: ACADEMIC], "
            "general/social/business → [MODE: GENERAL], or both → [MODE: HYBRID]?\n\n"
            "STEP 2 — BROAD SURVEY (3–5 searches):\n"
            f"Search: '{topic}', '{topic} overview', '{topic} latest research', "
            f"'{topic} key players'\n"
            "ACADEMIC: also search '{topic} site:arxiv.org', "
            "'{topic} site:pubmed.ncbi.nlm.nih.gov'\n"
            "GENERAL: also search '{topic} news 2024 2025', '{topic} industry report'\n\n"
            "STEP 3 — OUTPUT:\n"
            "[MODE: X]\n\n"
            "## Landscape Overview\n"
            "- [5–8 bullets: key facts, players, debates, timeline]\n\n"
            "## Key Search Terms for Deeper Research\n"
            "- [6–10 specific terms]\n\n"
            "## Initial Sources\n"
            "[SOURCE 1] Title | URL | Brief note\n"
            "[SOURCE 2] ..."
        ),
        expected_output=(
            "Structured topic map with [MODE: X] on first line, landscape overview "
            "(5–8 bullets), key search terms (6–10), and initial sources with URLs."
        ),
        agent=agent,
        output_file=str(_research_dir() / "task1_scout.txt"),
    )


def make_filter_task(topic: str, agent: Agent, scout_task: Task) -> Task:
    """Phase 1-B task: curate 10–15 best sources from Scout's findings."""
    return Task(
        description=(
            f"Evaluate and curate sources for **{topic}** from Scout's output.\n\n"
            "STEP 1 — SCORE EACH SOURCE from context:\n"
            "  Tier: [PRIMARY] / [SECONDARY] / [TERTIARY]\n"
            "  Relevance: 1–5\n"
            "  Recency: current (<2 yr) / dated (2–5 yr) / foundational (older, seminal)\n\n"
            "STEP 2 — SUPPLEMENT IF NEEDED:\n"
            "If fewer than 10 quality sources found, run targeted searches:\n"
            f"  ACADEMIC: '{topic} site:arxiv.org', '{topic} peer reviewed 2023 2024'\n"
            f"  GENERAL:  '{topic} report 2024', '{topic} analysis expert'\n\n"
            "STEP 3 — OUTPUT:\n"
            "## Curated Sources (10–15)\n"
            "[SOURCE N] Title | URL | [TIER] | Relevance: X/5 | One-line summary\n\n"
            "## Research Focus\n"
            "[3–4 bullets: the most important angles to investigate in Phase 2]"
        ),
        expected_output=(
            "Curated list of 10–15 sources with tier, relevance score, URL, and summary. "
            "Plus a Research Focus section with 3–4 key angles."
        ),
        agent=agent,
        context=[scout_task],
        output_file=str(_research_dir() / "task2_filter.txt"),
    )


def make_idea_task(topic: str, agent: Agent, filter_context: str) -> Task:
    """Phase 2-A task: generate novel angles from curated sources."""
    ctx = filter_context[:4000] if filter_context else "[No filter context available]"
    return Task(
        description=(
            f"Based on the curated sources below for **{topic}**, generate 4–6 novel "
            "research angles and hypotheses.\n\n"
            f"--- CURATED SOURCES ---\n{ctx}\n--- END ---\n\n"
            "For each idea:\n"
            "IDEA N: [Title]\n"
            "Type: [Novel connection / Research gap / Hypothesis / Counter-narrative]\n"
            "Argument: [2–3 sentences]\n"
            "Evidence basis: [which SOURCE N supports this]\n"
            "Confidence: [High / Medium / Speculative]\n\n"
            "Produce exactly 4–6 ideas. Label speculative ideas clearly. "
            "The Validator checks evidence independently — do not over-hedge."
        ),
        expected_output=(
            "4–6 structured ideas, each with: title, type, 2–3 sentence argument, "
            "evidence basis (SOURCE N references), and confidence level."
        ),
        agent=agent,
        output_file=str(_research_dir() / "task3a_ideas.txt"),
    )


def make_valid_task(topic: str, agent: Agent, filter_context: str) -> Task:
    """Phase 2-B task: cross-check claims in curated sources."""
    ctx = filter_context[:4000] if filter_context else "[No filter context available]"
    return Task(
        description=(
            f"Cross-check the claims in these curated sources about **{topic}**.\n\n"
            f"--- CURATED SOURCES ---\n{ctx}\n--- END ---\n\n"
            "Produce four sections:\n\n"
            "## VALIDATED CLAIMS\n"
            "[✓] Claim | Source N, Source M | Confidence level\n\n"
            "## WEAK / CONTESTED CLAIMS\n"
            "[⚠] Claim | Why weak | What would strengthen it\n\n"
            "## CONTRADICTIONS\n"
            "[↔] Source A says X vs Source B says Y | Recommended resolution\n\n"
            "## DATA GAPS\n"
            "[?] Important question with no good source available\n\n"
            "Rules: do not validate a claim from only one source. "
            "Do not fabricate validation — if unverifiable, flag [⚠]."
        ),
        expected_output=(
            "Four sections: validated claims [✓], weak/contested claims [⚠], "
            "contradictions [↔], and data gaps [?]."
        ),
        agent=agent,
        output_file=str(_research_dir() / "task3b_validation.txt"),
    )


# ── Crew Builder ──────────────────────────────────────────────────────────────

def build_crew(topic: str, step_cb=None, task_cb=None):
    """7-agent Ibn Al-Haytham hybrid research pipeline — scaffold stub.

    Full implementation added in Task 8 (IbnAlHaythamPipeline).
    """
    raise NotImplementedError(
        "build_crew() is a scaffold stub — IbnAlHaythamPipeline not yet wired up. "
        "Tasks 2–8 must be completed first."
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
