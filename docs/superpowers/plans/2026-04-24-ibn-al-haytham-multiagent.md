# Ibn Al-Haytham Multi-Agent Research System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing 2-agent Drafter→Critic research crew with a 7-agent phase-based hybrid research pipeline (Scout→Filter→[IdeaGen‖Validator]→Synthesizer→Critic→Writer) using Mistral + Gemma models, fully integrated with the web frontend.

**Architecture:** Three phases — Phase 1 (Scout+Filter, sequential), Phase 2 (IdeaGen+Validator, parallel via ThreadPoolExecutor), Phase 3 (Synthesizer+Critic+Writer, sequential). An `IbnAlHaythamPipeline` class orchestrates all phases and exposes a `.kickoff()` method so `server.py` needs zero changes beyond the output file list.

**Tech Stack:** CrewAI, Mistral AI (mistral-large/small), Gemma 4 via Google AI Studio, LinkUp/DuckDuckGo search, FastAPI, React (JSX), concurrent.futures.ThreadPoolExecutor

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `crewai_agents.py` | Modify | Remove 2-agent research functions; add 7 agent factories, 7 task factories, `_read_phase_output`, `IbnAlHaythamPipeline`, updated `build_crew()` |
| `server.py` | Modify | Update output file list in `_run_crew_background` (lines ~292–323) |
| `static/index/overlays.jsx` | Modify | Update `nodes` array to 7 agents with phases, update pipeline description and meta text |

---

## Task 1: Scaffold — remove old research functions, add import

**Files:**
- Modify: `crewai_agents.py`

- [x] **Step 1: Add `ThreadPoolExecutor` import**

Open `crewai_agents.py`. After the existing imports block (after `from crewai.tools import BaseTool`), add:

```python
from concurrent.futures import ThreadPoolExecutor
```

- [x] **Step 2: Delete old research agent/task factory functions**

Remove these four functions entirely (lines ~193–359 in the original file):
- `make_drafter(topic)`
- `make_critic(topic)`
- `make_draft_task(topic, agent)`
- `make_critique_task(topic, agent, draft_task)`

Keep everything else: LLM setup, `LinkUpSearchTool`, `DuckDuckGoTool`, `research_search_tool`, `search_tool`, `file_writer`, `_research_dir()`, all DataAnalyst functions.

- [x] **Step 3: Add `_read_phase_output` helper**

Directly above the `# ── Agent Factory` comment that you'll add next, insert:

```python
def _read_phase_output(fname: str) -> str:
    """Read a phase output file from research dir; return empty string if missing."""
    p = _research_dir() / fname
    return p.read_text(encoding="utf-8") if p.exists() else ""
```

- [x] **Step 4: Commit scaffold**

```bash
git add crewai_agents.py
git commit -m "refactor(crew): scaffold 7-agent pipeline — remove old 2-agent research crew"
```

---

## Task 2: Phase 1 agents — Scout + Filter

**Files:**
- Modify: `crewai_agents.py`

- [x] **Step 1: Add `make_scout` function**

After `_read_phase_output`, add:

```python
# ── Research Pipeline: Ibn Al-Haytham (7-Agent) ───────────────────────────────
#
# Phase 1 (sequential): Scout → Filter
# Phase 2 (parallel):   IdeaGen ‖ Validator
# Phase 3 (sequential): Synthesizer → Critic → Writer

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
```

- [x] **Step 2: Add `make_filter_agent` function**

```python
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
```

- [x] **Step 3: Commit**

```bash
git add crewai_agents.py
git commit -m "feat(crew): add Phase 1 agents — Scout + Filter"
```

---

## Task 3: Phase 2 agents — IdeaGen + Validator

**Files:**
- Modify: `crewai_agents.py`

- [x] **Step 1: Add `make_idea_gen` function**

```python
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
```

- [x] **Step 2: Add `make_validator_agent` function**

```python
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
```

- [x] **Step 3: Commit**

```bash
git add crewai_agents.py
git commit -m "feat(crew): add Phase 2 agents — IdeaGen + Validator (parallel)"
```

---

## Task 4: Phase 3 agents — Synthesizer + Critic + Writer

**Files:**
- Modify: `crewai_agents.py`

- [x] **Step 1: Add `make_synthesizer` function**

```python
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
```

