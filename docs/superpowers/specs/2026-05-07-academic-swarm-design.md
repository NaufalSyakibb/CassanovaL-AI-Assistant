# Academic Swarm Pipeline — Design Spec
**Date:** 2026-05-07  
**Reference:** [PaperBanana](https://github.com/dwzhu-pku/PaperBanana) architecture  
**Status:** Approved

---

## Overview

A meta-orchestrated academic researcher swarm added to CassanovaL's Crew Mode. Inspired by PaperBanana's flexible pipeline modes and Critic-loop pattern. A MetaOrchestrator agent (Al-Biruni) reads the research topic and automatically selects one of three depth tiers (Quick / Deep / Academic), then runs the appropriate subset of specialized agents. Final output is a structured markdown report saved to `AI Data/Ferry Agent/` and auto-ingested into the wiki.

---

## Architecture

```
User → Crew Mode ("Academic Swarm") → POST /api/crew/kickoff {pipeline: "academic_swarm", topic: "..."}
                        ↓
            AcademicSwarmPipeline.kickoff(topic)   [background thread]
                        ↓
         Phase 0 — Al-Biruni (MetaOrchestrator)
         mistral-small-latest: topic → {mode, rationale, angles}
                        ↓
         ┌──────────────────────────────────────────────────┐
         │  QUICK (2 agents)                                 │
         │  Hypatia → Darwin                                 │
         │                                                   │
         │  DEEP (5 agents)                                  │
         │  Hypatia → Bacon → Averroes → Sokrates(×1) → Darwin │
         │                                                   │
         │  ACADEMIC (7 agents)                              │
         │  Hypatia → [Bacon ‖ Popper] → Leibniz            │
         │          → Averroes → Sokrates(×3) → Darwin       │
         └──────────────────────────────────────────────────┘
                        ↓
                   WikiIngester
         saves final_report.md + ingest to wiki
```

---

## Agent Roster

| # | Persona | Role | Model | Modes |
|---|---------|------|-------|-------|
| 0 | **Al-Biruni** (MetaOrchestrator) | Classifies topic → selects Quick/Deep/Academic | mistral-small-latest | all |
| 1 | **Hypatia** (Scout) | Broad academic search: Semantic Scholar + web fallback | mistral-small-latest | all |
| 2 | **Francis Bacon** (Analyst) | Deep-reads top papers: methodology, claims, limitations | mistral-large-latest | deep + academic |
| 3 | **Karl Popper** (Validator) | Cross-checks claims, flags contradictions, rates evidence quality | mistral-large-latest | academic only (parallel with Bacon) |
| 4 | **Leibniz** (CitationChainer) | Follows citation chains → foundational literature map | mistral-small-latest | academic only |
| 5 | **Averroes** (Synthesizer) | Merges all findings into unified narrative with [Ref N] citations | mistral-large-latest | deep + academic |
| 6 | **Sokrates** (Critic) | Evaluates synthesis: coverage/gaps/logic → `{score, gaps, verdict: PASS\|REVISE}` | mistral-large-latest | deep(×1) + academic(×3) |
| 7 | **Darwin** (Writer) | Produces final structured academic markdown report | mistral-large-latest | all |

### Al-Biruni Classification Logic
- One `mistral-small-latest` call at pipeline start
- Input: topic string
- Output: `{"mode": "quick"|"deep"|"academic", "rationale": str, "angles": [str, ...]}`
- Classification signals:
  - **Quick**: well-known factual topic, straightforward explanation request
  - **Deep**: nuanced topic, recent developments needed, comparative analysis
  - **Academic**: cutting-edge research, contested findings, citation-heavy, requires Semantic Scholar

### Sokrates Critic Loop (PaperBanana-faithful)
- Evaluates Averroes' synthesis
- Returns: `{"score": 0-10, "gaps": [...], "feedback": str, "verdict": "PASS"|"REVISE"}`
- If `verdict == "REVISE"`: feedback sent back to Averroes for one more synthesis pass
- Loop limit: 3 rounds (Academic), 1 round (Deep)
- If `score >= 8` on any round: early exit regardless of round count

---

## Pipeline Modes

| Mode | Active Agents | Est. Runtime | Al-Biruni triggers when |
|------|--------------|-------------|------------------------|
| **Quick** | Al-Biruni + Hypatia + Darwin | ~2 min | Simple, well-known topic |
| **Deep** | + Bacon + Averroes + Sokrates(×1) | ~5 min | Nuanced, recent research needed |
| **Academic** | + Popper (‖ Bacon) + Leibniz + Sokrates(×3) | ~10 min | Cutting-edge, contested, citation-heavy |

---

## Data Flow

Single dictionary accumulated through pipeline (PaperBanana-style data accumulation pattern):

```python
data = {
    # Seeded by pipeline runner
    "topic": str,

    # Phase 0 — Al-Biruni
    "mode": "quick" | "deep" | "academic",
    "rationale": str,
    "angles": [str, ...],

    # Phase 1 — Hypatia
    "scout_sources": [
        {"title": str, "authors": str, "year": int,
         "abstract": str, "url": str, "citations": int}
    ],

    # Phase 2 — Bacon (deep+)
    "analyst_summaries": [
        {"paper_id": str, "methodology": str, "claims": [str], "limitations": [str]}
    ],

    # Phase 2 — Popper (academic, parallel with Bacon)
    "validator_matrix": {
        "evidence_quality": {str: "HIGH"|"MEDIUM"|"LOW"},
        "contradictions": [{"claim": str, "sources_for": [...], "sources_against": [...]}]
    },

    # Phase 3 — Leibniz (academic)
    "citation_map": {
        "foundational": [str],   # seminal papers
        "recent": [str],          # last 3 years
        "gaps": [str]             # missing links in literature
    },

    # Phase 4 — Averroes (deep+) — may be updated multiple times by Sokrates loop
    "synthesis": str,             # markdown with [Ref N] citations

    # Phase 5 — Sokrates (deep+)
    "critic_rounds": [
        {"round": int, "score": int, "gaps": [str], "feedback": str, "verdict": str}
    ],

    # Phase 6 — Darwin
    "final_report": str           # full markdown report
}
```

---

## Output Files

All saved to `AI Data/Ferry Agent/` with ISO timestamp prefix:

```
swarm_{timestamp}_0_meta.txt          ← Al-Biruni: mode, rationale, angles
swarm_{timestamp}_1_scout.txt         ← Hypatia: sources list (all modes)
swarm_{timestamp}_2_analysis.txt      ← Bacon: paper analysis      (deep/academic)
swarm_{timestamp}_3_validation.txt    ← Popper: evidence matrix     (academic only)
swarm_{timestamp}_4_citations.txt     ← Leibniz: citation chains    (academic only)
swarm_{timestamp}_5_synthesis.txt     ← Averroes: unified narrative (deep/academic)
swarm_{timestamp}_6_critique.txt      ← Sokrates: all critic rounds (deep/academic)
swarm_{timestamp}_final_report.md     ← Darwin: final report (wiki-ingested)
```

Files for skipped agents (e.g., Popper in Deep mode) are not created.

### Darwin's Report Structure

```markdown
# {Topic}
**Mode:** Academic | **Swarm Run:** {timestamp}

## Abstract
## Background & Context
## Key Findings          ← with [Ref N] inline citations
## Methodology Review    ← Bacon's analysis summarized
## Evidence Assessment   ← Popper's quality matrix (academic mode only)
## Research Gaps         ← Sokrates + Leibniz gaps merged
## Conclusions
## References            ← numbered list matching [Ref N]
```

---

## WikiIngester (Post-Pipeline Function)

Not an LLM agent — a Python function called after Darwin finishes:

1. Write `swarm_{timestamp}_final_report.md` to `AI Data/Ferry Agent/`
2. Call `write_research_to_wiki(topic, final_report)` — builds Cicero's knowledge base
3. Call `ingest_source(url)` for each URL in `scout_sources` (top 5 by citation count)

---

## Integration

### `crewai_agents.py`
New class `AcademicSwarmPipeline` alongside existing `IbnAlHaythamPipeline`:

```python
class AcademicSwarmPipeline:
    def kickoff(self, topic: str) -> dict:
        data = {"topic": topic}
        # Phase 0
        data.update(self._run_al_biruni(topic))
        mode = data["mode"]
        # Phase 1 (all modes)
        data["scout_sources"] = self._run_hypatia(data)
        # Phase 2+ (conditional on mode)
        if mode in ("deep", "academic"):
            if mode == "academic":
                # Bacon + Popper run in parallel via ThreadPoolExecutor(max_workers=2)
                # same pattern as Ibn Al-Haytham Phase 2
                with ThreadPoolExecutor(max_workers=2) as ex:
                    f_bacon  = ex.submit(self._run_bacon, data)
                    f_popper = ex.submit(self._run_popper, data)
                data["analyst_summaries"] = f_bacon.result()
                data["validator_matrix"]  = f_popper.result()
            else:
                data["analyst_summaries"] = self._run_bacon(data)
        # etc.
        data["final_report"] = self._run_darwin(data)
        self._wiki_ingest(data)
        return data
```

### `server.py`
Add `"academic_swarm"` to `POST /api/crew/kickoff` pipeline dispatch:

```python
elif pipeline == "academic_swarm":
    job = AcademicSwarmPipeline()
    thread = threading.Thread(target=_run_swarm, args=(job_id, job, topic))
```

SSE status endpoint (`GET /api/crew/status/{job_id}`) requires no changes — same event schema.

### `static/index/overlays.jsx` — CrewDrawer
Add second card alongside Ibn Al-Haytham:

```
┌────────────────────────────────┐  ┌────────────────────────────────┐
│ 🔬 Ibn Al-Haytham Research     │  │ 🎓 Academic Swarm              │
│ 7-agent deep research pipeline │  │ Meta-orchestrated academic     │
│ General + Academic + Hybrid    │  │ researcher — Quick/Deep/Full   │
│ [Topic ___________] [Start →]  │  │ [Topic ___________] [Start →]  │
└────────────────────────────────┘  └────────────────────────────────┘
```

`ResultModal` requires no changes — already renders markdown.

### No Changes To
- `router.py` — swarm is not a chat agent
- Any existing chat agents — no modifications
- `static/index/app.jsx` — Crew Mode state management unchanged

---

## Tools Used Per Agent

| Agent | Tools |
|-------|-------|
| Al-Biruni | LLM reasoning only (no tools) |
| Hypatia | `SemanticScholarSearchTool`, `LinkUpSearchTool` (web fallback) |
| Bacon | `SemanticScholarSearchTool` (fetch full abstract by paper ID) |
| Popper | LLM reasoning on Bacon's summaries + Hypatia's sources |
| Leibniz | `SemanticScholarSearchTool` (citation API — references/citations endpoints) |
| Averroes | LLM reasoning on accumulated data dict |
| Sokrates | LLM reasoning on Averroes' synthesis |
| Darwin | LLM reasoning on full data dict |

---

## Error Handling

- **Semantic Scholar rate limit (429)**: exponential backoff up to 60s, same pattern as Ibn Al-Haytham
- **Al-Biruni misclassification**: fallback to `"deep"` if output JSON is malformed
- **Sokrates max rounds reached**: use last synthesis regardless of score — never blocks pipeline
- **WikiIngester failure**: log warning, do not fail the pipeline — report is already saved to disk
- **Empty scout results**: if Hypatia finds 0 sources, pipeline aborts early with `{"error": "no_sources_found"}`

---

## Dependencies

All already in `requirements.txt`:
- `crewai crewai-tools` — agent framework
- `langchain-mistralai` — LLM provider
- `linkup-sdk` — web search fallback
- `wiki_tools` / `research_tools` — internal tools already present

No new packages required.
