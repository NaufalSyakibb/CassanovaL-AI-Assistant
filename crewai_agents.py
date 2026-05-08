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
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime
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


# ── Mistral LLMs (cloud) ───────────────────────────────────────────────────────
llm_large = _make_mistral_llm("mistral-large-latest", temperature=0.3)
llm_small = _make_mistral_llm("mistral-small-latest", temperature=0.1)


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


# Semantic Scholar article search tool — finds academic papers with direct URLs
class SemanticScholarSearchTool(BaseTool):
    name: str = "Semantic Scholar Article Search"
    description: str = (
        "Search Semantic Scholar for academic articles, research papers, and journal publications. "
        "Returns title, authors, year, venue/journal, abstract snippet, and a direct URL to the paper. "
        "Use this to find peer-reviewed articles and research publications. "
        "Input: a concise search query string."
    )

    def _run(self, query: str) -> str:
        import time
        try:
            params = {
                "query": query,
                "limit": 8,
                "fields": "title,authors,year,venue,url,externalIds,abstract",
            }
            for attempt in range(3):
                resp = requests.get(
                    "https://api.semanticscholar.org/graph/v1/paper/search",
                    params=params,
                    timeout=15,
                    headers={"User-Agent": "CassanovaL-Research/1.0"},
                )
                if resp.status_code == 429:
                    time.sleep(10 * (attempt + 1))
                    continue
                resp.raise_for_status()
                break
            else:
                return f"Semantic Scholar rate limit reached for query: {query}. Try again shortly."
            data = resp.json()
            papers = data.get("data", [])
            total  = data.get("total", 0)
            if not papers:
                return f"No articles found on Semantic Scholar for query: {query}"
            lines = [f"Semantic Scholar results for '{query}' ({total} total):\n"]
            for i, p in enumerate(papers, 1):
                title   = p.get("title", "Unknown Title")
                authors = ", ".join(a.get("name", "") for a in p.get("authors", [])[:3])
                if len(p.get("authors", [])) > 3:
                    authors += " et al."
                year    = p.get("year", "N/A")
                venue   = p.get("venue", "") or "Preprint"
                url     = p.get("url", "")
                ext_ids = p.get("externalIds", {})
                doi     = ext_ids.get("DOI", "")
                arxiv   = ext_ids.get("ArXiv", "")
                if not url and doi:
                    url = f"https://doi.org/{doi}"
                elif not url and arxiv:
                    url = f"https://arxiv.org/abs/{arxiv}"
                abstract = (p.get("abstract") or "")[:200].replace("\n", " ")
                if len(p.get("abstract") or "") > 200:
                    abstract += "..."
                lines.append(
                    f"[SS-{i}] {title}\n"
                    f"  Author: {authors} | Year: {year} | Venue: {venue}\n"
                    f"  URL: {url}\n"
                    + (f"  DOI: {doi}\n" if doi else "")
                    + (f"  Abstract: {abstract}\n" if abstract else "")
                )
            return "\n".join(lines)
        except Exception as e:
            return f"Semantic Scholar search error: {e}"


semantic_scholar_tool = SemanticScholarSearchTool()