- [x] **Step 2: Add `make_critic_agent` function**

```python
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
            "Key rule: soften, don't remove. Replace 'X causes Y' with "
            "'X is associated with Y' where causation is unproven."
        ),
        tools=[],
        allow_delegation=False,
        verbose=True,
        max_iter=6,
    )
```

- [x] **Step 3: Add `make_writer` function**

```python
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
```

- [x] **Step 4: Commit**

```bash
git add crewai_agents.py
git commit -m "feat(crew): add Phase 3 agents — Synthesizer + Critic + Writer"
```

---

## Task 5: Phase 1 tasks — scout_task + filter_task

**Files:**
- Modify: `crewai_agents.py`

- [x] **Step 1: Add `make_scout_task` function**

```python
# ── Task Factories ────────────────────────────────────────────────────────────

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
```

- [x] **Step 2: Add `make_filter_task` function**

```python
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
```

- [x] **Step 3: Commit**

```bash
git add crewai_agents.py
git commit -m "feat(crew): add Phase 1 tasks — scout_task + filter_task"
```

---

## Task 6: Phase 2 tasks — idea_task + valid_task

**Files:**
- Modify: `crewai_agents.py`

Note: Phase 2 tasks receive `filter_context` as a string (not `context=[task]`) because IdeaGen and Validator run in **separate Crew objects**. The filter output text is embedded directly in the task description.

- [x] **Step 1: Add `make_idea_task` function**

```python
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
```

- [x] **Step 2: Add `make_valid_task` function**

```python
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
```

- [x] **Step 3: Commit**

```bash
git add crewai_agents.py
git commit -m "feat(crew): add Phase 2 tasks — idea_task + valid_task"
```

---

## Task 7: Phase 3 tasks — synth_task + critique_task + write_task

**Files:**
- Modify: `crewai_agents.py`

Note: `make_synth_task` receives `ideas` and `validation` as strings (embedded in description). `make_critique_task_p3` and `make_write_task` use CrewAI `context=[prev_task]` since they're in the same Phase 3 Crew.

- [x] **Step 1: Add `make_synth_task` function**

```python
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
```

- [x] **Step 2: Add `make_critique_task_p3` function**

```python
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
```

- [x] **Step 3: Add `make_write_task` function**

```python
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
```

- [x] **Step 4: Commit**

```bash
git add crewai_agents.py
git commit -m "feat(crew): add Phase 3 tasks — synthesis + critique + write"
```

---

## Task 8: `IbnAlHaythamPipeline` orchestrator + update `build_crew()`

**Files:**
- Modify: `crewai_agents.py`

- [x] **Step 1: Add `IbnAlHaythamPipeline` class**

After all task factory functions, add:

```python
# ── Pipeline Orchestrator ─────────────────────────────────────────────────────

class IbnAlHaythamPipeline:
    """7-agent hybrid research pipeline (Phase-Based + Parallel Phase 2).

    Phase 1 (sequential): Scout → Filter
    Phase 2 (parallel):   IdeaGen ‖ Validator  (ThreadPoolExecutor)
    Phase 3 (sequential): Synthesizer → Critic → Writer
    """

    def __init__(self, topic: str, step_cb=None, task_cb=None):
        self.topic    = topic
        self.step_cb  = step_cb
        self.task_cb  = task_cb

    def _make_crew(self, agents, tasks) -> Crew:
        return Crew(
            agents=agents,
            tasks=tasks,
            verbose=self.step_cb is None,
            step_callback=self.step_cb,
            task_callback=self.task_cb,
        )

    def kickoff(self):
        topic = self.topic

        # ── Phase 1: Scout → Filter ───────────────────────────────────────
        scout        = make_scout(topic)
        filter_agent = make_filter_agent(topic)
        scout_task   = make_scout_task(topic, scout)
        filter_task  = make_filter_task(topic, filter_agent, scout_task)

        self._make_crew(
            [scout, filter_agent],
            [scout_task, filter_task],
        ).kickoff()

        filter_context = _read_phase_output("task2_filter.txt")

        # ── Phase 2: IdeaGen ‖ Validator (parallel) ───────────────────────
        idea_gen   = make_idea_gen(topic)
        validator  = make_validator_agent(topic)
        idea_task  = make_idea_task(topic, idea_gen, filter_context)
        valid_task = make_valid_task(topic, validator, filter_context)

        idea_crew  = self._make_crew([idea_gen],  [idea_task])
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
            raise RuntimeError(
                "Phase 2 completely failed — both IdeaGen and Validator crashed."
            )

        # ── Phase 3: Synthesizer → Critic → Writer ────────────────────────
        synthesizer  = make_synthesizer(topic)
        critic       = make_critic_agent(topic)
        writer       = make_writer(topic)
        synth_task   = make_synth_task(topic, synthesizer, ideas_output, valid_output)
        crit_task    = make_critique_task_p3(topic, critic, synth_task)
        write_task   = make_write_task(topic, writer, crit_task)

        return self._make_crew(
            [synthesizer, critic, writer],
            [synth_task, crit_task, write_task],
        ).kickoff()
```

