# Ibn Al-Haytham — Multi-Agent Research System (7-Agent)
**Date:** 2026-04-24  
**Status:** Implemented — 2026-04-25  
**Replaces:** 2-agent Drafter→Critic pipeline in `crewai_agents.py`

---

## Overview

A 7-agent hybrid research pipeline inspired by HKUDS AI-Researcher, adapted for both academic and general topics. Auto-detects research mode per topic. Replaces the existing 2-agent Ibn Al-Haytham crew in `crewai_agents.py` and surfaces in the web frontend's CrewDrawer.

---

## Architecture

### Pipeline

```
─────────────────── PHASE 1 (Sequential) ───────────────────
 [1] Scout      →  [2] Filter
 Peta topik         Kurasi sumber
 + auto-detect

─────────────────── PHASE 2 (Parallel) ─────────────────────
              [3] IdeaGen  ‖  [4] Validator
              Sudut pandang   Verifikasi bukti
              & hipotesis     & deteksi lemah

─────────────────── PHASE 3 (Sequential) ───────────────────
 [5] Synthesizer  →  [6] Critic  →  [7] Writer
 Gabungkan           Logika &        Artikel final
 Phase 2             self-critique   terformat
```

### Agent & LLM Assignment

| # | Agent | LLM | Role |
|---|-------|-----|------|
| 1 | Scout | `mistral-small-latest` | Topic map, auto-detect mode, broad search |
| 2 | Filter | `mistral-small-latest` | Source quality scoring, curate 10–15 best |
| 3 | IdeaGen | `gemma-4` | Generate hypotheses, novel angles, connections |
| 4 | Validator | `gemma-4` | Cross-check claims, flag weak evidence `[⚠]` |
| 5 | Synthesizer | `mistral-large-latest` | Merge Phase 2 outputs into unified narrative |
| 6 | Critic | `mistral-large-latest` | Logic review, remove over-generalizations |
| 7 | Writer | `mistral-large-latest` | Final article with inline citations `[Ref N]` |

### Auto-Detect Mode (Scout)

Scout outputs one of three mode tags:
- `[MODE: ACADEMIC]` → prioritise arXiv, PubMed, IEEE, Nature, Semantic Scholar
- `[MODE: GENERAL]` → prioritise news, industry reports, LinkUp/DuckDuckGo
- `[MODE: HYBRID]` → balanced search across both

All downstream agents read this tag and adjust search strategy accordingly.

### Parallel Execution (Phase 2)

IdeaGen and Validator run as two separate `Crew` objects inside a `ThreadPoolExecutor(max_workers=2)`. Both receive Filter's curated sources as context. Synthesizer waits for both futures before proceeding.

---

## Data Flow & Output Files

```
Scout  → {topic_map, mode_tag, raw_sources}       → task1_scout.txt
Filter → {curated_sources, relevance_scores}       → task2_filter.txt

IdeaGen   ← curated_sources → ideas              → task3a_ideas.txt
Validator ← curated_sources → validation         → task3b_validation.txt

Synthesizer ← {ideas + validation}                → task4_synthesis.txt
Critic      ← synthesis                           → task5_critique.txt
Writer      ← {synthesis + critique + sources}    → task6_final_report.md
```

All files saved to `_research_dir()` (existing helper, unchanged).

---

## Frontend Changes

### `overlays.jsx` — `CrewDrawer`

1. **`nodes` array for `research` type** — expand from 2 to 7 nodes with phase labels and LLM badges
2. **Pipeline selector subtitle** — `"Scout → [IdeaGen ‖ Validator] → Writer"`
3. **Crew meta line** — `"Mistral + Gemma · est. 3–6 min"`
4. **Phase separator rendering** — visual dividers between Phase 1 / Phase 2 (parallel badge) / Phase 3

### `server.py` — `_run_crew_background`

Replace output file collection for `research` crew_type:
```python
# NEW — 7 output files
for fname in ("task1_scout.txt", "task2_filter.txt",
              "task3a_ideas.txt", "task3b_validation.txt",
              "task4_synthesis.txt", "task5_critique.txt",
              "task6_final_report.md"):
```

No API changes — existing endpoints (`/api/crew/kickoff`, `/api/crew/status/{job_id}`) unchanged.

---

## Error Handling

| Failure point | Behaviour |
|---------------|-----------|
| Scout fails to classify | Default to `[MODE: HYBRID]`, continue |
| Filter < 3 sources | Scout re-search once with broader query, then continue |
| One Phase 2 thread crashes | Synthesizer proceeds with partial output + `[PARTIAL]` note |
| Both Phase 2 threads crash | Job status → `"error"` |
| Phase 3 agent hits `max_iter` | Pass best available output to next agent |
| Phase 2 timeout (>300s) | Synthesizer called with whatever output exists |

---

## Testing

Three manual smoke tests after implementation:

| Test | Topic | Pass condition |
|------|-------|----------------|
| ACADEMIC | `"CRISPR gene editing mechanism"` | `[MODE: ACADEMIC]` in scout output, arXiv/PubMed refs in final report |
| GENERAL | `"Strategi pemasaran TikTok 2025"` | `[MODE: GENERAL]` in scout output, news/blog sources |
| HYBRID | `"Large Language Models in healthcare"` | `[MODE: HYBRID]`, mix of academic + industry sources |

Validation: check `[MODE: X]` in `task1_scout.txt` and `[Ref N]` citations in `task6_final_report.md`.

---

## Files Modified

| File | Change |
|------|--------|
| `crewai_agents.py` | Replace `build_crew()` + all 2-agent factory functions with 7-agent phase-based system |
| `server.py` | Update output file list in `_run_crew_background` |
| `static/index/overlays.jsx` | Update `nodes` array, pipeline description, meta line |
