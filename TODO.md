# TODO

## Status as of 2026-04-25

### ✅ Completed
- **Ibn Al-Haytham 7-agent research pipeline** — fully implemented in `crewai_agents.py`
  - Phase 1: Scout → Filter (sequential, mistral-small)
  - Phase 2: IdeaGen ‖ Validator (parallel, gemma-4)
  - Phase 3: Synthesizer → Critic → Writer (sequential, mistral-large)
  - `IbnAlHaythamPipeline` class + `build_crew()` wired up
- **Server output file list** updated to 7 new files (`task1_scout.txt` … `task6_final_report.md`)
- **CrewDrawer UI** updated: 7 nodes with phase separators, LLM badges, parallel badge
- **Documentation** updated: CLAUDE.md, DOCUMENTATION.md, spec status, plan tasks marked done
- **requirements.txt** updated with `crewai`, `crewai-tools`

### 🔜 Potential next steps
- Run a full end-to-end smoke test:
  ```bash
  $env:PYTHONUTF8=1; python crewai_agents.py --topic "CRISPR gene editing mechanism"
  ```
  Verify `task1_scout.txt` contains `[MODE: ACADEMIC]` and `task6_final_report.md` contains `[Ref N]` citations.
- Set up `GEMMA4_API_KEY` in `.env` to enable native Gemma models in Phase 2
- Set up `LINKUP_API_KEY` for deeper search quality