- [x] **Step 2: Replace `build_crew()` function**

Find the old `build_crew` function and replace it entirely with:

```python
def build_crew(topic: str, step_cb=None, task_cb=None) -> IbnAlHaythamPipeline:
    """Build the 7-agent Ibn Al-Haytham hybrid research pipeline.

    Phase 1 (sequential): Scout → Filter
    Phase 2 (parallel):   IdeaGen ‖ Validator
    Phase 3 (sequential): Synthesizer → Critic → Writer
    """
    return IbnAlHaythamPipeline(topic, step_cb, task_cb)
```

- [x] **Step 3: Update CLI `main()` to reflect new pipeline**

Find the `main()` function and update the print block to:

```python
def main():
    parser = argparse.ArgumentParser(description="CrewAI Ibn Al-Haytham research pipeline")
    parser.add_argument(
        "--topic", "-t",
        default="Artificial Intelligence in Healthcare",
        help="Research topic",
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Ibn Al-Haytham — 7-Agent Hybrid Research Pipeline")
    print(f"  Topic: {args.topic}")
    search_provider = "LinkUp (deep)" if _linkup_key else ("Serper" if _serper_key else "DuckDuckGo (free)")
    print(f"  Search: {search_provider}")
    print(f"  Pipeline:")
    print(f"    Phase 1: Scout       → mistral-small  (map + mode detect)")
    print(f"             Filter      → mistral-small  (curate sources)")
    print(f"    Phase 2: IdeaGen     → gemma-4        (novel angles)   [parallel]")
    print(f"             Validator   → gemma-4        (evidence check) [parallel]")
    print(f"    Phase 3: Synthesizer → mistral-large  (merge)")
    print(f"             Critic      → mistral-large  (logic review)")
    print(f"             Writer      → mistral-large  (final article)")
    print(f"{'='*60}\n")

    crew = build_crew(args.topic)
    result = crew.kickoff()

    print(f"\n{'='*60}")
    print("  FINAL OUTPUT")
    print(f"{'='*60}")
    print(result)
    print(f"\nFiles saved to: {_research_dir()}")
    print("  task1_scout.txt         — topic map + mode declaration")
    print("  task2_filter.txt        — curated sources")
    print("  task3a_ideas.txt        — novel angles (IdeaGen)")
    print("  task3b_validation.txt   — evidence check (Validator)")
    print("  task4_synthesis.txt     — merged synthesis")
    print("  task5_critique.txt      — critique notes + refined synthesis")
    print("  task6_final_report.md   — final article")
```

- [x] **Step 4: Commit**

```bash
git add crewai_agents.py
git commit -m "feat(crew): add IbnAlHaythamPipeline orchestrator + update build_crew()"
```

---

## Task 9: Update `server.py` — output file collection

**Files:**
- Modify: `server.py` (~lines 317–323)

- [x] **Step 1: Find and replace the research output file list**

Locate this block in `_run_crew_background`:

```python
        else:
            from crewai_agents import _research_dir
            research_out = _research_dir()
            for fname in ("task1_research.txt", "task2_report.md"):
                p = research_out / fname
                if p.exists():
                    outputs[fname] = p.read_text(encoding="utf-8")
```

Replace with:

