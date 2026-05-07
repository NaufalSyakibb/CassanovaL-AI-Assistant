# Academic Swarm Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a meta-orchestrated academic researcher swarm (8 named agents) as a fourth Crew Mode pipeline alongside Ibn Al-Haytham, DataAnalyst, and Career Ops.

**Architecture:** `_classify_topic()` makes a direct Mistral API call to select Quick/Deep/Academic mode. `AcademicSwarmPipeline.kickoff()` then runs the matching agent subset using the same CrewAI + ThreadPoolExecutor patterns already in `crewai_agents.py`. Sokrates critic loop re-runs Averroes up to 3× until score ≥ 8 or rounds exhausted. Darwin's final report is auto-ingested into the wiki via `write_research_to_wiki`.

**Tech Stack:** Python, CrewAI, Mistral AI (mistral-small + mistral-large), Semantic Scholar API, LangChain wiki tools, React (Babel JSX via CDN, no build step)

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `crewai_agents.py` | Modify | Add `_classify_topic()`, 8 agent factories, 8+ task factories, `AcademicSwarmPipeline`, `build_academic_swarm` |
| `server.py` | Modify | Add `"academic_swarm"` branch to `_run_crew_background` dispatch + output collection |
| `static/index/overlays.jsx` | Modify | Add 4th pipeline button, Academic Swarm node list, time estimate |

---

## Task 1: `_classify_topic` helper + agent/task factories (crewai_agents.py)

**Files:**
- Modify: `crewai_agents.py` — add after the `_research_dir()` function (around line 254)

### Step 1.1 — Add `datetime` import and `_classify_topic` helper

Add to the imports at the top of `crewai_agents.py` (after `from pathlib import Path`):

```python
from datetime import datetime
```

Then add this function immediately after the `_research_dir()` function (after line ~253):

```python
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
```

- [ ] **Step 1.1: Add `datetime` import** — open `crewai_agents.py` and add `from datetime import datetime` after `from pathlib import Path` on line 17.

- [ ] **Step 1.2: Add helpers** — add the `_classify_topic`, `_read_swarm_file`, `_swarm_path`, `_parse_critic_output` functions after `_research_dir()` (after line 253).

- [ ] **Step 1.3: Verify helpers parse correctly**

```bash
cd c:\Users\muham\OneDrive\Dokumen\Python\ai_python
python -c "
from crewai_agents import _parse_critic_output, _swarm_path
from pathlib import Path
r = _parse_critic_output('{\"score\": 9, \"verdict\": \"PASS\", \"gaps\": [], \"feedback\": \"Good\"}')
assert r['score'] == 9, r
assert r['verdict'] == 'PASS', r
p = _swarm_path(Path('AI Data/Ferry Agent'), '20260507_1430', '1_scout.txt')
assert 'swarm_20260507_1430_1_scout.txt' in p, p
print('OK')
"
```

Expected: `OK`

- [ ] **Step 1.4: Commit**

```bash
git add crewai_agents.py
git commit -m "feat(swarm): add _classify_topic, _read_swarm_file, _swarm_path, _parse_critic_output helpers"
```

---

### Step 1.5 — Add 8 agent factories

Add the following agent factories to `crewai_agents.py` after the helpers above:

```python
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
```

- [ ] **Step 1.5: Add 8 agent factories** — paste the agent factory code above into `crewai_agents.py` after the helpers from Step 1.2.

- [ ] **Step 1.6: Verify import**

```bash
python -c "
from crewai_agents import (
    make_hypatia, make_bacon, make_popper, make_leibniz,
    make_averroes, make_sokrates, make_darwin,
    _classify_topic, _parse_critic_output
)
print('All agent factories importable: OK')
"
```

Expected: `All agent factories importable: OK`

- [ ] **Step 1.7: Commit**

```bash
git add crewai_agents.py
git commit -m "feat(swarm): add Hypatia, Bacon, Popper, Leibniz, Averroes, Sokrates, Darwin agent factories"
```

---

### Step 1.8 — Add 8 task factories

Add these task factories to `crewai_agents.py` immediately after the agent factories above:

```python
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
    ctx_scout  = scout_out[:3000]  if scout_out  else "[Not available]"
    ctx_bacon  = bacon_out[:2000]  if bacon_out  else "[Not available — Quick/Deep mode]"
    ctx_popper = popper_out[:2000] if popper_out else "[Not available — Quick/Deep mode]"
    ctx_leibniz= leibniz_out[:1500]if leibniz_out else "[Not available — Quick/Deep mode]"
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
```

- [ ] **Step 1.8: Add task factories** — paste the task factory code above into `crewai_agents.py` after the agent factories.

- [ ] **Step 1.9: Verify all factories importable**

