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
# Main generation LLM — large model for deep reasoning
llm_large = _make_mistral_llm("mistral-large-latest", temperature=0.3)

# Fast LLM — small model for tool calls / function calling
llm_small = _make_mistral_llm("mistral-small-latest", temperature=0.1)

# ── Gemma4 LLMs (Google AI Studio) ────────────────────────────────────────────
# Model names can be overridden via .env: GEMMA4_MODEL / GEMMA4_2_MODEL
_gemma4_model   = os.getenv("GEMMA4_MODEL",   "gemma-4")
_gemma4_2_model = os.getenv("GEMMA4_2_MODEL", "gemma-4-2b-it")

llm_gemma4   = _make_gemma_llm(_gemma4_model,   "GEMMA4_API_KEY",   temperature=0.3)
llm_gemma4_2 = _make_gemma_llm(_gemma4_2_model, "GEMMA4_2_API_KEY", temperature=0.1)


# ── Tools ─────────────────────────────────────────────────────────────────────

# Prefer Serper (paid, higher quality) → fall back to DuckDuckGo (free)
_serper_key = os.getenv("SERPER_API_KEY", "")

if _serper_key:
    search_tool = SerperDevTool()
else:
    # Wrap DuckDuckGo as a CrewAI-compatible tool
    _ddg = DuckDuckGoSearchRun()

    class DuckDuckGoTool(BaseTool):
        name: str = "DuckDuckGo Search"
        description: str = (
            "Search the web for current information. "
            "Input should be a concise search query string."
        )

        def _run(self, query: str) -> str:
            return _ddg.run(query)

    search_tool = DuckDuckGoTool()

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
# Pipeline: Ibnu Al-Haytham (Drafter) → Ibnu Al-Haytham (Self-Critic)
#
# The same persona runs twice in different modes:
#   1. DRAFTER  — researches deeply and writes a first draft, flagging weak spots
#   2. CRITIC   — reads the draft with a skeptic's eye, identifies logic gaps and
#                 unsupported claims, then outputs a refined final article
#
# The user never sees the raw draft — only the critique notes + final version.

def make_drafter(topic: str) -> Agent:
    """Agent 1: research the topic and produce a first draft with self-flagged weak spots."""
    return Agent(
        llm=llm_large,
        function_calling_llm=llm_small,
        role="Ibnu Al-Haytham — Research Drafter",
        goal=(
            f"Riset topik '{topic}' secara mendalam lalu tulis draf pertama artikel. "
            "Draf boleh belum sempurna — tandai bagian yang argumennya masih lemah "
            "agar bisa diperbaiki pada tahap kritik."
        ),
        backstory=(
            "Kamu adalah Ibnu Al-Haytham dalam mode riset dan penulisan. "
            "Tugasmu di tahap ini adalah mengumpulkan sebanyak mungkin informasi yang "
            "relevan, akurat, dan terkini, lalu menuangkannya ke dalam draf pertama.\n\n"
            "Cara kerjamu:\n"
            "1. Mulai dengan pencarian luas untuk memetakan lanskap topik\n"
            "2. Lanjutkan dengan pencarian spesifik per aspek penting\n"
            "3. Kumpulkan fakta, data, kutipan ahli, kontroversi, dan contoh nyata\n"
            "4. Catat setiap URL sumber secara lengkap\n"
            "5. Tulis draf artikel yang mengalir — pembuka, isi, penutup\n\n"
            "Prinsip penting: setiap paragraf yang kamu rasa klaimnya masih tipis atau "
            "belum cukup didukung data, tambahkan penanda [⚠ PERLU DIKUATKAN] tepat di "
            "akhir paragraf tersebut. Ini bukan kelemahan — ini kejujuran intelektual "
            "yang akan membantu tahap kritik bekerja lebih efektif."
        ),
        tools=[search_tool, file_writer],
        allow_delegation=False,
        verbose=True,
        max_iter=15,
    )


def make_critic(topic: str) -> Agent:
    """Agent 2: critique the draft's logic and evidence, then output the refined final article."""
    return Agent(
        llm=llm_large,
        role="Ibnu Al-Haytham — Self-Critic & Logic Refiner",
        goal=(
            f"Baca draf pertama tentang '{topic}' dengan mata skeptis. "
            "Identifikasi setiap celah logika, klaim tanpa bukti, dan argumen lemah. "
            "Hasilkan versi final yang lebih tajam, lebih jujur, dan lebih terpercaya."
        ),
        backstory=(
            "Kamu adalah Ibnu Al-Haytham — tapi sekarang kamu mengenakan topi kritik. "
            "Kamu baru saja menyelesaikan draf pertama, dan sekarang kamu membacanya ulang "
            "bukan sebagai penulisnya, melainkan sebagai pembaca yang paling kritis.\n\n"
            "Pertanyaan yang selalu kamu tanyakan pada tulisanmu sendiri:\n"
            "- Apakah klaim ini benar-benar didukung bukti yang memadai?\n"
            "- Apakah logika dari A → B → C benar-benar mengalir tanpa lompatan?\n"
            "- Adakah perspektif penting yang sengaja atau tidak sengaja diabaikan?\n"
            "- Apakah ada generalisasi berlebihan ('selalu', 'semua', 'tidak pernah')?\n"
            "- Bagian mana yang akan langsung dipertanyakan pembaca kritis?\n"
            "- Apakah bagian yang ditandai [⚠ PERLU DIKUATKAN] sudah ditangani?\n\n"
            "Setelah mengidentifikasi masalah, kamu tidak berhenti di daftar kritik — "
            "kamu langsung memperbaiki setiap masalah. Jika suatu klaim tidak bisa "
            "dikuatkan, kamu hapus atau ubah menjadi pernyataan yang lebih hati-hati "
            "('cenderung', 'dalam banyak kasus', 'ada indikasi bahwa'). "
            "Output akhirmu adalah artikel yang lebih tajam, lebih logis, dan lebih "
            "jujur tentang batas antara yang sudah pasti vs. yang masih spekulatif."
        ),
        tools=[file_writer],
        allow_delegation=False,
        verbose=True,
        max_iter=6,
    )


