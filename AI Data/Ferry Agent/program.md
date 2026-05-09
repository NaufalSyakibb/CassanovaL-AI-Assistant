---
agent: Ferry (Research)
created: 2026-04-15
metric: Research plan accuracy — user approves the Phase 1 scope on first attempt vs. needs to redirect
---

# Autoresearch Program — Ferry (Research)

## Current Hypothesis

**H-001** (Baseline): Presenting the Phase 1 scope as numbered bullets and waiting for explicit approval before searching reduces wasted search cycles.

## Metric

Research plan accuracy — user approves the Phase 1 scope on first attempt vs. needs to redirect

## Baseline Approach

- Always present a scope plan before executing searches
- Use iterative_search for multi-angle coverage
- Always call write_research_to_wiki() after completing a report

## Next Experiments

- [ ] **E-001**: Switch scope plan to a numbered checklist with estimated search count per angle.
- [ ] **E-002**: Ask "Is there an angle I missed?" explicitly at the plan stage before any searches.
- [ ] **E-003**: Offer "quick mode" (3 searches, 1 summary) vs. "deep mode" (full iterative) at session start.

## Experiment Log

See: [[experiment_log]]
