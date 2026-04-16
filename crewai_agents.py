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


# ── Agent Factory ─────────────────────────────────────────────────────────────

def make_researcher(topic: str) -> Agent:
    return Agent(
        llm=llm_large,
        function_calling_llm=llm_small,
        role="Ibnu Al-Haytham — Deep Research Specialist",
        goal=(
            f"Lakukan riset mendalam dan menyeluruh tentang: {topic}. "
            "Kumpulkan sebanyak mungkin informasi yang relevan, akurat, dan terkini. "
            "Sertakan semua URL sumber web yang digunakan secara lengkap. "
            "Gali lebih dalam — temukan fakta, data, pendapat ahli, dan perspektif yang beragam."
        ),
        backstory=(
            "Kamu adalah Ibnu Al-Haytham, peneliti independen yang dikenal karena ketelitian "
            "dan kedalamannya dalam mencari informasi. Kamu tidak puas dengan jawaban dangkal. "
            "Setiap klaim yang kamu buat harus didukung oleh sumber yang jelas.\n\n"
            "Cara kerjamu:\n"
            "1. Mulai dengan pencarian luas untuk memetakan lanskap topik\n"
            "2. Lanjutkan dengan pencarian spesifik per aspek penting dari topik\n"
            "3. Kumpulkan fakta, data, kutipan, dan opini dari berbagai sudut pandang\n"
            "4. Catat setiap URL sumber — judul halaman, URL lengkap, poin utama dari sumber tersebut\n"
            "5. Jika menemukan informasi yang bertentangan antar sumber, catat keduanya\n\n"
            "Kamu menghasilkan bahan mentah riset yang lengkap dan siap diolah menjadi narasi."
        ),
        tools=[search_tool],
        allow_delegation=False,
        verbose=True,
        max_iter=12,
    )


def make_writer(topic: str) -> Agent:
    return Agent(
        llm=llm_large,
        role="Narator & Penulis Konten",
        goal=(
            f"Ubah hasil riset tentang '{topic}' menjadi tulisan yang enak dibaca, "
            "mengalir secara natural, dan mudah dipahami oleh pembaca awam sekalipun. "
            "Sajikan informasi secara naratif — bukan daftar poin kering, "
            "melainkan cerita yang informatif dan engaging."
        ),
        backstory=(
            "Kamu adalah penulis konten berpengalaman yang mahir mengubah data dan fakta "
            "mentah menjadi tulisan yang hidup dan mudah dicerna. Gayamu hangat, mengalir, "
            "dan tidak kaku — seperti menjelaskan kepada teman yang ingin tahu tapi bukan "
            "seorang ahli di bidang tersebut.\n\n"
            "Prinsipmu:\n"
            "- Gunakan bahasa yang natural dan mudah dipahami, hindari jargon yang tidak perlu\n"
            "- Bangun narasi dengan alur: pembuka yang menarik, isi yang mengalir, penutup berkesan\n"
            "- Setiap klaim penting tetap dilengkapi sumber (nama situs atau URL singkat)\n"
            "- Prioritaskan keterbacaan — pembaca harus bisa memahami tanpa effort berlebih\n"
            "- Gunakan analogi atau contoh konkret untuk memperjelas konsep yang kompleks"
        ),
        tools=[file_writer],
        allow_delegation=False,
        verbose=True,
        max_iter=5,
    )


# ── Task Factory ──────────────────────────────────────────────────────────────

def make_research_task(topic: str, agent: Agent) -> Task:
    return Task(
        description=(
            f"Lakukan riset mendalam tentang topik berikut: **{topic}**\n\n"
            "Ikuti langkah-langkah ini:\n\n"
            "1. PENCARIAN AWAL — Mulai dengan 2-3 pencarian luas untuk memetakan topik:\n"
            f"   - Cari '{topic}' untuk gambaran umum\n"
            f"   - Cari '{topic} terbaru' atau '{topic} latest' untuk perkembangan terkini\n"
            f"   - Cari '{topic} data' atau '{topic} statistik' untuk angka dan fakta\n\n"
            "2. PENGGALIAN MENDALAM — Identifikasi 4-5 aspek penting dari topik ini dan "
            "lakukan pencarian spesifik untuk setiap aspek. Minimal 2-3 pencarian per aspek.\n\n"
            "3. PENGUMPULAN SUMBER — Untuk setiap informasi penting yang ditemukan, catat:\n"
            "   - Fakta atau data utama yang ditemukan\n"
            "   - URL sumber lengkap\n"
            "   - Nama/judul sumber tersebut\n\n"
            "4. PERSPEKTIF BERAGAM — Pastikan kamu mengumpulkan:\n"
            "   - Fakta dan data kuantitatif\n"
            "   - Opini atau analisis dari pakar/ahli\n"
            "   - Contoh nyata atau studi kasus jika ada\n"
            "   - Kontroversi atau perdebatan yang relevan jika ada\n\n"
            "Berikan temuan selengkap mungkin agar penulis punya bahan yang kaya."
        ),
        expected_output=(
            "Dokumen riset lengkap berisi:\n"
            "- Temuan utama per aspek topik, dengan penjelasan detail\n"
            "- Semua fakta, data, dan kutipan penting yang ditemukan\n"
            "- Daftar sumber: [Nama Sumber] — [URL] — [Poin utama dari sumber ini]\n"
            "- Minimal 8-12 sumber web berbeda\n"
            "- Catatan jika ada informasi yang bertentangan antar sumber\n"
            "Hasil riset harus komprehensif dan siap dijadikan dasar narasi yang kaya."
        ),
        agent=agent,
        output_file=str(_research_dir() / "task1_research.txt"),
    )