# OpenLibrary book/thesis search tool — available to all research agents
class OpenLibrarySearchTool(BaseTool):
    name: str = "OpenLibrary Book Search"
    description: str = (
        "Search OpenLibrary for books, academic texts, and theses related to a topic. "
        "Returns title, author, year, language, and a direct URL to the work. "
        "Use this to find book-length references and classic academic texts. "
        "Input: a concise search query string."
    )

    def _run(self, query: str) -> str:
        try:
            params = {"q": query, "limit": 8, "fields": "key,title,author_name,first_publish_year,language,edition_count,has_fulltext,ebook_access"}
            resp = requests.get(
                "https://openlibrary.org/search.json",
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            docs = data.get("docs", [])
            if not docs:
                return f"No results found on OpenLibrary for query: {query}"
            lines = [f"OpenLibrary results for '{query}' ({data.get('numFound', 0)} total):\n"]
            for i, doc in enumerate(docs, 1):
                title   = doc.get("title", "Unknown Title")
                authors = ", ".join(doc.get("author_name", ["Unknown Author"]))
                year    = doc.get("first_publish_year", "N/A")
                key     = doc.get("key", "")
                url     = f"https://openlibrary.org{key}" if key else "N/A"
                langs   = ", ".join(doc.get("language", [])[:3])
                access  = doc.get("ebook_access", "unknown")
                editions = doc.get("edition_count", 1)
                lines.append(
                    f"[OL-{i}] {title}\n"
                    f"  Author: {authors} | Year: {year} | Editions: {editions}\n"
                    f"  Language: {langs} | Access: {access}\n"
                    f"  URL: {url}\n"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"OpenLibrary search error: {e}"


openlibrary_tool = OpenLibrarySearchTool()


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


# ── Academic Swarm helpers ────────────────────────────────────────────────────

def _classify_topic(topic: str) -> dict:
    """Al-Biruni: direct Mistral call to classify topic depth.

    Returns {"mode": "quick"|"deep"|"academic", "rationale": str, "angles": [str, ...]}
    """
    import json as _json
    prompt = (
        f'You are Al-Biruni, a research orchestrator. Classify this topic: "{topic}"\n\n'
        "Reply with ONLY this JSON (no markdown, no extra text):\n"
        '{"mode": "<quick|deep|academic>", "rationale": "<one sentence>", '
        '"angles": ["<angle 1>", "<angle 2>", "<angle 3>"]}\n\n'
        "Classification guide:\n"
        "- 'quick': well-known topic, simple factual question, single well-documented domain\n"
        "- 'deep': nuanced, needs recent research, comparative or analytical question\n"
        "- 'academic': cutting-edge, contested findings, citation chains required, advanced research"
    )
    api_key = os.getenv("MISTRAL_API_KEY", "")
    try:
        resp = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": 256,
            },
            timeout=30,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return _json.loads(text.strip())
    except Exception as exc:
        return {
            "mode": "deep",
            "rationale": f"Classification failed ({exc}), defaulting to deep mode",
            "angles": [topic, f"{topic} recent advances", f"{topic} key findings"],
        }


def _read_swarm_file(out_dir: Path, ts: str, suffix: str) -> str:
    """Read a swarm output file; return empty string if missing."""
    p = out_dir / f"swarm_{ts}_{suffix}"
    try:
        return p.read_text(encoding="utf-8") if p.exists() else ""
    except OSError:
        return ""


def _swarm_path(out_dir: Path, ts: str, suffix: str) -> str:
    """Return absolute path string for a swarm output file."""
    return str(out_dir / f"swarm_{ts}_{suffix}")


def _parse_critic_output(text: str) -> dict:
    """Parse Sokrates' JSON verdict from task output text."""
    import re, json as _json
    match = re.search(r'\{[^{}]*"score"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return _json.loads(match.group())
        except Exception:
            pass
    score_m = re.search(r'"score"\s*:\s*(\d+)', text)
    verdict_m = re.search(r'"verdict"\s*:\s*"(\w+)"', text)
    return {
        "score": int(score_m.group(1)) if score_m else 6,
        "verdict": verdict_m.group(1).upper() if verdict_m else "REVISE",
        "gaps": [],
        "feedback": text[:500],
    }


# ── Academic Swarm — Agent Factories ─────────────────────────────────────────

def make_hypatia(topic: str) -> Agent:
    """Swarm Phase 1: broad academic search (all modes)."""
    return Agent(
        llm=llm_small,
        function_calling_llm=llm_small,
        role="Academic Swarm — Hypatia (Scout)",
        goal=(
            f"Perform a broad academic literature search on '{topic}'. "
            "Find 15–20 high-quality sources with full metadata."
        ),
        backstory=(
            "You are Hypatia of Alexandria, the ancient librarian and scholar. "
            "Your mission: survey the academic landscape of a topic and return a rich, "
            "structured source list.\n\n"
            "Search strategy:\n"
            "1. Use Semantic Scholar to search for peer-reviewed papers: "
            f"  '{topic}', '{topic} review', '{topic} recent advances'\n"
            "2. Use web search for complementary sources: "
            f"  '{topic} research 2024 2025', '{topic} key findings'\n\n"
            "For each source found, note: title, authors, year, venue/journal, "
            "abstract snippet (first 100 words), URL, and citation count if available.\n\n"
            "Output format:\n"
            "## Academic Sources\n"
            "[SS-N] Title | Authors | Year | Venue | Citations: X | URL\n"
            "  Abstract: ...\n\n"
            "## Web Sources\n"
            "[WEB-N] Title | Source | URL\n"
            "  Summary: ...\n\n"
            "Aim for 15–20 total sources. Prioritize recent (last 5 years) and highly cited."
        ),
        tools=[semantic_scholar_tool, research_search_tool],
        allow_delegation=False,
        verbose=True,
        max_iter=8,
    )


def make_bacon(topic: str) -> Agent:
    """Swarm Phase 2 (deep+): deep paper analysis."""
    return Agent(
        llm=llm_large,
        role="Academic Swarm — Francis Bacon (Analyst)",
        goal=(
            f"Deep-read the top papers from Hypatia's source list on '{topic}'. "
            "Extract methodology, key claims, and limitations for each."
        ),
        backstory=(
            "You are Francis Bacon, founder of the empirical scientific method. "
            "You read research papers with a methodologist's eye.\n\n"
            "For each source in Hypatia's output:\n"
            "- Summarize the methodology used (1–2 sentences)\n"
            "- List the 2–3 strongest claims the paper makes\n"
            "- Note any stated limitations or caveats\n"
            "- Rate methodological rigor: [STRONG] / [ADEQUATE] / [WEAK]\n\n"
            "Process the top 8–10 sources. Skip sources without clear abstracts.\n\n"
            "Output format:\n"
            "## Paper Analysis\n\n"
            "**[SS-N / WEB-N] Title**\n"
            "Methodology: ...\n"
            "Claims: (1) ... (2) ... (3) ...\n"
            "Limitations: ...\n"
            "Rigor: [STRONG/ADEQUATE/WEAK]\n"
        ),
        tools=[semantic_scholar_tool],
        allow_delegation=False,
        verbose=True,
        max_iter=8,
    )


def make_popper(topic: str) -> Agent:
    """Swarm Phase 2 (academic only): evidence cross-checking, parallel with Bacon."""
    return Agent(
        llm=llm_large,
        role="Academic Swarm — Karl Popper (Validator)",
        goal=(
            f"Cross-check claims across Hypatia's sources on '{topic}'. "
            "Build an evidence quality matrix and flag contradictions."
        ),
        backstory=(
            "You are Karl Popper, champion of falsificationism. "
            "Your job: stress-test every major claim in the source list.\n\n"
            "For each major claim that appears in 2+ sources:\n"
            "- Mark [✓ HIGH] if corroborated by 3+ independent primary sources\n"
            "- Mark [~ MEDIUM] if supported by 2 sources with minor disagreements\n"
            "- Mark [⚠ LOW] if only 1 source, or sources conflict\n\n"
            "Identify CONTRADICTIONS: where two sources make opposite claims. "
            "Flag which is more credible and why.\n\n"
            "Output format:\n"
            "## Evidence Quality Matrix\n"
            "[✓ HIGH] Claim | Sources: SS-1, SS-3\n"
            "[~ MEDIUM] Claim | Sources: SS-2 | Note: minor disagreement on X\n"
            "[⚠ LOW] Claim | Source: SS-5 | Reason: single source, no replication\n\n"
            "## Contradictions\n"
            "[↔] SS-2 claims X, but SS-4 claims Y | Recommended: trust SS-2 because Z\n\n"
            "## Evidence Gaps\n"
            "[?] Important question not answered by any source"
        ),
        tools=[],
        allow_delegation=False,
        verbose=True,
        max_iter=6,
    )


def make_leibniz(topic: str) -> Agent:
    """Swarm Phase 3 (academic only): citation chain tracer."""
    return Agent(
        llm=llm_small,
        function_calling_llm=llm_small,
        role="Academic Swarm — Leibniz (CitationChainer)",
        goal=(
            f"Trace citation chains from the top papers on '{topic}'. "
            "Identify foundational works and recent high-impact papers."
        ),
        backstory=(
            "You are Gottfried Wilhelm Leibniz, who built on Newton's shoulders. "
            "You follow citation chains to find the intellectual ancestry of ideas.\n\n"
            "Using Semantic Scholar:\n"
            "1. Search for the 3 most-cited papers from Hypatia's source list\n"
            "2. For each, search 'cited by' to find papers that reference it\n"
            "3. Look for seminal older works (>100 citations) that keep appearing\n"
            "4. Find the most recent high-impact papers (last 2 years, >20 citations)\n\n"
            "Output format:\n"
            "## Foundational Papers (seminal, frequently cited)\n"
            "[F-N] Title | Authors | Year | Citations: X | URL\n"
            "  Why foundational: ...\n\n"
            "## Recent High-Impact (last 2 years)\n"
            "[R-N] Title | Authors | Year | Citations: X | URL\n\n"
            "## Citation Gaps\n"
            "[GAP-N] Area not covered in current source list: ..."
        ),
        tools=[semantic_scholar_tool],
        allow_delegation=False,
        verbose=True,
        max_iter=8,
    )


def make_averroes(topic: str) -> Agent:
    """Swarm Phase 4 (deep+): synthesis of all gathered findings."""
    return Agent(
        llm=llm_large,
        role="Academic Swarm — Averroes (Synthesizer)",
        goal=(
            f"Synthesize all research findings on '{topic}' into a unified narrative "
            "with inline [Ref N] citations."
        ),
        backstory=(
            "You are Ibn Rushd (Averroes), the great synthesizer of Aristotle. "
            "You merge multiple analyses into one coherent, citable narrative.\n\n"
            "Process:\n"
            "1. Read Hypatia's sources (+ Bacon's analysis, Popper's evidence matrix, "
            "and Leibniz's citation chains if provided in context)\n"
            "2. Build a numbered reference list from all sources\n"
            "3. Write a flowing synthesis memo (600–800 words):\n"
            "   Overview → Key validated findings (with [Ref N]) → "
            "Contested areas → Novel angles → Open questions\n\n"
            "Confidence rules:\n"
            "- [✓ HIGH] evidence → state confidently\n"
            "- [~ MEDIUM] or single-source → hedge: 'suggests', 'may indicate'\n"
            "- [⚠ LOW] or contradicted → explicitly note the disagreement\n\n"
            "End with:\n"
            "## References\n"
            "[1] Author. 'Title'. Venue, Year. URL\n"
            "[2] ...\n\n"
            "This synthesis will be reviewed by Sokrates — be honest about uncertainty."
        ),
        tools=[],
        allow_delegation=False,
        verbose=True,
        max_iter=8,
    )


def make_sokrates(topic: str) -> Agent:
    """Swarm critic loop: evaluates synthesis quality."""
    return Agent(
        llm=llm_large,
        role="Academic Swarm — Sokrates (Critic)",
        goal=(
            f"Evaluate the synthesis on '{topic}' for coverage, logic, and evidence quality. "
            "Return a JSON verdict."
        ),
        backstory=(
            "You are Sokrates, the questioner. You have just read a research synthesis "
            "and now you interrogate it.\n\n"
            "Check for:\n"
            "- Coverage: are all major angles from the source list covered?\n"
            "- Logic: any leaps from A to C without B?\n"
            "- Evidence: any strong claims with weak [~ MEDIUM] or [⚠ LOW] backing?\n"
            "- Gaps: what important question is not addressed?\n\n"
            "Score 1–10 (8+ = acceptable for publication).\n\n"
            "Respond with ONLY this JSON (no markdown, no extra text):\n"
            '{"score": <int 1-10>, "verdict": "<PASS|REVISE>", '
            '"gaps": ["<gap 1>", "<gap 2>"], '
            '"feedback": "<2-3 sentences of specific improvement instructions>"}\n\n'
            "verdict must be PASS if score >= 8, REVISE if score < 8."
        ),
        tools=[],
        allow_delegation=False,
        verbose=True,
        max_iter=4,
    )


def make_darwin(topic: str) -> Agent:
    """Swarm final writer: produces structured academic markdown report."""
    return Agent(
        llm=llm_large,
        role="Academic Swarm — Darwin (Writer)",
        goal=(
            f"Write the final structured academic report on '{topic}' "
            "with all sections, inline citations, and references. Save with file_writer."
        ),
        backstory=(
            "You are Charles Darwin, who distilled years of research into The Origin of Species. "
            "You write the final, publication-ready report.\n\n"
            "Required sections (in this order):\n\n"
            "# {Descriptive Title}\n"
            "**Swarm Mode:** {Quick|Deep|Academic}  "
            "**Date:** {today's date}\n\n"
            "## Abstract\n"
            "[3–5 sentences answering the core question directly]\n\n"
            "## Background & Context\n"
            "[Establish why this topic matters; 100–150 words]\n\n"
            "## Key Findings\n"
            "[Numbered. Each: bold claim → explanation → [Ref N]. Min 4 findings.]\n\n"
            "## Methodology Review\n"
            "[Based on Bacon's analysis — what methods dominate this field? "
            "What are their strengths/limitations?]\n\n"
            "## Evidence Assessment\n"
            "[Only in Academic mode — summarize Popper's quality matrix: "
            "how strong is the evidence overall? Any unresolved contradictions?]\n\n"
            "## Research Gaps\n"
            "[From Sokrates' gaps + Popper's evidence gaps: what remains unanswered?]\n\n"
            "## Conclusions\n"
            "[2–3 paragraph synthesis of what we know, what we don't, and what to explore next]\n\n"
            "## References\n"
            "[N] Author. 'Title'. Venue/Journal, Year. URL: <full URL>\n\n"
            "Rules:\n"
            "- 900–1300 words total\n"
            "- Every factual claim must have [Ref N]\n"
            "- Min 8 references, 5+ must be primary academic sources with URLs\n"
            "- Omit 'Evidence Assessment' section in Quick and Deep modes\n"
            "- Language: Bahasa Indonesia if topic was asked in Indonesian, English otherwise\n"
            "Save using file_writer."
        ),
        tools=[file_writer],
        allow_delegation=False,
        verbose=True,
        max_iter=8,
    )


# ── Academic Swarm — Task Factories ──────────────────────────────────────────

def make_hypatia_task(topic: str, agent: Agent, angles: list, out_path: str) -> Task:
    angles_str = "\n".join(f"- {a}" for a in angles)
    return Task(
        description=(
            f"Search for academic and web sources on **{topic}**.\n\n"
            "Al-Biruni identified these research angles to cover:\n"
            f"{angles_str}\n\n"
            "STEP 1 — Semantic Scholar searches (run all three):\n"
            f"  1. '{topic}'\n"
            f"  2. '{topic} review'\n"
            f"  3. '{topic} recent advances 2023 2024'\n\n"
            "STEP 2 — Web search (run two queries):\n"
            f"  1. '{topic} research findings'\n"
            f"  2. '{topic} key studies'\n\n"
            "STEP 3 — Output in this format:\n\n"
            "## Academic Sources\n"
            "[SS-N] Title | Authors | Year | Venue | URL\n"
            "  Abstract: <first 80 words>\n\n"
            "## Web Sources\n"
            "[WEB-N] Title | Source | URL\n"
            "  Summary: <1-2 sentences>\n\n"
            "Target: 15–20 total sources. Prefer peer-reviewed and last 5 years."
        ),
        expected_output=(
            "Structured source list: Academic Sources section ([SS-N] entries with abstracts) "
            "and Web Sources section ([WEB-N] entries with summaries). 15–20 sources total."
        ),
        agent=agent,
        output_file=out_path,
    )


def make_bacon_task(topic: str, agent: Agent, scout_output: str, out_path: str) -> Task:
    ctx = scout_output[:5000] if scout_output else "[No scout output available]"
    return Task(
        description=(
            f"Deep-analyze the top papers from this source list on **{topic}**.\n\n"
            f"--- HYPATIA'S SOURCES ---\n{ctx}\n--- END ---\n\n"
            "For the top 8–10 sources with abstracts:\n"
            "1. Summarize the methodology (1–2 sentences)\n"
            "2. List 2–3 strongest claims\n"
            "3. Note stated limitations\n"
            "4. Rate rigor: [STRONG] peer-reviewed + large sample + replicated | "
            "[ADEQUATE] peer-reviewed but limited scope | [WEAK] no peer review or tiny sample\n\n"
            "Use Semantic Scholar to fetch additional details if needed.\n\n"
            "Output:\n"
            "## Paper Analysis\n\n"
            "**[SS-N/WEB-N] Title**\n"
            "Methodology: ...\n"
            "Claims: (1) ... (2) ... (3) ...\n"
            "Limitations: ...\n"
            "Rigor: [STRONG/ADEQUATE/WEAK]"
        ),
        expected_output=(
            "Paper Analysis section with 8–10 entries. Each entry: title, methodology, "
            "2–3 claims, limitations, rigor rating."
        ),
        agent=agent,
        output_file=out_path,
    )


def make_popper_task(topic: str, agent: Agent, scout_output: str, out_path: str) -> Task:
    ctx = scout_output[:5000] if scout_output else "[No scout output available]"
    return Task(
        description=(
            f"Cross-check the claims in these sources on **{topic}**.\n\n"
            f"--- HYPATIA'S SOURCES ---\n{ctx}\n--- END ---\n\n"
            "Build an evidence quality matrix:\n"
            "- [✓ HIGH]: claim corroborated by 3+ independent sources\n"
            "- [~ MEDIUM]: supported by 2 sources with minor disagreements\n"
            "- [⚠ LOW]: single source, or sources conflict\n\n"
            "Also identify CONTRADICTIONS (Source A says X, Source B says Y) "
            "and EVIDENCE GAPS (important questions with no good source).\n\n"
            "Output:\n"
            "## Evidence Quality Matrix\n"
            "[✓ HIGH] Claim | Sources: SS-1, SS-3\n"
            "[~ MEDIUM] Claim | Sources: SS-2 | Note: ...\n"
            "[⚠ LOW] Claim | Source: SS-5 | Reason: ...\n\n"
            "## Contradictions\n"
            "[↔] SS-2 claims X, but SS-4 claims Y | Recommended: trust SS-2 because ...\n\n"
            "## Evidence Gaps\n"
            "[?] Important unanswered question"
        ),
        expected_output=(
            "Three sections: Evidence Quality Matrix (HIGH/MEDIUM/LOW claims), "
            "Contradictions (↔ entries), Evidence Gaps (? entries)."
        ),
        agent=agent,
        output_file=out_path,
    )


def make_leibniz_task(topic: str, agent: Agent, scout_output: str, out_path: str) -> Task:
    ctx = scout_output[:3000] if scout_output else "[No scout output available]"
    return Task(
        description=(
            f"Trace citation chains from the top papers on **{topic}**.\n\n"
            f"--- HYPATIA'S TOP SOURCES ---\n{ctx[:2000]}\n--- END ---\n\n"
            "STEP 1 — Run Semantic Scholar searches to find highly-cited papers:\n"
            f"  1. '{topic} highly cited'\n"
            f"  2. '{topic} foundational paper'\n"
            f"  3. '{topic} seminal work'\n\n"
            "STEP 2 — Identify:\n"
            "  A. Foundational papers (older, >100 citations, keep being referenced)\n"
            "  B. Recent high-impact papers (published 2022–2025, >20 citations)\n"
            "  C. Citation gaps (important adjacent areas not in current source list)\n\n"
            "Output:\n"
            "## Foundational Papers\n"
            "[F-N] Title | Authors | Year | Citations: X | URL\n"
            "  Why foundational: ...\n\n"
            "## Recent High-Impact Papers\n"
            "[R-N] Title | Authors | Year | Citations: X | URL\n\n"
            "## Citation Gaps\n"
            "[GAP-N] Area missing from current coverage: ..."
        ),
        expected_output=(
            "Three sections: Foundational Papers ([F-N] with citation counts + reason), "
            "Recent High-Impact Papers ([R-N]), Citation Gaps ([GAP-N])."
        ),
        agent=agent,
        output_file=out_path,
    )


def make_averroes_task(
    topic: str, agent: Agent,
    scout_out: str, bacon_out: str, popper_out: str, leibniz_out: str,
    out_path: str,
) -> Task:
    ctx_scout   = scout_out[:3000]   if scout_out   else "[Not available]"
    ctx_bacon   = bacon_out[:2000]   if bacon_out   else "[Not available — Quick/Deep mode]"
    ctx_popper  = popper_out[:2000]  if popper_out  else "[Not available — Quick/Deep mode]"
    ctx_leibniz = leibniz_out[:1500] if leibniz_out else "[Not available — Quick/Deep mode]"
    return Task(
        description=(
            f"Synthesize all research findings on **{topic}** into a unified narrative.\n\n"
            f"--- HYPATIA (Sources) ---\n{ctx_scout}\n--- END ---\n\n"
            f"--- BACON (Paper Analysis) ---\n{ctx_bacon}\n--- END ---\n\n"
            f"--- POPPER (Evidence Matrix) ---\n{ctx_popper}\n--- END ---\n\n"
            f"--- LEIBNIZ (Citation Chains) ---\n{ctx_leibniz}\n--- END ---\n\n"
            "Write a flowing synthesis memo (600–800 words):\n"
            "Overview → Key validated findings (with [Ref N]) → "
            "Contested areas → Novel angles → Open questions\n\n"
            "Build a numbered reference list from all sources at the end.\n\n"
            "Confidence rules:\n"
            "- [✓ HIGH] evidence → state confidently\n"
            "- [~ MEDIUM] or single-source → hedge: 'suggests', 'may indicate'\n"
            "- [⚠ LOW] → explicitly note 'this claim is contested: ...'\n\n"
            "End with:\n"
            "## References\n"
            "[1] Author. 'Title'. Venue, Year. URL\n"
            "[2] ..."
        ),
        expected_output=(
            "Flowing synthesis memo (600–800 words) with [Ref N] inline citations, "
            "followed by a numbered References section."
        ),
        agent=agent,
        output_file=out_path,
    )


def make_averroes_revision_task(
    topic: str, agent: Agent,
    previous_synthesis: str, critic_feedback: str,
    out_path: str,
) -> Task:
    prev = previous_synthesis[:4000] if previous_synthesis else "[No previous synthesis]"
    return Task(
        description=(
            f"Revise the synthesis on **{topic}** based on Sokrates' critique.\n\n"
            f"--- PREVIOUS SYNTHESIS ---\n{prev}\n--- END ---\n\n"
            f"--- SOKRATES' FEEDBACK ---\n{critic_feedback}\n--- END ---\n\n"
            "Address each point in the feedback. Do not remove content — improve it:\n"
            "- Add missing angles\n"
            "- Hedge weak claims more explicitly\n"
            "- Resolve noted contradictions\n"
            "- Improve flow where flagged\n\n"
            "Return the FULL revised synthesis (not just the changed parts). "
            "Keep the References section intact, adding any new sources cited."
        ),
        expected_output=(
            "Full revised synthesis memo (600–800 words) with feedback addressed, "
            "inline [Ref N] citations, and References section."
        ),
        agent=agent,
        output_file=out_path,
    )


def make_sokrates_task(
    topic: str, agent: Agent,
    synthesis: str, round_num: int,
    out_path: str,
) -> Task:
    ctx = synthesis[:5000] if synthesis else "[No synthesis available]"
    return Task(
        description=(
            f"Evaluate this synthesis on **{topic}** (critic round {round_num}).\n\n"
            f"--- SYNTHESIS TO EVALUATE ---\n{ctx}\n--- END ---\n\n"
            "Score 1–10. Give verdict PASS if score >= 8, REVISE if score < 8.\n\n"
            "Check:\n"
            "1. Coverage: are all major angles covered?\n"
            "2. Logic: any A→C leaps without B?\n"
            "3. Evidence: any strong claims with weak backing?\n"
            "4. Gaps: what important question is unanswered?\n\n"
            "RESPOND WITH ONLY THIS JSON (no markdown, no other text):\n"
            '{"score": <int 1-10>, "verdict": "<PASS|REVISE>", '
            '"gaps": ["<gap 1>", "<gap 2>"], '
            '"feedback": "<2-3 sentences of specific improvement instructions>"}'
        ),
        expected_output=(
            'JSON object: {"score": int, "verdict": "PASS"|"REVISE", '
            '"gaps": [str, ...], "feedback": str}'
        ),
        agent=agent,
        output_file=out_path,
    )


def make_darwin_task(
    topic: str, agent: Agent,
    synthesis: str, critic_rounds: list, mode: str,
    out_path: str,
) -> Task:
    ctx_synth = synthesis[:4000] if synthesis else "[No synthesis available]"
    gaps = []
    for r in critic_rounds:
        gaps.extend(r.get("gaps", []))
    gaps_str = "\n".join(f"- {g}" for g in gaps) if gaps else "- None identified"
    include_evidence = "Yes — include the Evidence Assessment section." if mode == "academic" else "No — omit the Evidence Assessment section."
    return Task(
        description=(
            f"Write the final academic report on **{topic}**.\n\n"
            f"--- SYNTHESIS ---\n{ctx_synth}\n--- END ---\n\n"
            f"Swarm mode: {mode.upper()}\n"
            f"Include Evidence Assessment section: {include_evidence}\n\n"
            f"Research gaps identified by Sokrates:\n{gaps_str}\n\n"
            "Write the full report with ALL these sections in this order:\n"
            "1. Title + metadata line (Swarm Mode + Date)\n"
            "2. Abstract (3–5 sentences)\n"
            "3. Background & Context (100–150 words)\n"
            "4. Key Findings (numbered, bold claim → explanation → [Ref N], min 4)\n"
            "5. Methodology Review (what methods dominate this field?)\n"
            "6. Evidence Assessment (Academic mode ONLY — omit otherwise)\n"
            "7. Research Gaps (from Sokrates' gaps list above)\n"
            "8. Conclusions (2–3 paragraphs)\n"
            "9. References ([N] Author. 'Title'. Venue, Year. URL — min 8 entries)\n\n"
            "Rules:\n"
            "- 900–1300 words\n"
            "- Every factual claim: [Ref N]\n"
            "- Language: Bahasa Indonesia if topic is in Indonesian, English otherwise\n"
            "Save with file_writer."
        ),
        expected_output=(
            "Complete academic report with all 8 required sections (9 in Academic mode), "
            "900–1300 words, inline [Ref N] citations, 8+ references with URLs."
        ),
        agent=agent,
        output_file=out_path,
    )


# ── Academic Swarm Pipeline Orchestrator ─────────────────────────────────────

class AcademicSwarmPipeline:
    """Meta-orchestrated academic researcher swarm.

    Modes (selected by Al-Biruni):
      quick:    Hypatia → Darwin                              (~2 min)
      deep:     Hypatia → Bacon → Averroes → Sokrates(×1) → Darwin  (~5 min)
      academic: Hypatia → [Bacon ‖ Popper] → Leibniz → Averroes → Sokrates(×3) → Darwin (~10 min)
    """

    def __init__(self, topic: str, step_cb=None, task_cb=None):
        self.topic = topic
        self.step_cb = step_cb
        self.task_cb = task_cb
        self.ts: str = ""

    def _make_crew(self, agents, tasks):
        return Crew(
            agents=agents,
            tasks=tasks,
            verbose=self.step_cb is None,
            step_callback=self.step_cb,
            task_callback=self.task_cb,
        )

    def _log(self, msg: str) -> None:
        if self.step_cb:
            self.step_cb(msg)
        else:
            print(msg)

    def _wiki_ingest(self, out_dir: Path) -> None:
        report_path = out_dir / f"swarm_{self.ts}_final_report.md"
        if not report_path.exists():
            self._log("[SWARM] WikiIngester: final report not found, skipping")
            return
        try:
            from tools.wiki_tools import write_research_to_wiki
            report_text = report_path.read_text(encoding="utf-8")
            write_research_to_wiki.invoke({"topic": self.topic, "content": report_text})
            self._log("[SWARM] WikiIngester → report ingested to wiki")
        except Exception as exc:
            self._log(f"[SWARM] WikiIngester warning (non-fatal): {exc}")

    def kickoff(self):
        topic = self.topic
        self.ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ts = self.ts
        out_dir = _research_dir()

        # ── Phase 0: Al-Biruni classifies topic ──────────────────────────────
        self._log(f"[SWARM] Al-Biruni classifying topic: '{topic}'…")
        meta = _classify_topic(topic)
        mode = meta.get("mode", "deep")
        angles = meta.get("angles", [topic])
        (out_dir / f"swarm_{ts}_0_meta.txt").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._log(f"[SWARM] Al-Biruni → mode={mode.upper()} | {meta.get('rationale', '')}")

        # ── Phase 1: Hypatia (all modes) ─────────────────────────────────────
        self._log("[SWARM] Hypatia searching academic sources…")
        hypatia = make_hypatia(topic)
        hypatia_task = make_hypatia_task(
            topic, hypatia, angles,
            _swarm_path(out_dir, ts, "1_scout.txt")
        )
        self._make_crew([hypatia], [hypatia_task]).kickoff()
        scout_out = _read_swarm_file(out_dir, ts, "1_scout.txt")
        self._log(f"[SWARM] Hypatia complete — {len(scout_out)} chars")

        if mode == "quick":
            self._log("[SWARM] Quick mode: Hypatia → Darwin")
            darwin = make_darwin(topic)
            darwin_task = make_darwin_task(
                topic, darwin, scout_out, [], mode,
                _swarm_path(out_dir, ts, "final_report.md")
            )
            self._make_crew([darwin], [darwin_task]).kickoff()
            self._wiki_ingest(out_dir)
            return {"mode": mode, "ts": ts}

        # ── Phase 2: Bacon + optional Popper ─────────────────────────────────
        bacon = make_bacon(topic)
        bacon_task = make_bacon_task(
            topic, bacon, scout_out,
            _swarm_path(out_dir, ts, "2_analysis.txt")
        )
        bacon_out = "[PARTIAL: Bacon unavailable]"
        popper_out = ""

        if mode == "academic":
            self._log("[SWARM] Academic mode: Bacon ‖ Popper (parallel)")
            popper = make_popper(topic)
            popper_task = make_popper_task(
                topic, popper, scout_out,
                _swarm_path(out_dir, ts, "3_validation.txt")
            )
            bacon_crew  = self._make_crew([bacon], [bacon_task])
            popper_crew = self._make_crew([popper], [popper_task])
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_bacon  = ex.submit(bacon_crew.kickoff)
                f_popper = ex.submit(popper_crew.kickoff)
                try:
                    f_bacon.result(timeout=300)
                    bacon_out = _read_swarm_file(out_dir, ts, "2_analysis.txt")
                except Exception as exc:
                    bacon_out = f"[PARTIAL: Bacon failed — {exc}]"
                try:
                    f_popper.result(timeout=300)
                    popper_out = _read_swarm_file(out_dir, ts, "3_validation.txt")
                except Exception as exc:
                    popper_out = f"[PARTIAL: Popper failed — {exc}]"
        else:
            self._log("[SWARM] Deep mode: Bacon analyzing papers")
            self._make_crew([bacon], [bacon_task]).kickoff()
            bacon_out = _read_swarm_file(out_dir, ts, "2_analysis.txt")

        # ── Phase 3: Leibniz (academic only) ─────────────────────────────────
        leibniz_out = ""
        if mode == "academic":
            self._log("[SWARM] Leibniz tracing citation chains…")
            leibniz = make_leibniz(topic)
            leibniz_task = make_leibniz_task(
                topic, leibniz, scout_out,
                _swarm_path(out_dir, ts, "4_citations.txt")
            )
            self._make_crew([leibniz], [leibniz_task]).kickoff()
            leibniz_out = _read_swarm_file(out_dir, ts, "4_citations.txt")

        # ── Phase 4: Averroes synthesizes ────────────────────────────────────
        self._log("[SWARM] Averroes synthesizing findings…")
        averroes = make_averroes(topic)
        averroes_task = make_averroes_task(
            topic, averroes, scout_out, bacon_out, popper_out, leibniz_out,
            _swarm_path(out_dir, ts, "5_synthesis.txt")
        )
        self._make_crew([averroes], [averroes_task]).kickoff()
        synthesis = _read_swarm_file(out_dir, ts, "5_synthesis.txt")

        # ── Phase 5: Sokrates critic loop ────────────────────────────────────
        max_rounds = 3 if mode == "academic" else 1
        critic_rounds = []

        for round_num in range(1, max_rounds + 1):
            self._log(f"[SWARM] Sokrates critic round {round_num}/{max_rounds}…")
            sokrates = make_sokrates(topic)
            sokrates_task = make_sokrates_task(
                topic, sokrates, synthesis, round_num,
                _swarm_path(out_dir, ts, "6_critique.txt")
            )
            self._make_crew([sokrates], [sokrates_task]).kickoff()
            critique_raw = _read_swarm_file(out_dir, ts, "6_critique.txt")
            critique = _parse_critic_output(critique_raw)
            critique["round"] = round_num
            critic_rounds.append(critique)
            self._log(
                f"[SWARM] Sokrates → score={critique.get('score')}, "
                f"verdict={critique.get('verdict')}"
            )

            if critique.get("verdict") == "PASS" or critique.get("score", 0) >= 8:
                self._log("[SWARM] Sokrates PASS — proceeding to Darwin")
                break

            if round_num < max_rounds:
                self._log(f"[SWARM] Sokrates REVISE — Averroes revising (round {round_num + 1})…")
                averroes2 = make_averroes(topic)
                revision_task = make_averroes_revision_task(
                    topic, averroes2, synthesis,
                    critique.get("feedback", ""),
                    _swarm_path(out_dir, ts, "5_synthesis.txt")
                )
                self._make_crew([averroes2], [revision_task]).kickoff()
                synthesis = _read_swarm_file(out_dir, ts, "5_synthesis.txt")

        # ── Phase 6: Darwin writes final report ──────────────────────────────
        self._log("[SWARM] Darwin writing final report…")
        darwin = make_darwin(topic)
        darwin_task = make_darwin_task(
            topic, darwin, synthesis, critic_rounds, mode,
            _swarm_path(out_dir, ts, "final_report.md")
        )
        self._make_crew([darwin], [darwin_task]).kickoff()
        self._log("[SWARM] Darwin complete")

        self._wiki_ingest(out_dir)
        return {"mode": mode, "ts": ts, "critic_rounds": len(critic_rounds)}


def build_academic_swarm(
    topic: str, step_cb=None, task_cb=None
) -> AcademicSwarmPipeline:
    return AcademicSwarmPipeline(topic, step_cb, task_cb)


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
            "- GENERAL mode: which outlets cover this best (news, industry, think-tanks)?\n"
            "- Use OpenLibrary Book Search to find foundational books and theses on the topic.\n\n"
            "Output a structured topic map:\n"
            "1. [MODE: X] declaration — first line, always\n"
            "2. Landscape summary — 5–8 bullet points\n"
            "3. Key search terms for deeper research — 6–10 terms\n"
            "4. Initial sources found — URL + title + one-line note\n"
            "5. Key books/theses found on OpenLibrary — [OL-N] title, author, URL"
        ),
        tools=[research_search_tool, openlibrary_tool, semantic_scholar_tool],
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
            "  - Source tier: [PRIMARY] peer-reviewed/official/books, "
            "[SECONDARY] expert commentary, [TERTIARY] blogs/forums\n"
            "  - Recency: prefer < 3 years unless foundational\n"
            "  - ACADEMIC mode: prioritise peer-reviewed papers and academic books\n"
            "  - GENERAL mode: prioritise authoritative outlets and recent reports\n"
            "  - Use OpenLibrary Book Search to find additional book references if "
            "fewer than 10 quality sources are available from web searches.\n\n"
            "Output format:\n"
            "## Curated Sources (10–15)\n"
            "[SOURCE N] Title | URL | [TIER] | Relevance: X/5 | One-line summary\n\n"
            "## OpenLibrary References\n"
            "[OL-N] Title | Author | Year | URL | Brief note\n\n"
            "## Research Focus\n"
            "[3–4 bullet points: the most important angles to investigate next]"
        ),
        tools=[research_search_tool, openlibrary_tool, semantic_scholar_tool],
        allow_delegation=False,
        verbose=True,
        max_iter=6,
    )


