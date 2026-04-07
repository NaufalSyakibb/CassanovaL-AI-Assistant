import sys
import io
from router import SupervisorRouter

# Fix Windows terminal encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

AGENT_ICONS = {
    "task":     "[ TASK     ]",
    "notes":    "[ NOTES    ]",
    "news":     "[ NEWS     ]",
    "coding":   "[ CODING   ]",
    "schedule": "[ SCHEDULE ]",
    "budget":   "[ BUDGET   ]",
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
Example commands:
  Tasks    : "add task: beli sayuran, high priority"
             "show my pending tasks"
             "mark task abc123 done"

  Notes    : "create note about Python async/await"
             "summarize this URL: https://..."
             "search my notes about AI"

  News     : "what's the news today?"
             "latest tech news"
             "berita hari ini"

  Coding   : "explain Python decorators"
             "how does useEffect work in React?"
             "review this code: ..."

  Schedule : "show my schedule today"
             "create meeting tomorrow 10am-11am"
             "list events this week"

  Budget   : "tambah pengeluaran 50000 untuk makan siang"
             "show my monthly summary"
             "add income 5000000 salary"
"""


def main():
    print(BANNER)

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

        try:
            agent_name, answer = router.chat(user_input)
            icon = AGENT_ICONS.get(agent_name, "[ AGENT   ]")
            print(f"\n{icon}\n{answer}\n")
        except Exception as e:
            print(f"\nError: {e}\n")
            print("Please check your .env file and internet connection.\n")


if __name__ == "__main__":
    main()