```python
        else:
            from crewai_agents import _research_dir
            research_out = _research_dir()
            for fname in (
                "task1_scout.txt",
                "task2_filter.txt",
                "task3a_ideas.txt",
                "task3b_validation.txt",
                "task4_synthesis.txt",
                "task5_critique.txt",
                "task6_final_report.md",
            ):
                p = research_out / fname
                if p.exists():
                    outputs[fname] = p.read_text(encoding="utf-8")
```

- [x] **Step 2: Commit**

```bash
git add server.py
git commit -m "fix(server): update research output file list for 7-agent pipeline"
```

---

## Task 10: Update `overlays.jsx` — 7-node UI with phase display

**Files:**
- Modify: `static/index/overlays.jsx`

- [x] **Step 1: Replace `nodes` definition for research crew**

Find:
```javascript
  const nodes = crewType === 'research'
    ? [
        { num:'I',  name:'Ibn al-Haytham', role:'Research Drafter',    hue:'var(--hue-alfred)' },
        { num:'II', name:'Ibn al-Haytham', role:'Self-Critic & Refiner', hue:'var(--hue-linus)' },
      ]
```

Replace with:
```javascript
  const nodes = crewType === 'research'
    ? [
        { phase:'Phase 1', num:'I',   name:'Ibn al-Haytham', role:'Scout — Map & Mode Detect',  hue:'var(--hue-alfred)',  llm:'mistral-small', parallel:false },
        { phase:'Phase 1', num:'II',  name:'Ibn al-Haytham', role:'Filter — Source Curation',   hue:'var(--hue-alfred)',  llm:'mistral-small', parallel:false },
        { phase:'Phase 2', num:'III', name:'Ibn al-Haytham', role:'IdeaGen — Novel Angles',     hue:'var(--hue-cicero)',  llm:'gemma-4',       parallel:true  },
        { phase:'Phase 2', num:'IV',  name:'Ibn al-Haytham', role:'Validator — Evidence Check', hue:'var(--hue-linus)',   llm:'gemma-4',       parallel:true  },
        { phase:'Phase 3', num:'V',   name:'Ibn al-Haytham', role:'Synthesizer — Merge',        hue:'var(--hue-mansa)',   llm:'mistral-large', parallel:false },
        { phase:'Phase 3', num:'VI',  name:'Ibn al-Haytham', role:'Critic — Logic Review',      hue:'var(--hue-linus)',   llm:'mistral-large', parallel:false },
        { phase:'Phase 3', num:'VII', name:'Ibn al-Haytham', role:'Writer — Final Article',     hue:'var(--hue-davinci)', llm:'mistral-large', parallel:false },
      ]
```

- [x] **Step 2: Replace the node rendering block**

Find the entire `{nodes.map((n, i) => (` block (inside `<div className="crew-section">`) and replace it with:

```javascript
              {crewType === 'research' ? (
                ['Phase 1', 'Phase 2', 'Phase 3'].map(phase => {
                  const phaseNodes = nodes.filter(n => n.phase === phase);
                  const isParallel = phaseNodes.some(n => n.parallel);
                  return (
                    <div key={phase}>
                      <div style={{fontSize:10, letterSpacing:'0.08em', textTransform:'uppercase', color:'var(--ink-3)', padding:'8px 0 4px', marginTop:8, fontFamily:"'Inter', sans-serif"}}>
                        {phase}{isParallel ? ' — Parallel ‖' : ''}
                      </div>
                      {phaseNodes.map((n, i) => (
                        <div key={i} className="crew-node" style={{'--node-hue': n.hue}}>
                          <div className="crew-node-num">{n.num}</div>
                          <div style={{flex:1}}>
                            <div className="crew-node-title">The <em>{n.name}</em></div>
                            <div className="crew-node-role">{n.role}</div>
                          </div>
                          <div style={{display:'flex', alignItems:'center', gap:8}}>
                            {n.llm && <span style={{fontSize:9, opacity:0.45, fontFamily:"'JetBrains Mono', monospace", letterSpacing:'0.04em'}}>{n.llm}</span>}
                            {status === 'done' && <span className="crew-node-check"><IcoCheck/></span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                })
              ) : (
                nodes.map((n, i) => (
                  <div key={i} className="crew-node" style={{'--node-hue': n.hue}}>
                    <div className="crew-node-num">{n.num}</div>
                    <div>
                      <div className="crew-node-title">The <em>{n.name}</em></div>
                      <div className="crew-node-role">{n.role}</div>
                    </div>
                    {status === 'done' && <span className="crew-node-check"><IcoCheck/></span>}
                  </div>
                ))
              )}
```