def make_idea_gen(topic: str) -> Agent:
    """Phase 2-A (parallel): generate novel angles and hypotheses."""
    return Agent(
        llm=llm_large,
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
        tools=[research_search_tool, semantic_scholar_tool],
        allow_delegation=False,
        verbose=True,
        max_iter=8,
    )


def make_validator_agent(topic: str) -> Agent:
    """Phase 2-B (parallel): cross-check claims, flag weak evidence."""
    return Agent(
        llm=llm_large,
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
        tools=[research_search_tool, semantic_scholar_tool],
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
            "and a complete reference list including OpenLibrary book sources. "
            "Save it using file_writer."
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
            "[N] Author. 'Title'. Journal/Outlet/Publisher, Year. URL: <full clickable URL>\n\n"
            "Rules:\n"
            "- 800–1200 words for the main body\n"
            "- Minimum 8 references, 5+ must be primary sources with full URLs\n"
            "- Include any OpenLibrary books from [OL-N] entries in the reference list "
            "using their openlibrary.org URL\n"
            "- Include any Semantic Scholar articles from [SS-N] entries in the reference list "
            "using their DOI or semanticscholar.org URL\n"
            "- Every factual claim must have [Ref N]\n"
            "- Language: Bahasa Indonesia if topic was asked in Indonesian, English otherwise"
        ),
        tools=[file_writer, openlibrary_tool, semantic_scholar_tool],
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
            "STEP 2 — BROAD WEB SURVEY (3–5 searches):\n"
            f"Search: '{topic}', '{topic} overview', '{topic} latest research', "
            f"'{topic} key players'\n"
            "ACADEMIC: also search '{topic} site:arxiv.org', "
            "'{topic} site:pubmed.ncbi.nlm.nih.gov'\n"
            "GENERAL: also search '{topic} news 2024 2025', '{topic} industry report'\n\n"
            "STEP 3 — OPENLIBRARY BOOK SEARCH:\n"
            f"Use OpenLibrary Book Search tool to search for books and theses about '{topic}'. "
            f"Also search '{topic} theory', '{topic} introduction' to find foundational texts. "
            "Note the [OL-N] entries with their openlibrary.org URLs.\n\n"
            "STEP 4 — SEMANTIC SCHOLAR ARTICLE SEARCH:\n"
            f"Use Semantic Scholar Article Search tool to search for peer-reviewed articles about '{topic}'. "
            f"Also try '{topic} review article' and '{topic} recent advances' to find key papers. "
            "Note the [SS-N] entries with their DOI or URL.\n\n"
            "STEP 5 — OUTPUT:\n"
            "[MODE: X]\n\n"
            "## Landscape Overview\n"
            "- [5–8 bullets: key facts, players, debates, timeline]\n\n"
            "## Key Search Terms for Deeper Research\n"
            "- [6–10 specific terms]\n\n"
            "## Initial Web Sources\n"
            "[SOURCE 1] Title | URL | Brief note\n"
            "[SOURCE 2] ...\n\n"
            "## OpenLibrary Books & Theses\n"
            "[OL-1] Title | Author | Year | URL\n"
            "[OL-2] ...\n\n"
            "## Semantic Scholar Articles\n"
            "[SS-1] Title | Author | Year | Venue | URL\n"
            "[SS-2] ..."
        ),
        expected_output=(
            "Structured topic map with [MODE: X] on first line, landscape overview "
            "(5–8 bullets), key search terms (6–10), web sources with URLs, "
            "an OpenLibrary Books section with [OL-N] entries, "
            "and a Semantic Scholar Articles section with [SS-N] entries."
        ),
        agent=agent,
        output_file=str(_research_dir() / "task1_scout.txt"),
    )


