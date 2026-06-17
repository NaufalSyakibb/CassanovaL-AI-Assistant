import sys
import io
import argparse
from router import SupervisorRouter, AGENT_REGISTRY

# Fix Windows terminal encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

AGENT_ICONS = {
    "task":     "[ TASK     ]",
    "notes":    "[ NOTES    ]",
    "news":     "[ NEWS     ]",
    "coding":   "[ CODING   ]",
    "schedule": "[ SCHEDULE ]",
    "budget":   "[ BUDGET   ]",
    "research": "[ RESEARCH ]",
    "fitness":  "[ FITNESS  ]",
    "journal":  "[ JOURNAL  ]",
    "davinci":      "[ DA VINCI ]",
    "dataanalyst":  "[ DATABOT  ]",
}

BANNER = """
╔══════════════════════════════════════════════════════╗
║          Personal AI Assistant — Multi-Agent         ║
╠══════════════════════════════════════════════════════╣
║  Agents available:                                   ║
║  • Task Manager   — manage your to-do list           ║
║  • Notes          — write notes, summarize research  ║
║  • News           — latest 24h headlines             ║
║  • Coding Guru    — programming help & tutorials     ║
║  • Schedule       — Google Calendar management       ║
║  • Budget         — track income & expenses          ║
╠══════════════════════════════════════════════════════╣
║  Just type naturally — the AI routes automatically   ║
║  Type 'help', 'quit', or 'exit' to stop              ║
╚══════════════════════════════════════════════════════╝
"""

HELP_TEXT = """
Special commands:
  history <agent>  — show the full conversation history for an agent
                     e.g. "history davinci", "history fitness"

Example commands:
  Tasks    : "add task: beli sayuran, high priority"
             "show my pending tasks"
             "mark task abc123 done"

  Notes    : "create note about Python async/await"
             "summarize this URL: https://..."
             "search my notes about AI"

  News     : "what's the news today?"
             "latest tech news"
             "what happened in AI this week?"

  Coding   : "explain Python decorators"
             "how does useEffect work in React?"
             "review this code: ..."

  Schedule : "show my schedule today"
             "create meeting tomorrow 10am-11am"
             "list events this week"

  Budget   : "add expense 50000 for lunch"
             "show my monthly summary"
             "add income 5000000 salary"

  Da Vinci : "I have a wild idea for a new app"
             "brainstorm ideas for a content creator"
             "expand the startup idea from before"
             "show all the ideas I've saved"
"""


def main():
    parser = argparse.ArgumentParser(description="CassanovaL — Personal AI Assistant")
    parser.add_argument(
        "--agent", "-a",
        choices=list(AGENT_REGISTRY.keys()),
        default=None,
        metavar="AGENT",
        help=f"Pin to a specific agent: {', '.join(AGENT_REGISTRY.keys())}",
    )
    args = parser.parse_args()
    pinned = args.agent

    print(BANNER)
    if pinned:
        icon = AGENT_ICONS.get(pinned, "[ AGENT   ]")
        print(f"  Pinned to {icon.strip()} — all messages go directly to this agent.\n")

    try:
        router = SupervisorRouter()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("Assistant is ready. How can I help you today?\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "keluar", "bye"):
            print("Goodbye! See you next time.")
            break

        if user_input.lower() == "help":
            print(HELP_TEXT)
            continue

        if user_input.lower().startswith("history"):
            parts = user_input.split(maxsplit=1)
            target = parts[1].strip().lower() if len(parts) > 1 else (pinned or "")
            if not target or target not in AGENT_ICONS:
                print(f"\nUsage: history <agent>")
                print(f"Available agents: {', '.join(AGENT_ICONS.keys())}\n")
                continue
            msgs = router.get_history(target)
            if not msgs:
                print(f"\nNo history for [{target}] yet.\n")
                continue
            icon = AGENT_ICONS.get(target, f"[ {target.upper()} ]")
            print(f"\n{'─'*54}")
            print(f"  Full history — {icon.strip()}  ({len(msgs)//2} exchanges)")
            print(f"{'─'*54}")
            for i, m in enumerate(msgs, 1):
                label = "You" if m["role"] == "human" else icon.strip()
                print(f"\n[{i}] {label}:\n{m['content']}")
            print(f"\n{'─'*54}\n")
            continue

        try:
            if pinned:
                agent_name, answer = router.chat_direct(pinned, user_input)
            else:
                agent_name, answer = router.chat(user_input)
            icon = AGENT_ICONS.get(agent_name, "[ AGENT   ]")
            print(f"\n{icon}\n{answer}\n")
        except Exception as e:
            print(f"\nError: {e}\n")
            print("Please check your .env file and internet connection.\n")


if __name__ == "__main__":
    main()