def make_writing_task(topic: str, agent: Agent, research_task: Task) -> Task:
    return Task(
        description=(
            f"Berdasarkan hasil riset yang telah dikumpulkan tentang **{topic}**, "
            "tulislah artikel naratif yang informatif dan enak dibaca.\n\n"
            "STRUKTUR TULISAN:\n"
            "1. Pembuka yang menarik — mulai dengan fakta mengejutkan, pertanyaan, atau "
            "konteks yang langsung menarik perhatian pembaca\n"
            "2. Isi yang mengalir — sajikan informasi secara berurutan dan logis, "
            "gunakan paragraf pendek, bangun dari konsep sederhana ke yang lebih kompleks\n"
            "3. Sisipkan sumber secara natural — tulis '...menurut [nama sumber]...' atau "
            "'...berdasarkan data dari [sumber]...' bukan footnote kaku\n"
            "4. Penutup yang berkesan — simpulkan dengan insight utama atau pertanyaan "
            "yang membuat pembaca berpikir lebih jauh\n\n"
            "GAYA PENULISAN:\n"
            "- Tulis seperti menjelaskan kepada teman cerdas yang bukan ahli di bidang ini\n"
            "- Gunakan bahasa Indonesia yang natural, tidak kaku, tidak akademis\n"
            "- Boleh campur istilah asing jika lebih tepat, tapi jelaskan artinya\n"
            "- Gunakan analogi atau contoh konkret untuk hal-hal yang abstrak\n"
            "- Hindari terlalu banyak bullet point — utamakan kalimat yang mengalir\n\n"
            "Di akhir artikel, sertakan bagian **Sumber Referensi** dengan daftar "
            "semua URL yang digunakan, format: - [Nama Sumber] — [URL]"
        ),
        expected_output=(
            "Artikel naratif dalam Bahasa Indonesia (600-1000 kata) yang:\n"
            "- Enak dan mudah dibaca oleh pembaca awam\n"
            "- Informatif dan berbasis fakta dari hasil riset\n"
            "- Mengalir natural dengan pembuka, isi, dan penutup yang jelas\n"
            "- Menyebutkan sumber secara natural dalam teks\n"
            "- Diakhiri bagian Sumber Referensi berisi daftar URL lengkap"
        ),
        agent=agent,
        context=[research_task],
        output_file=str(_research_dir() / "task2_report.md"),
    )


# ── Crew Builder ──────────────────────────────────────────────────────────────

def build_crew(topic: str, step_cb=None, task_cb=None) -> Crew:
    researcher = make_researcher(topic)
    writer     = make_writer(topic)

    research_task = make_research_task(topic, researcher)
    writing_task  = make_writing_task(topic, writer, research_task)

    return Crew(
        agents=[researcher, writer],
        tasks=[research_task, writing_task],
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
    print(f"  CrewAI Research Pipeline — Multi-LLM")
    print(f"  Topic: {args.topic}")
    search_provider = "Serper" if _serper_key else "DuckDuckGo (free)"
    print(f"  Search: {search_provider}")
    print(f"  LLMs:")
    print(f"    Researcher  → mistral-large-latest  (Mistral Cloud)")
    print(f"    Writer      → mistral-large-latest  (Mistral Cloud)")
    print(f"{'='*60}\n")

    crew = build_crew(args.topic)
    result = crew.kickoff()

    print(f"\n{'='*60}")
    print("  FINAL OUTPUT")
    print(f"{'='*60}")
    print(result)
    print(f"\nFiles saved:")
    print("  task1_research.txt  — raw research findings")
    print("  task2_report.md     — final polished report")


if __name__ == "__main__":
    main()