def make_filter_task(topic: str, agent: Agent, scout_task: Task) -> Task:
    """Phase 1-B task: curate 10–15 best sources from Scout's findings."""
    return Task(
        description=(
            f"Evaluate and curate sources for **{topic}** from Scout's output.\n\n"
            "STEP 1 — SCORE EACH WEB SOURCE from context:\n"
            "  Tier: [PRIMARY] / [SECONDARY] / [TERTIARY]\n"
            "  Relevance: 1–5\n"
            "  Recency: current (<2 yr) / dated (2–5 yr) / foundational (older, seminal)\n\n"
            "STEP 2 — SUPPLEMENT IF NEEDED:\n"
            "If fewer than 10 quality sources found, run targeted searches:\n"
            f"  ACADEMIC: '{topic} site:arxiv.org', '{topic} peer reviewed 2023 2024'\n"
            f"  GENERAL:  '{topic} report 2024', '{topic} analysis expert'\n"
            f"  BOOKS:    Use OpenLibrary Book Search for '{topic}', '{topic} textbook'\n"
            f"  ARTICLES: Use Semantic Scholar Article Search for '{topic} recent', '{topic} review'\n\n"
            "STEP 3 — OUTPUT:\n"
            "## Curated Web Sources (10–15)\n"
            "[SOURCE N] Title | URL | [TIER] | Relevance: X/5 | One-line summary\n\n"
            "## OpenLibrary References\n"
            "[OL-N] Title | Author | Year | URL: https://openlibrary.org/... | Brief note\n"
            "(carry forward all [OL-N] from Scout; add new ones if useful)\n\n"
            "## Semantic Scholar Articles\n"
            "[SS-N] Title | Author | Year | Venue | URL | Brief note\n"
            "(carry forward all [SS-N] from Scout; add new ones from supplemental search)\n\n"
            "## Research Focus\n"
            "[3–4 bullets: the most important angles to investigate in Phase 2]"
        ),
        expected_output=(
            "Curated list of 10–15 web sources (tier, relevance, URL, summary), "
            "an OpenLibrary References section with [OL-N] book entries, "
            "a Semantic Scholar Articles section with [SS-N] paper entries, "
            "and a Research Focus section with 3–4 key angles."
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


def make_synth_task(topic: str, agent: Agent, ideas: str, validation: str) -> Task:
    """Phase 3-A task: merge IdeaGen + Validator outputs."""
    ideas_ctx = ideas[:3000] if ideas else "[IdeaGen output unavailable]"
    valid_ctx = validation[:3000] if validation else "[Validator output unavailable]"
    return Task(
        description=(
            f"Merge two analyses about **{topic}** into a unified narrative.\n\n"
            f"--- IDEAS (IdeaGen) ---\n{ideas_ctx}\n--- END ---\n\n"
            f"--- VALIDATION (Validator) ---\n{valid_ctx}\n--- END ---\n\n"
            "Process:\n"
            "1. For each IDEA: check Validator's findings on the underlying claims.\n"
            "   - VALIDATED [✓] → present confidently\n"
            "   - WEAK [⚠]     → hedge: 'suggests', 'may indicate', 'in some cases'\n"
            "   - CONTRADICTED  → resolve explicitly, or note the disagreement\n"
            "2. Include all DATA GAPS [?] as an 'Open Questions' section\n"
            "3. Write a flowing memo (not a bullet list):\n"
            "   Overview → Key validated findings → Contested areas → "
            "Novel angles → Open questions\n\n"
            "Length: 500–700 words. Be honest about uncertainty — "
            "this synthesis will be critiqued next."
        ),
        expected_output=(
            "Flowing research memo (500–700 words) integrating ideas and validation, "
            "with hedged confidence levels and an open questions section."
        ),
        agent=agent,
        output_file=str(_research_dir() / "task4_synthesis.txt"),
    )


def make_critique_task_p3(topic: str, agent: Agent, synth_task: Task) -> Task:
    """Phase 3-B task: logic review + produce refined synthesis."""
    return Task(
        description=(
            f"Review the synthesis about **{topic}** for logical issues, "
            "then output critique notes + a refined version.\n\n"
            "CHECK FOR:\n"
            "- Logical leaps (A → C without establishing B)\n"
            "- Over-generalizations: 'always', 'all', 'never', 'obviously', 'clearly'\n"
            "- Residual [⚠] weak claims still presented as facts\n"
            "- Missing perspectives or systematic blind spots\n"
            "- Structural breaks in reading flow\n\n"
            "OUTPUT FORMAT (mandatory):\n"
            "## CATATAN KRITIK\n"
            "[Issue N]: [specific location] → [problem] → [fix applied]\n\n"
            "---\n\n"
            "## SINTESIS YANG DISEMPURNAKAN\n"
            "[Full refined synthesis with every issue corrected]\n\n"
            "Rule: soften, do not remove. "
            "'X causes Y' → 'X is associated with Y' where causation is unproven."
        ),
        expected_output=(
            "Two sections: CATATAN KRITIK (numbered issues with fixes) "
            "and SINTESIS YANG DISEMPURNAKAN (complete refined synthesis)."
        ),
        agent=agent,
        context=[synth_task],
        output_file=str(_research_dir() / "task5_critique.txt"),
    )


def make_write_task(topic: str, agent: Agent, critique_task: Task) -> Task:
    """Phase 3-C task: write final article with citations + reference list."""
    return Task(
        description=(
            f"Write the final article about **{topic}** using the refined synthesis.\n\n"
            "STRUCTURE:\n"
            "# [Descriptive title]\n"
            "**Research Mode:** [ACADEMIC / GENERAL / HYBRID]\n"
            "**Date:** [today's date]\n"
            "**Confidence:** [High / Medium / Low] — [one-line rationale]\n\n"
            "## Ringkasan Eksekutif\n"
            "[3–5 sentences directly answering the core question]\n\n"
            "## Temuan Utama\n"
            "[Numbered: bold claim → explanation → [Ref N]]\n\n"
            "## [2–4 thematic sections based on synthesis content]\n"
            "[Flowing prose, every factual claim cited with [Ref N]]\n\n"
            "## Pertanyaan Terbuka & Celah Riset\n"
            "[From Validator's DATA GAPS — what remains unknown or contested]\n\n"
            "## Referensi\n"
            "[N] Author. 'Title'. Journal/Outlet, Year. URL: <full clickable URL>\n\n"
            "RULES:\n"
            "- 800–1200 words for the main body\n"
            "- Minimum 8 references, 5+ primary with full URLs\n"
            "- Include [OL-N] books from context using their openlibrary.org URL\n"
            "- Include [SS-N] articles from context using their DOI or semanticscholar.org URL\n"
            "- Every factual claim must have [Ref N] inline\n"
            "- Language: Bahasa Indonesia if topic was in Indonesian, English otherwise\n"
            "Save using file_writer."
        ),
        expected_output=(
            "Complete final article (800–1200 words) with header, executive summary, "
            "key findings, thematic sections, open questions, and reference list "
            "(8+ entries with full URLs). Saved to task6_final_report.md."
        ),
        agent=agent,
        context=[critique_task],
        output_file=str(_research_dir() / "task6_final_report.md"),
    )


# ── Pipeline Orchestrator ─────────────────────────────────────────────────────

class IbnAlHaythamPipeline:
    def __init__(self, topic: str, step_cb=None, task_cb=None):
        self.topic = topic
        self.step_cb = step_cb
        self.task_cb = task_cb

    def _make_crew(self, agents, tasks):
        return Crew(
            agents=agents,
            tasks=tasks,
            verbose=self.step_cb is None,
            step_callback=self.step_cb,
            task_callback=self.task_cb,
        )

    def kickoff(self):
        topic = self.topic

        # ── Phase 1: Sequential (Scout → Filter) ──────────────────────────────
        scout = make_scout(topic)
        filter_agent = make_filter_agent(topic)
        scout_task = make_scout_task(topic, scout)
        filter_task = make_filter_task(topic, filter_agent, scout_task)
        self._make_crew([scout, filter_agent], [scout_task, filter_task]).kickoff()
        filter_context = _read_phase_output("task2_filter.txt")

        # ── Phase 2: Parallel (IdeaGen ‖ Validator) ───────────────────────────
        idea_gen = make_idea_gen(topic)
        validator = make_validator_agent(topic)
        idea_task = make_idea_task(topic, idea_gen, filter_context)
        valid_task = make_valid_task(topic, validator, filter_context)
        idea_crew = self._make_crew([idea_gen], [idea_task])
        valid_crew = self._make_crew([validator], [valid_task])

        ideas_output = "[PARTIAL: IdeaGen unavailable]"
        valid_output = "[PARTIAL: Validator unavailable]"
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_ideas = ex.submit(idea_crew.kickoff)
            f_valid = ex.submit(valid_crew.kickoff)
            try:
                f_ideas.result(timeout=300)
                ideas_output = _read_phase_output("task3a_ideas.txt")
            except Exception as exc:
                ideas_output = f"[PARTIAL: IdeaGen failed — {exc}]"
            try:
                f_valid.result(timeout=300)
                valid_output = _read_phase_output("task3b_validation.txt")
            except Exception as exc:
                valid_output = f"[PARTIAL: Validator failed — {exc}]"

        if ideas_output.startswith("[PARTIAL") and valid_output.startswith("[PARTIAL"):
            raise RuntimeError("Phase 2 completely failed — both IdeaGen and Validator errored.")

        # ── Phase 3: Sequential (Synthesizer → Critic → Writer) ───────────────
        synthesizer = make_synthesizer(topic)
        critic = make_critic_agent(topic)
        writer = make_writer(topic)
        synth_task = make_synth_task(topic, synthesizer, ideas_output, valid_output)
        crit_task = make_critique_task_p3(topic, critic, synth_task)
        write_task = make_write_task(topic, writer, crit_task)
        return self._make_crew(
            [synthesizer, critic, writer],
            [synth_task, crit_task, write_task],
        ).kickoff()


def build_crew(topic: str, step_cb=None, task_cb=None) -> IbnAlHaythamPipeline:
    return IbnAlHaythamPipeline(topic, step_cb, task_cb)


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE 3 — CAREER OPS  (Archetype → Evaluator → CV Advisor → Report Writer)
# Inspired by github.com/santifer/career-ops
# ══════════════════════════════════════════════════════════════════════════════

def _career_dir() -> Path:
    """Return the directory where Career Ops output files are written."""
    vault = os.getenv("OBSIDIAN_VAULT_PATH", "")
    if vault:
        p = Path(vault) / "CareerOps"
        p.mkdir(parents=True, exist_ok=True)
        return p
    p = Path(__file__).parent / "AI Data" / "CareerOps"
    p.mkdir(parents=True, exist_ok=True)
    return p


def make_archetype_agent() -> Agent:
    return Agent(
        llm=llm_small,
        role="Career Ops — Job Archetype Classifier",
        goal="Classify the job role into an archetype and extract key requirements, seniority, company signals, and red flags.",
        backstory=(
            "You are a senior talent analyst who has screened thousands of job descriptions. "
            "You classify every role into one of six archetypes:\n"
            "  [TECHNICAL]    — engineering, data, systems, product\n"
            "  [LEADERSHIP]   — management, VP, director, C-level\n"
            "  [CREATIVE]     — design, content, marketing, UX\n"
            "  [OPERATIONAL]  — ops, finance, HR, legal, admin\n"
            "  [RESEARCH]     — science, academia, R&D, policy\n"
            "  [SALES]        — biz-dev, account management, growth\n\n"
            "For each role you extract:\n"
            "- Seniority level: junior / mid / senior / principal / staff\n"
            "- Work mode: remote / hybrid / onsite\n"
            "- Company stage: startup / scale-up / enterprise\n"
            "- Must-have requirements vs nice-to-have\n"
            "- Compensation signals (if mentioned)\n"
            "- Red flag indicators: vague scope, 'startup hustle', rock-star wording, "
            "excessive requirements for seniority, unclear reporting line"
        ),
        tools=[],
        allow_delegation=False,
        verbose=True,
        max_iter=4,
    )


def make_evaluator_agent() -> Agent:
    return Agent(
        llm=llm_large,
        role="Career Ops — Job Evaluator",
        goal=(
            "Score the job across 7 dimensions (A–G) using the candidate's CV. "
            "Produce a structured scorecard and a clear recommendation."
        ),
        backstory=(
            "You are a career strategist with brutal, analytical honesty. "
            "You only recommend applications with a Global Score ≥ 4.0/5.\n\n"
            "7-dimension scoring framework:\n"
            "  A — Match with CV      : alignment of candidate experience with JD requirements (1–5)\n"
            "  B — Career alignment   : does this role advance the stated career direction? (1–5)\n"
            "  C — Compensation       : salary signals vs market rate "
            "(1=below market, 3=neutral/not mentioned, 5=top quartile) (1–5)\n"
            "  D — Cultural signals   : company reputation, stability, culture clues in JD (1–5)\n"
            "  E — Red flags          : warning signs — low score = more red flags (1–5)\n"
            "  F — Legitimacy         : is this a real, active opening? [High / Caution / Suspicious]\n"
            "  G — Global score       : weighted synthesis of A–F, 1–5 scale\n\n"
            "Rules:\n"
            "- Score ONLY on what is explicitly stated — never assume\n"
            "- Salary not mentioned → C: 3 (neutral, not penalized)\n"
            "- 'Unicorn JD' (10 requirements, 2 years exp) → E: 2 (red flag)\n"
            "- F: Suspicious = copy-pasted text, ghost posting, no company name"
        ),
        tools=[],
        allow_delegation=False,
        verbose=True,
        max_iter=6,
    )


def make_cv_advisor_agent() -> Agent:
    return Agent(
        llm=llm_large,
        role="Career Ops — CV Advisor",
        goal=(
            "Provide specific, actionable advice for customizing the candidate's CV for this job. "
            "Reformulate existing experience only — never invent."
        ),
        backstory=(
            "You are an ATS optimization expert and career coach who makes every word count.\n\n"
            "Your advice is:\n"
            "- SPECIFIC: quote the exact CV bullet and suggest the exact replacement\n"
            "- HONEST: reformulate existing achievements, never fabricate skills\n"
            "- KEYWORD-AWARE: embed exact JD phrases naturally\n"
            "- PRIORITIZED: highest-impact changes first\n\n"
            "Structure:\n"
            "## Keywords to embed  — 5–8 exact phrases from the JD\n"
            "## Section-by-section rewrites\n"
            "   CURRENT: [original] | SUGGESTED: [rewrite] | WHY: [one line]\n"
            "## What to de-emphasize — experience that dilutes focus for this role\n"
            "## Suggested summary/objective — 2-sentence opener tailored to this role"
        ),
        tools=[],
        allow_delegation=False,
        verbose=True,
        max_iter=6,
    )


def make_career_report_writer() -> Agent:
    return Agent(
        llm=llm_large,
        role="Career Ops — Report Writer",
        goal="Compile archetype analysis, scorecard, and CV advice into a clean, structured evaluation report.",
        backstory=(
            "You are the final stage of the Career Ops pipeline. "
            "You synthesize everything into one readable report that gives a clear go/no-go decision.\n\n"
            "Strict report structure:\n"
            "# Career Ops Evaluation Report\n"
            "**Role:** | **Company:** | **Archetype:** | **Date:**\n\n"
            "## Verdict\n"
            "APPLY / DO NOT APPLY / APPLY WITH RESERVATIONS\n"
            "Global Score: **G: X.X / 5**\n\n"
            "## Scorecard\n"
            "| Dimension | Score | Notes |\n"
            "|-----------|-------|-------|\n"
            "| A — Match with CV    | X/5 | |\n"
            "| B — Career alignment | X/5 | |\n"
            "| C — Compensation     | X/5 | |\n"
            "| D — Cultural signals | X/5 | |\n"
            "| E — Red flags        | X/5 | |\n"
            "| F — Legitimacy       | High/Caution/Suspicious | |\n"
            "| G — Global score     | X.X/5 | |\n\n"
            "## Key Requirements\n"
            "## CV Customization Advice\n"
            "## Red Flags\n"
            "## Why Apply / Why Not"
        ),
        tools=[file_writer],
        allow_delegation=False,
        verbose=True,
        max_iter=6,
    )


def make_archetype_task(job_desc: str, agent: Agent, career_dir: Path) -> Task:
    jd = job_desc[:3000]
    return Task(
        description=(
            "Classify this job description and extract key signals.\n\n"
            f"--- JOB DESCRIPTION ---\n{jd}\n--- END ---\n\n"
            "Output:\n"
            "1. [ARCHETYPE: TYPE]\n"
            "2. Seniority level\n"
            "3. Work mode\n"
            "4. Company stage\n"
            "5. Must-have requirements (bullet list)\n"
            "6. Nice-to-have requirements (bullet list)\n"
            "7. Compensation signals\n"
            "8. Red flag indicators"
        ),
        expected_output=(
            "Structured classification: archetype tag, seniority, work mode, company stage, "
            "must-haves, nice-to-haves, compensation signals, and any red flags."
        ),
        agent=agent,
        output_file=str(career_dir / "career_archetype.txt"),
    )


def make_eval_task(job_desc: str, cv_text: str, agent: Agent, career_dir: Path) -> Task:
    jd = job_desc[:3000]
    cv = cv_text[:3000] if cv_text else "[No CV provided — score A as 3/5, C as 3/5 neutral]"
    return Task(
        description=(
            "Score this job against the candidate's CV using the A–G framework.\n\n"
            f"--- JOB DESCRIPTION ---\n{jd}\n--- END ---\n\n"
            f"--- CANDIDATE CV ---\n{cv}\n--- END ---\n\n"
            "Output a structured scorecard:\n"
            "## Scorecard\n"
            "A — Match with CV     : X/5 — [one-line reasoning]\n"
            "B — Career alignment  : X/5 — [one-line reasoning]\n"
            "C — Compensation      : X/5 — [one-line reasoning or 'Not mentioned']\n"
            "D — Cultural signals  : X/5 — [one-line reasoning]\n"
            "E — Red flags         : X/5 — [one-line reasoning]\n"
            "F — Legitimacy        : [High / Caution / Suspicious] — [reason]\n"
            "G — Global score      : X.X/5 — [APPLY / DO NOT APPLY / APPLY WITH RESERVATIONS]\n\n"
            "Follow with a 3–4 sentence justification for G."
        ),
        expected_output=(
            "Scorecard with A–F scores (1–5), F legitimacy flag, G global score (1.0–5.0), "
            "one-line reasoning per dimension, and a 3–4 sentence G justification."
        ),
        agent=agent,
        output_file=str(career_dir / "career_scores.txt"),
    )


def make_cv_advice_task(
    job_desc: str, cv_text: str, agent: Agent,
    career_dir: Path, eval_task: Task,
) -> Task:
    jd = job_desc[:2000]
    cv = cv_text[:2000] if cv_text else "[No CV provided — give keyword and structure advice only]"
    return Task(
        description=(
            "Provide targeted CV customization advice for this application.\n\n"
            f"--- JOB DESCRIPTION ---\n{jd}\n--- END ---\n\n"
            f"--- CANDIDATE CV ---\n{cv}\n--- END ---\n\n"
            "Produce:\n"
            "## Keywords to embed — 5–8 exact phrases from JD\n"
            "## Section-by-section rewrites\n"
            "   CURRENT: [original] | SUGGESTED: [rewrite] | WHY: [one line]\n"
            "## What to de-emphasize\n"
            "## Suggested summary line — 2-sentence tailored opener\n\n"
            "Never invent skills or achievements — only reformulate what is already there."
        ),
        expected_output=(
            "Keywords list (5–8), section-by-section rewrites, de-emphasis list, "
            "and a 2-sentence tailored CV summary."
        ),
        agent=agent,
        context=[eval_task],
        output_file=str(career_dir / "career_cv_advice.txt"),
    )


def make_career_report_task(
    job_desc: str, agent: Agent,
    career_dir: Path, eval_task: Task, cv_task: Task,
) -> Task:
    jd_header = job_desc.split("\n")[0][:100]
    return Task(
        description=(
            "Compile the archetype analysis, scorecard, and CV advice into the final Career Ops report.\n\n"
            f"Job reference: '{jd_header}'\n\n"
            "Use the Evaluator's scorecard and CV Advisor's advice from context. "
            "Follow the EXACT report structure from your instructions. "
            "The Verdict and Global Score must appear prominently at the top. "
            "Save the report using file_writer."
        ),
        expected_output=(
            "Complete Career Ops Evaluation Report (Markdown) with: verdict, A-G scorecard table, "
            "key requirements, CV customization advice, red flags, and apply/not-apply reasons."
        ),
        agent=agent,
        context=[eval_task, cv_task],
        output_file=str(career_dir / "career_eval_report.md"),
    )


class CareerOpsPipeline:
    """4-agent career evaluation pipeline.

    Phase 1: Archetype Classifier (mistral-small)
    Phase 2: Evaluator → CV Advisor → Report Writer (mistral-large, sequential)
    """

    def __init__(self, job_desc: str, cv_text: str = "", step_cb=None, task_cb=None):
        self.job_desc = job_desc
        self.cv_text = cv_text
        self.step_cb = step_cb
        self.task_cb = task_cb

    def _make_crew(self, agents, tasks):
        return Crew(
            agents=agents,
            tasks=tasks,
            verbose=self.step_cb is None,
            step_callback=self.step_cb,
            task_callback=self.task_cb,
        )

    def kickoff(self):
        cd = _career_dir()
        jd = self.job_desc
        cv = self.cv_text

        arch_agent = make_archetype_agent()
        arch_task = make_archetype_task(jd, arch_agent, cd)
        self._make_crew([arch_agent], [arch_task]).kickoff()

        evaluator = make_evaluator_agent()
        cv_advisor = make_cv_advisor_agent()
        report_writer = make_career_report_writer()
        eval_task = make_eval_task(jd, cv, evaluator, cd)
        cv_task = make_cv_advice_task(jd, cv, cv_advisor, cd, eval_task)
        report_task = make_career_report_task(jd, report_writer, cd, eval_task, cv_task)

        return self._make_crew(
            [evaluator, cv_advisor, report_writer],
            [eval_task, cv_task, report_task],
        ).kickoff()


def build_career_crew(job_desc: str, cv_text: str = "", step_cb=None, task_cb=None) -> CareerOpsPipeline:
    return CareerOpsPipeline(job_desc, cv_text, step_cb, task_cb)


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
    """Agent 2 — Mistral large: statistical reasoning and interpretation."""
    return Agent(
        llm=llm_large,
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
    """Agent 3 — Mistral small for generation; Mistral large for tool-calling decisions."""
    return Agent(
        llm=llm_small,
        function_calling_llm=llm_large,
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
      Agent 2 — Stats Analyst    → mistral-large-latest  (Mistral Cloud)
      Agent 3 — Viz Engineer     → mistral-small-latest  (Mistral Cloud)
    """
    print(f"\n{'='*60}")
    print(f"  CrewAI DataAnalyst Crew — Mistral")
    print(f"  File: {filename}")
    print(f"  Agents:")
    print(f"    [1] Data Cleaner    → mistral-large-latest  (Mistral Cloud)")
    print(f"    [2] Stats Analyst   → mistral-large-latest  (Mistral Cloud)")
    print(f"    [3] Viz Engineer    → mistral-small-latest  (Mistral Cloud)")
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
    parser = argparse.ArgumentParser(description="Ibn Al-Haytham — 7-agent hybrid research pipeline")
    parser.add_argument(
        "--topic", "-t",
        default="Artificial Intelligence in Healthcare",
        help="Research topic (default: 'Artificial Intelligence in Healthcare')",
    )
    args = parser.parse_args()

    search_provider = "LinkUp (deep)" if _linkup_key else ("Serper" if _serper_key else "DuckDuckGo (free)")
    print(f"\n{'='*60}")
    print(f"  Ibn Al-Haytham — 7-Agent Hybrid Research Pipeline")
    print(f"  Topic : {args.topic}")
    print(f"  Search: {search_provider}")
    print(f"  Pipeline:")
    print(f"    Phase 1 (sequential)")
    print(f"      [1] Scout      → mistral-small-latest  (topic map + mode detect)")
    print(f"      [2] Filter     → mistral-small-latest  (source curation)")
    print(f"    Phase 2 (parallel)")
    print(f"      [3] IdeaGen    → mistral-large-latest  (hypotheses + angles)")
    print(f"      [4] Validator  → mistral-large-latest  (cross-check + flag weak)")
    print(f"    Phase 3 (sequential)")
    print(f"      [5] Synthesizer→ mistral-large-latest  (unified narrative)")
    print(f"      [6] Critic     → mistral-large-latest  (logic review)")
    print(f"      [7] Writer     → mistral-large-latest  (final article)")
    print(f"{'='*60}\n")

    pipeline = build_crew(args.topic)
    result = pipeline.kickoff()

    print(f"\n{'='*60}")
    print("  FINAL OUTPUT")
    print(f"{'='*60}")
    print(result)
    print(f"\nFiles saved to research output dir:")
    print("  task1_scout.txt        — topic map + [MODE: X] tag")
    print("  task2_filter.txt       — curated sources")
    print("  task3a_ideas.txt       — hypotheses + novel angles")
    print("  task3b_validation.txt  — cross-checked claims")
    print("  task4_synthesis.txt    — unified narrative")
    print("  task5_critique.txt     — logic review notes")
    print("  task6_final_report.md  — final article with [Ref N] citations")


if __name__ == "__main__":
    main()