```bash
python -c "
from crewai_agents import (
    make_hypatia_task, make_bacon_task, make_popper_task, make_leibniz_task,
    make_averroes_task, make_averroes_revision_task,
    make_sokrates_task, make_darwin_task
)
print('All task factories importable: OK')
"
```

Expected: `All task factories importable: OK`

- [ ] **Step 1.10: Commit**

```bash
git add crewai_agents.py
git commit -m "feat(swarm): add Hypatia, Bacon, Popper, Leibniz, Averroes, Sokrates, Darwin task factories"
```

---

## Task 2: `AcademicSwarmPipeline` class + `build_academic_swarm`

**Files:**
- Modify: `crewai_agents.py` — add pipeline class after the task factories

- [ ] **Step 2.1: Add `AcademicSwarmPipeline` class**

Add this class to `crewai_agents.py` immediately after the task factories:

```python
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
        self.ts: str = ""   # set at kickoff start; readable after kickoff for output collection

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
        """Post-pipeline: ingest final report into Cicero's wiki."""
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
            # ── Quick: Hypatia → Darwin ───────────────────────────────────────
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
                self._log(f"[SWARM] Sokrates PASS — proceeding to Darwin")
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

        # ── WikiIngester ──────────────────────────────────────────────────────
        self._wiki_ingest(out_dir)

        return {"mode": mode, "ts": ts, "critic_rounds": len(critic_rounds)}


def build_academic_swarm(
    topic: str, step_cb=None, task_cb=None
) -> AcademicSwarmPipeline:
    return AcademicSwarmPipeline(topic, step_cb, task_cb)
```

- [ ] **Step 2.2: Verify the class and builder function import**

```bash
python -c "
from crewai_agents import AcademicSwarmPipeline, build_academic_swarm
p = build_academic_swarm('test topic')
assert p.topic == 'test topic'
assert p.ts == ''
print('AcademicSwarmPipeline importable and constructable: OK')
"
```

Expected: `AcademicSwarmPipeline importable and constructable: OK`

- [ ] **Step 2.3: Verify _classify_topic returns correct structure**

```bash
python -c "
from crewai_agents import _classify_topic
result = _classify_topic('quantum computing basics')
assert 'mode' in result, result
assert result['mode'] in ('quick', 'deep', 'academic'), result
assert 'rationale' in result, result
assert 'angles' in result and len(result['angles']) > 0, result
print(f'_classify_topic OK: mode={result[\"mode\"]}')
"
```

Expected: `_classify_topic OK: mode=<quick|deep|academic>`

- [ ] **Step 2.4: Commit**

```bash
git add crewai_agents.py
git commit -m "feat(swarm): add AcademicSwarmPipeline class and build_academic_swarm factory"
```

---

## Task 3: `server.py` — add `academic_swarm` dispatch + output collection

**Files:**
- Modify: `server.py:446-508` — `_run_crew_background` function

- [ ] **Step 3.1: Add `academic_swarm` branch to dispatch block**

In `server.py`, find the `if crew_type == "dataanalyst":` block (around line 446) and replace the entire try block's dispatch section with:

```python
        if crew_type == "dataanalyst":
            from crewai_agents import build_data_crew
            crew = build_data_crew(filename or topic, step_cb=_log, task_cb=_log)
            result = crew.kickoff()
        elif crew_type == "career":
            from crewai_agents import build_career_crew
            crew = build_career_crew(topic, cv_text or "", step_cb=_log, task_cb=_log)
            result = crew.kickoff()
        elif crew_type == "academic_swarm":
            from crewai_agents import build_academic_swarm
            pipeline = build_academic_swarm(topic, step_cb=_log, task_cb=_log)
            result = pipeline.kickoff()
        else:
            from crewai_agents import build_crew
            crew = build_crew(topic, step_cb=_log, task_cb=_log)
            result = crew.kickoff()
```

- [ ] **Step 3.2: Add `academic_swarm` output collection block**

In `server.py`, find the `elif crew_type == "career":` output collection block (around line 487) and add a new `elif` for `academic_swarm` immediately after it:

```python
        elif crew_type == "academic_swarm":
            from crewai_agents import _research_dir
            research_out = _research_dir()
            # pipeline.ts is set during kickoff; result dict contains ts
            ts = (result or {}).get("ts", "")
            if ts:
                for pattern in (
                    f"swarm_{ts}_0_meta.txt",
                    f"swarm_{ts}_1_scout.txt",
                    f"swarm_{ts}_2_analysis.txt",
                    f"swarm_{ts}_3_validation.txt",
                    f"swarm_{ts}_4_citations.txt",
                    f"swarm_{ts}_5_synthesis.txt",
                    f"swarm_{ts}_6_critique.txt",
                    f"swarm_{ts}_final_report.md",
                ):
                    p = research_out / pattern
                    if p.exists():
                        outputs[pattern] = p.read_text(encoding="utf-8")
```

