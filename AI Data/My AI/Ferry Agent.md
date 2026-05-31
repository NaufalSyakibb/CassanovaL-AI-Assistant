---
agent: Ferry
tags: [research, deep-research, ferry, index, ibn-al-haytham]
created: 2026-05-31
---

# Ferry — Deep Research Agent

*Systematic, evidence-driven, thorough. No shortcuts.*

[[Home]]

---

## What Ferry Does

Runs a 7-agent autonomous research pipeline (Ibn Al-Haytham Research Crew):

```
Phase 1 (Sequential)
  [1] Scout      → topic map + mode detection (academic/general/hybrid)
  [2] Filter     → curates 10–15 quality sources

Phase 2 (Parallel)
  [3] IdeaGen    → novel hypotheses and angles
  [4] Validator  → cross-checks claims, flags weak evidence

Phase 3 (Sequential)
  [5] Synthesizer → unified narrative
  [6] Critic     → logic review
  [7] Writer     → final article with citations
```

---

## Research Output Files

| File | Purpose |
|------|---------|
| `task1_scout.txt` | Topic map + mode tag |
| `task2_filter.txt` | Curated sources |
| `task3a_ideas.txt` | Hypotheses |
| `task3b_validation.txt` | Cross-checked claims |
| `task4_synthesis.txt` | Unified narrative |
| `task5_critique.txt` | Logic review |
| `task6_final_report.md` | Final article |

---

## How to Use Ferry

From the app: go to **Crew Mode** → select Research → enter a topic → start.

From terminal:
```bash
python crewai_agents.py --topic "your topic here"
```

---

## When to Use Ferry vs. Najwa

| Situation | Use |
|-----------|-----|
| Quick news on a topic | Najwa |
| One-line summary of events | Najwa |
| Comprehensive deep analysis | Ferry |
| Academic-quality research | Ferry |
| Writing a report or essay background | Ferry |

---

## See Also

[[Home]] · [[Najwa Agent]] · [[Da Vinci Agent]] · [[wiki/index]]