- [x] **Step 3: Update pipeline selector subtitle for research**

Find:
```javascript
                  <div className="crew-type-sub">Drafter → Critic → Memo</div>
```
Replace with:
```javascript
                  <div className="crew-type-sub">Scout → [IdeaGen ‖ Validator] → Writer</div>
```

- [x] **Step 4: Update crew meta line**

Find:
```javascript
              : 'Estimated 1–3 min · Mistral LLM'}
```
Replace with:
```javascript
              : 'Estimated 3–6 min · Mistral + Gemma'}
```

- [x] **Step 5: Update agent count in crew-label**

The `{nodes.length} agents` count is now dynamic and correct (7 for research, 3 for dataanalyst) — no change needed here since `nodes.length` is already dynamic.

- [x] **Step 6: Commit**

```bash
git add static/index/overlays.jsx
git commit -m "feat(ui): update CrewDrawer to 7-agent Ibn Al-Haytham pipeline with phase display"
```

---

## Task 11: Smoke test

- [x] **Step 1: Install dependencies if needed**

```bash
pip install crewai crewai-tools linkup-sdk
```

Expected: packages install or already present (no error).

- [x] **Step 2: Test CLI — HYBRID mode**

```bash
$env:PYTHONUTF8=1; python crewai_agents.py --topic "Large Language Models in Healthcare"
```

Expected:
- Prints 7-agent pipeline banner
- Phase 1 runs (Scout declares `[MODE: HYBRID]`, Filter curates sources)
- Phase 2 runs in parallel (both IdeaGen and Validator)
- Phase 3 runs (Synthesizer → Critic → Writer)
- 7 output files created in `_research_dir()`

- [x] **Step 3: Verify output files exist**

```bash
python -c "
from crewai_agents import _research_dir
d = _research_dir()
files = ['task1_scout.txt','task2_filter.txt','task3a_ideas.txt','task3b_validation.txt','task4_synthesis.txt','task5_critique.txt','task6_final_report.md']
for f in files:
    p = d / f
    print(f'{f}: {\"OK\" if p.exists() else \"MISSING\"} ({p.stat().st_size if p.exists() else 0} bytes)')
"
```

Expected: all 7 files exist with size > 0.

- [x] **Step 4: Verify mode tag in scout output**

```bash
python -c "
from crewai_agents import _research_dir
txt = (_research_dir() / 'task1_scout.txt').read_text(encoding='utf-8')
print('MODE TAG:', 'FOUND' if '[MODE:' in txt else 'MISSING')
print(txt[:300])
"
```

Expected: `MODE TAG: FOUND` and mode tag visible in first 300 chars.

- [x] **Step 5: Verify citations in final report**

```bash
python -c "
from crewai_agents import _research_dir
txt = (_research_dir() / 'task6_final_report.md').read_text(encoding='utf-8')
import re
refs = re.findall(r'\[Ref \d+\]', txt)
print(f'Inline citations found: {len(refs)}')
ref_section = '[N]' in txt or '## Referensi' in txt
print(f'Reference section: {\"FOUND\" if ref_section else \"MISSING\"}')
"
```

Expected: at least 3 inline citations, reference section found.

- [x] **Step 6: Test web server**

```bash
$env:PYTHONUTF8=1; python server.py
```

Open browser at `http://localhost:8000`, open CrewDrawer (click the crew button), verify:
- Research pipeline shows 7 nodes grouped into Phase 1 / Phase 2 — Parallel ‖ / Phase 3
- Each node shows LLM badge (mistral-small / gemma-4 / mistral-large)
- Pipeline selector says `"Scout → [IdeaGen ‖ Validator] → Writer"`
- Meta line says `"Estimated 3–6 min · Mistral + Gemma"`

- [x] **Step 7: Test via web UI end-to-end**

Enter topic `"Blockchain in Supply Chain"`, click Launch.
Expected:
- Status shows `running`
- Logs stream in
- After completion, Results modal shows 7 file tabs

- [x] **Step 8: Final commit**

```bash
git add -A
git commit -m "feat: Ibn Al-Haytham 7-agent hybrid research pipeline — fully operational"
```
