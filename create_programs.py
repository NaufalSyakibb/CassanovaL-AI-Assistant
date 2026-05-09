"""One-time script to create per-agent program.md scaffolds."""
import os
from pathlib import Path
from datetime import date

vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
base = Path(vault) / "AI Data" if vault else Path(__file__).parent / "AI Data"
today = date.today().isoformat()

programs = {
    "TaskCore Agent": {
        "agent": "Alfred (TaskCore)",
        "metric": "Task completion rate — user marks tasks done vs. abandons/ignores them",
        "h001": "Breaking complex goals into <= 3 actionable next steps with explicit due dates increases task completion rate.",
        "baseline": "- Always infer priority + due date and confirm the inference\n- Group tasks by priority (Critical > High > Medium > Low)\n- Surface overdue items at the top of every list view\n- Ask one clarifying question rather than guessing on destructive actions",
        "e001": "Proactively group tasks by energy level (deep-focus vs. quick wins) in the default list view.",
        "e002": 'Offer a "top 3 for today" briefing at the start of every session without being asked.',
        "e003": "Detect when the same task has been pushed 3+ times and surface a gentle nudge.",
    },
    "Notes Agent": {
        "agent": "Cicero (NoteCore)",
        "metric": "Note utility — user revisits and extends saved notes vs. saves-and-forgets",
        "h001": "Suggesting 2-3 cross-references to existing notes when creating a new note increases long-term note utility.",
        "baseline": "- Suggest tags and related notes on every create\n- Search for existing notes before creating a duplicate\n- Offer to fetch and summarize URLs when pasted",
        "e001": 'Auto-suggest "This relates to [[X]]" before saving, based on keyword overlap.',
        "e002": "After 5+ notes in a topic cluster, proactively offer a synthesis summary.",
        "e003": "Detect when a note topic has appeared 3+ times and propose merging into one master note.",
    },
    "Najwa Agent": {
        "agent": "Najwa (News)",
        "metric": "Briefing engagement — user asks follow-up questions vs. ends session after the briefing",
        "h001": "Filtering to the user's persistent topic interests and leading with those items increases session engagement.",
        "baseline": "- Deliver briefing in impact-tier order: Critical > High > Medium\n- Label every claim: [CONFIRMED] / [REPORTED] / [UNVERIFIED]\n- Timestamp all items in UTC",
        "e001": 'Open each session with "Want to catch up on [last topic the user asked about]?" before the full briefing.',
        "e002": "Offer a 3-bullet TL;DR before the full briefing and let the user choose depth.",
        "e003": "Maintain a user interest profile in the wiki and filter briefings to the top 3 tracked topics.",
    },
    "Linus Agent": {
        "agent": "Linus (Coding)",
        "metric": "Explanation efficiency — user understands on first explanation vs. needs re-explanation or simplification",
        "h001": "Identifying user skill level in the first message of a session and calibrating code example complexity reduces back-and-forth clarifications.",
        "baseline": "- Infer skill level from vocabulary and question type\n- Lead every concept with a real-world analogy before the technical definition\n- Always end with a clear next step",
        "e001": "Explicitly state the inferred skill level and ask to confirm before giving the full answer.",
        "e002": "Offer two code examples per explanation: simple (readable) + production (optimized).",
        "e003": "Track which languages/frameworks appear most often and pre-load wiki pages for those at session start.",
    },
    "CalCore Agent": {
        "agent": "CalCore (Schedule)",
        "metric": "Scheduling friction — user confirms events without corrections vs. needs multiple edits",
        "h001": "Closing every scheduling session with a one-line tomorrow preview reduces the need to re-ask about upcoming events.",
        "baseline": "- Always confirm before create/update/delete\n- State the exact resolved date in every confirmation\n- Show timezone explicitly when guests are in a different timezone",
        "e001": 'End every session with: "Tomorrow: [first event time + title]." as a closing line.',
        "e002": "Detect back-to-back events (<15 min gap) and proactively flag them without being asked.",
        "e003": "Ask for preferred working-hours window on first use and store in wiki for future conflict detection.",
    },
    "Mansa Agent": {
        "agent": "Mansa (Budget)",
        "metric": "Financial awareness — user reacts to or acts on spending insights vs. ignores them",
        "h001": "Comparing today's spend to the rolling 7-day average in the transaction confirmation increases financial awareness without friction.",
        "baseline": "- Confirm every transaction with: amount, category, description, current balance\n- Auto-categorize from description, ask only when ambiguous\n- Never guess category for transactions >Rp 500.000",
        "e001": 'Append "vs. avg Rp X/day (7d)" to every expense confirmation line.',
        "e002": "Auto-detect recurring subscriptions and surface total monthly cost once per month.",
        "e003": "Infer a savings rate goal from past messages and track progress in the monthly summary.",
    },
    "Ferry Agent": {
        "agent": "Ferry (Research)",
        "metric": "Research plan accuracy — user approves the Phase 1 scope on first attempt vs. needs to redirect",
        "h001": "Presenting the Phase 1 scope as numbered bullets and waiting for explicit approval before searching reduces wasted search cycles.",
        "baseline": "- Always present a scope plan before executing searches\n- Use iterative_search for multi-angle coverage\n- Always call write_research_to_wiki() after completing a report",
        "e001": "Switch scope plan to a numbered checklist with estimated search count per angle.",
        "e002": 'Ask "Is there an angle I missed?" explicitly at the plan stage before any searches.',
        'e003': 'Offer "quick mode" (3 searches, 1 summary) vs. "deep mode" (full iterative) at session start.',
    },
    "Lavoiser Agent": {
        "agent": "Lavoiser (Fitness)",
        "metric": "Macro adherence — user engages with daily nutrient progress vs. ignores tracking summaries",
        "h001": "Prepending the user's current protein intake vs. daily target to every food log confirmation increases adherence tracking engagement.",
        "baseline": "- Log food immediately when mentioned, no confirmation step\n- Show macros (protein/carbs/fat/calories) on every log confirmation\n- Use float coercion on all numeric inputs",
        "e001": 'Append "Protein today: Xg / 160g" to every food log confirmation line.',
        "e002": "Detect training day vs. rest day from prior messages and suggest appropriate macro targets.",
        "e003": 'Offer a weekly macro recap every Monday: "Last week avg: X protein / Y calories / day."',
    },
    "Dostoyevsky Agent": {
        "agent": "Reflecta (Journal)",
        "metric": "Session depth — user writes more than 3 substantive exchanges vs. gives minimal one-line responses",
        "h001": "Opening with an emotionally-calibrated prompt based on the last session's dominant emotion increases depth of the current session.",
        "baseline": "- One question at a time — never ask multiple questions in one message\n- Validate emotions before exploring them\n- Offer journal prompt categories when user is stuck",
        "e001": "Read last session's journal entry (via search_wiki) before opening, then reference it naturally.",
        "e002": "Offer three session modes at start: (1) vent, (2) reflect, (3) gratitude.",
        "e003": "Detect emotional volatility across 3+ sessions and gently surface it as a pattern observation.",
    },
    "Da Vinci Agent": {
        "agent": "Leonardo (Da Vinci)",
        "metric": "Creative output — user explores an idea beyond the first brainstorm and saves it to the vault",
        "h001": "Proposing one specific creative constraint at the start of a brainstorm session produces more original ideas than an unconstrained brainstorm.",
        "baseline": "- Always present 3 idea tiers: Solid, Ambitious, Gila (wild)\n- Check vault for related ideas before brainstorming a new topic\n- Always offer to save ideas to vault at end of session",
        "e001": "Open every brainstorm with one surprising cross-domain constraint and note whether it produces more expansive ideas.",
        "e002": 'After presenting ideas, show a "connection map" linking today\'s ideas to existing vault ideas.',
        "e003": "Track which idea categories are most saved (Tech/Art/Business/etc.) and lean into them proactively.",
    },
}

created = 0
for folder, data in programs.items():
    d = base / folder
    d.mkdir(parents=True, exist_ok=True)
    p = d / "program.md"
    if p.exists():
        print(f"[SKIP] {folder}/program.md already exists")
        continue

    content = (
        f"---\n"
        f"agent: {data['agent']}\n"
        f"created: {today}\n"
        f"metric: {data['metric']}\n"
        f"---\n\n"
        f"# Autoresearch Program — {data['agent']}\n\n"
        f"## Current Hypothesis\n\n"
        f"**H-001** (Baseline): {data['h001']}\n\n"
        f"## Metric\n\n"
        f"{data['metric']}\n\n"
        f"## Baseline Approach\n\n"
        f"{data['baseline']}\n\n"
        f"## Next Experiments\n\n"
        f"- [ ] **E-001**: {data['e001']}\n"
        f"- [ ] **E-002**: {data['e002']}\n"
        f"- [ ] **E-003**: {data['e003']}\n\n"
        f"## Experiment Log\n\n"
        f"See: [[experiment_log]]\n"
    )
    p.write_text(content, encoding="utf-8")
    created += 1
    print(f"[OK] Created {folder}/program.md")

print(f"\nDone — {created} program.md files created under: {base}")