# ── Task Factory ──────────────────────────────────────────────────────────────

def make_draft_task(topic: str, agent: Agent) -> Task:
    """Task 1: deep research + first draft with self-flagged weak spots."""
    return Task(
        description=(
            f"Lakukan riset mendalam tentang **{topic}**, lalu tulis draf pertama artikel.\n\n"
            "FASE 1 — RISET (gunakan search tool):\n"
            "1. Lakukan 2-3 pencarian luas untuk memetakan topik secara umum\n"
            f"   - '{topic}', '{topic} terbaru / latest', '{topic} data / statistik'\n"
            "2. Identifikasi 4-5 aspek utama topik ini, riset masing-masing secara spesifik "
            "(minimal 2 pencarian per aspek)\n"
            "3. Kumpulkan: fakta kuantitatif, kutipan ahli, contoh nyata, kontroversi jika ada\n"
            "4. Catat setiap URL sumber — nama sumber, URL lengkap, poin utama\n\n"
            "FASE 2 — TULIS DRAF PERTAMA:\n"
            "Berdasarkan riset, tulis artikel naratif dengan struktur:\n"
            "- Pembuka yang langsung menarik perhatian (fakta mengejutkan / pertanyaan)\n"
            "- Isi yang mengalir per aspek utama, paragraf pendek, bahasa natural\n"
            "- Sumber disebutkan secara natural dalam teks ('menurut [sumber]...')\n"
            "- Penutup dengan insight utama\n"
            "- Bagian Sumber Referensi di akhir\n\n"
            "PENANDA KEJUJURAN INTELEKTUAL:\n"
            "Setiap paragraf yang klaimnya masih tipis atau datanya belum kuat, "
            "tambahkan [⚠ PERLU DIKUATKAN] di akhir paragraf tersebut.\n\n"
            "Simpan draf menggunakan file_writer."
        ),
        expected_output=(
            "Draf pertama artikel Bahasa Indonesia (600-900 kata) berisi:\n"
            "- Narasi lengkap: pembuka, isi per aspek utama, penutup\n"
            "- Sumber disebutkan natural dalam teks\n"
            "- Penanda [⚠ PERLU DIKUATKAN] di paragraf yang masih lemah\n"
            "- Bagian Sumber Referensi di akhir dengan minimal 8 URL\n"
            "Disimpan ke task1_research.txt"
        ),
        agent=agent,
        output_file=str(_research_dir() / "task1_research.txt"),
    )


def make_critique_task(topic: str, agent: Agent, draft_task: Task) -> Task:
    """Task 2: self-critique the draft's logic then produce the polished final article."""
    return Task(
        description=(
            f"Baca draf pertama artikel tentang **{topic}** dan lakukan kritik menyeluruh, "
            "lalu hasilkan versi final yang sudah disempurnakan.\n\n"
            "LANGKAH 1 — KRITIK DRAF:\n"
            "Periksa setiap bagian dan buat daftar masalah yang ditemukan:\n"
            "- Klaim yang tidak didukung bukti memadai (termasuk semua [⚠ PERLU DIKUATKAN])\n"
            "- Lompatan logika (dari premis A langsung ke kesimpulan C tanpa jembatan B)\n"
            "- Generalisasi berlebihan: 'selalu', 'semua', 'tidak pernah', 'pasti'\n"
            "- Perspektif penting yang hilang atau diabaikan\n"
            "- Urutan atau struktur narasi yang mengganggu alur baca\n"
            "- Istilah atau konsep yang tidak dijelaskan tapi diasumsikan dipahami\n\n"
            "LANGKAH 2 — PERBAIKAN DAN PENULISAN FINAL:\n"
            "Tulis versi artikel yang sudah diperbaiki:\n"
            "- Kuatkan argumen lemah, atau ganti dengan pernyataan yang lebih berhati-hati\n"
            "- Isi celah logika dengan penjelasan yang jelas\n"
            "- Hapus klaim yang tidak bisa diverifikasi sama sekali\n"
            "- Tambahkan nuansa di tempat yang perlu: 'cenderung', 'dalam banyak kasus', "
            "'ada indikasi bahwa', 'beberapa peneliti berpendapat'\n"
            "- Pertahankan gaya bahasa natural dan mudah dibaca\n\n"
            "FORMAT OUTPUT WAJIB:\n"
            "## CATATAN KRITIK\n"
            "[Daftar masalah yang ditemukan beserta tindakan perbaikan spesifik]\n\n"
            "---\n\n"
            "## ARTIKEL FINAL\n"
            "[Artikel lengkap yang sudah disempurnakan]\n\n"
            "## Sumber Referensi\n"
            "[Daftar URL dari draf]\n\n"
            "Simpan menggunakan file_writer."
        ),
        expected_output=(
            "Dokumen dua bagian:\n"
            "1. CATATAN KRITIK — daftar masalah logika/bukti yang ditemukan dan "
            "tindakan perbaikan konkret untuk masing-masing\n"
            "2. ARTIKEL FINAL — versi yang sudah disempurnakan, logis, berimbang, "
            "700-1000 kata, bahasa Indonesia natural\n"
            "Disimpan ke task2_report.md"
        ),
        agent=agent,
        context=[draft_task],
        output_file=str(_research_dir() / "task2_report.md"),
    )


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
    search_provider = "Serper" if _serper_key else "DuckDuckGo (free)"
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