- [ ] **Step 3.3: Verify server.py imports correctly**

```bash
python -c "
import server
print('server.py imports OK')
"
```

Expected: `server.py imports OK`  
(If you see an error about missing environment variables, that's fine — the import check itself should succeed.)

- [ ] **Step 3.4: Commit**

```bash
git add server.py
git commit -m "feat(swarm): add academic_swarm dispatch and output collection to server.py"
```

---

## Task 4: `overlays.jsx` — add Academic Swarm to CrewDrawer

**Files:**
- Modify: `static/index/overlays.jsx:128-380`

- [ ] **Step 4.1: Add `academic_swarm` to the pipeline selector buttons**

In `overlays.jsx`, find the `crew-type-row` div (around line 249) and add a fourth button after the Career Ops button:

```jsx
                <button className={`crew-type ${crewType==='academic_swarm'?'active':''}`} onClick={() => setCrewType('academic_swarm')}>
                  <div className="crew-type-title">Academic Swarm</div>
                  <div className="crew-type-sub">Al-Biruni → [Hypatia…Darwin]</div>
                </button>
```

- [ ] **Step 4.2: Add `academic_swarm` node list to the `nodes` computation**

In `overlays.jsx`, find the `const nodes = crewType === 'career'` block (around line 201). Add the academic_swarm case before the final `/* dataanalyst */` fallback:

Replace:
```jsx
    : /* dataanalyst */ [
```

With:
```jsx
    : crewType === 'academic_swarm'
    ? [
        { num:'0', name:'Al-Biruni',  role:'Classify depth: Quick/Deep/Academic', llm:'mistral-small', phase:'Phase 0', hue:'var(--hue-alfred)' },
        { num:'1', name:'Hypatia',    role:'Broad academic search',                llm:'mistral-small', phase:'Phase 1', hue:'var(--hue-cicero)' },
        { num:'2', name:'Bacon',      role:'Deep paper analysis',                  llm:'mistral-large', phase:'Phase 2', hue:'var(--hue-linus)' },
        { num:'3', name:'Popper',     role:'Evidence cross-check',                 llm:'mistral-large', phase:'Phase 2', parallel:true, hue:'var(--hue-linus)' },
        { num:'4', name:'Leibniz',    role:'Citation chain tracer',                llm:'mistral-small', phase:'Phase 3', hue:'var(--hue-najwa)' },
        { num:'5', name:'Averroes',   role:'Synthesize findings + citations',      llm:'mistral-large', phase:'Phase 4', hue:'var(--hue-cicero)' },
        { num:'6', name:'Sokrates',   role:'Critic loop (up to 3×)',               llm:'mistral-large', phase:'Phase 5', hue:'var(--hue-alfred)' },
        { num:'7', name:'Darwin',     role:'Final academic report',                llm:'mistral-large', phase:'Phase 6', hue:'var(--hue-najwa)' },
      ]
    : /* dataanalyst */ [
```

- [ ] **Step 4.3: Add topic input section for `academic_swarm`**

In `overlays.jsx`, find the input section that starts with `{crewType === 'career' ? (` (around line 266). Add `academic_swarm` to the `research` branch — since both use the same topic textarea, change:

```jsx
              ) : crewType === 'research' ? (
```

To:

```jsx
              ) : crewType === 'research' || crewType === 'academic_swarm' ? (
```

- [ ] **Step 4.4: Add time estimate for `academic_swarm`**

In `overlays.jsx`, find the time estimate block in `crew-meta-line` (around line 370):

```jsx
                : crewType === 'research' ? 'Estimated 3–6 min · Mistral LLM'
                : crewType === 'career'   ? 'Estimated 2–4 min · Mistral LLM'
```

Add a line for `academic_swarm`:

```jsx
                : crewType === 'research'        ? 'Estimated 3–6 min · Mistral LLM'
                : crewType === 'career'          ? 'Estimated 2–4 min · Mistral LLM'
                : crewType === 'academic_swarm'  ? 'Estimated 2–10 min · Quick/Deep/Academic'
```

- [ ] **Step 4.5: Fix the launch button `disabled` condition**

In `overlays.jsx`, find the `crew-launch` button's `disabled` prop (around line 364):

```jsx
              disabled={status === 'running' || !topic.trim() || (crewType === 'dataanalyst' && !filename) || (crewType === 'career' && !topic.trim())}>
```

This already correctly disables when `topic` is empty — no change needed for `academic_swarm` since it only needs a topic. Verify this is the case and leave it unchanged.

- [ ] **Step 4.6: Start the server and test the UI manually**

```bash
$env:PYTHONUTF8=1; python server.py
```

Open `http://localhost:8000` in browser.  
1. Click the crew mode button (Rocket icon in sidebar)
2. Verify "Academic Swarm" appears as a 4th pipeline button
3. Click "Academic Swarm" — verify the 8-node crew diagram shows (Al-Biruni through Darwin)
4. Verify Phase 2 shows the "parallel" badge on Bacon and Popper nodes
5. Enter a topic and verify the Launch button becomes enabled
6. Close the drawer without launching (no need to run the full pipeline for UI verification)

- [ ] **Step 4.7: Commit**

```bash
git add static/index/overlays.jsx
git commit -m "feat(swarm): add Academic Swarm pipeline to CrewDrawer UI"
```

---

## Task 5: Smoke test + final verification

- [ ] **Step 5.1: Full import check**

```bash
python -c "
from crewai_agents import (
    AcademicSwarmPipeline,
    build_academic_swarm,
    _classify_topic,
    _read_swarm_file,
    _swarm_path,
    _parse_critic_output,
    make_hypatia, make_bacon, make_popper, make_leibniz,
    make_averroes, make_sokrates, make_darwin,
    make_hypatia_task, make_bacon_task, make_popper_task,
    make_leibniz_task, make_averroes_task,
    make_averroes_revision_task, make_sokrates_task, make_darwin_task,
)
print('Full import check: OK')
"
```

Expected: `Full import check: OK`

- [ ] **Step 5.2: Server startup check**

```bash
python -c "import server; print('server.py import OK')"
```

Expected: `server.py import OK`

- [ ] **Step 5.3: Verify no duplicate tool names in existing agents still pass**

```bash
python -c "
from agents.task_agent import TASK_AGENT_TOOLS
from agents.research_agent import RESEARCH_AGENT_TOOLS
from agents.fitness_agent import FITNESS_TOOLS
for name, tools in [
    ('task', TASK_AGENT_TOOLS),
    ('research', RESEARCH_AGENT_TOOLS),
    ('fitness', FITNESS_TOOLS),
]:
    names = [t.name for t in tools]
    dupes = [n for n in names if names.count(n) > 1]
    assert not dupes, f'{name} has duplicate tools: {dupes}'
    print(f'{name}: {len(tools)} tools, no duplicates OK')
"
```

Expected: 3 lines each ending in `OK`

- [ ] **Step 5.4: _classify_topic end-to-end test**

```bash
python -c "
from crewai_agents import _classify_topic
for topic in ['Python list comprehension', 'CRISPR gene editing ethics', 'climate change tipping points']:
    r = _classify_topic(topic)
    assert r['mode'] in ('quick', 'deep', 'academic'), r
    print(f'  {topic[:40]!r:42} → {r[\"mode\"]}')
print('_classify_topic end-to-end: OK')
"
```

Expected: 3 lines showing topic → mode mapping, then `OK`

- [ ] **Step 5.5: Final commit**

```bash
git add crewai_agents.py server.py static/index/overlays.jsx
git commit -m "feat(swarm): Academic Swarm pipeline complete — Al-Biruni through Darwin, wiki ingest, Crew Mode UI"
```

---

## Quick Reference: What Was Built

| Component | Location | What it does |
|-----------|----------|-------------|
| `_classify_topic(topic)` | `crewai_agents.py` | Direct Mistral call → `{mode, rationale, angles}` |
| `_read_swarm_file(out_dir, ts, suffix)` | `crewai_agents.py` | Read `swarm_{ts}_{suffix}` from disk |
| `_swarm_path(out_dir, ts, suffix)` | `crewai_agents.py` | Return output file path string |
| `_parse_critic_output(text)` | `crewai_agents.py` | Parse Sokrates JSON from task output |
| `make_hypatia(topic)` | `crewai_agents.py` | Semantic Scholar + web search agent |
| `make_bacon(topic)` | `crewai_agents.py` | Paper analysis agent |
| `make_popper(topic)` | `crewai_agents.py` | Evidence cross-check agent |
| `make_leibniz(topic)` | `crewai_agents.py` | Citation chain agent |
| `make_averroes(topic)` | `crewai_agents.py` | Synthesis agent |
| `make_sokrates(topic)` | `crewai_agents.py` | Critic loop agent |
| `make_darwin(topic)` | `crewai_agents.py` | Final report writer agent |
| `AcademicSwarmPipeline` | `crewai_agents.py` | Pipeline orchestrator with critic loop |
| `build_academic_swarm(topic)` | `crewai_agents.py` | Factory for server.py |
| `_run_crew_background` | `server.py` | Added `academic_swarm` dispatch + output collection |
| `CrewDrawer` | `static/index/overlays.jsx` | Added 4th pipeline button + 8-node diagram |
