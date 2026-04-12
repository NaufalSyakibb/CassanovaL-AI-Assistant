"""
CassanovaL Discord Bot
======================
Connects all 9 AI agents to Discord.

Commands (in any server channel or DM):
  !ask <message>           — auto-route to the best agent
  !alfred <message>        — Task manager
  !cicero <message>        — Notes & knowledge
  !najwa <message>         — News briefing
  !linus <message>         — Coding tutor
  !miyamoto <message>      — Calendar / schedule
  !mansa <message>         — Budget & finance
  !ferry <message>         — Deep research
  !lavoiser <message>      — Fitness & nutrition
  !dostyevsky <message>    — Personal journaling
  !agents                  — List all agents
  !help                    — Show this help

DM mode: Just send a plain message in DM → auto-routed, no prefix needed.

Setup:
  1. Add DISCORD_BOT_TOKEN=... to your .env file
  2. pip install "discord.py>=2.3"
  3. python discord_bot.py
"""

import os
import sys
import io
import asyncio
import textwrap
import discord
from discord.ext import commands
from dotenv import load_dotenv

# ── Windows UTF-8 fix ─────────────────────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
if not BOT_TOKEN:
    print("❌  DISCORD_BOT_TOKEN not found in .env")
    print("    Add: DISCORD_BOT_TOKEN=your_token_here")
    sys.exit(1)

# ── Agent registry ────────────────────────────────────────────────────────────
# Maps Discord command → internal agent name (None = auto-route)
COMMAND_TO_AGENT: dict[str, str | None] = {
    "ask":        None,          # auto-route via SupervisorRouter
    "alfred":     "task",
    "cicero":     "notes",
    "najwa":      "news",
    "linus":      "coding",
    "miyamoto":   "schedule",
    "mansa":      "budget",
    "ferry":      "research",
    "lavoiser":   "fitness",
    "dostyevsky": "journal",
}

AGENT_META = {
    "task":     {"name": "Alfred",       "emoji": "📋", "color": 0x00FF41},
    "notes":    {"name": "Cicero",       "emoji": "📚", "color": 0x4499FF},
    "news":     {"name": "Najwa",        "emoji": "📰", "color": 0xFFAA00},
    "coding":   {"name": "Linus",        "emoji": "💻", "color": 0xBB44FF},
    "schedule": {"name": "Miyamoto",     "emoji": "📅", "color": 0x00FFCC},
    "budget":   {"name": "Mansa",        "emoji": "💰", "color": 0xFFCC00},
    "research": {"name": "Ferry",        "emoji": "🔬", "color": 0x00DDFF},
    "fitness":  {"name": "Lavoiser",     "emoji": "💪", "color": 0xFF2244},
    "journal":  {"name": "Dostoyevsky",  "emoji": "📔", "color": 0xC084FC},
}

DISCORD_CHAR_LIMIT = 1990   # safe margin under Discord's 2000-char message limit
EMBED_DESC_LIMIT   = 4096   # Discord embed description limit

# ── Discord bot setup ─────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True   # required for reading message text

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Lazy-loaded router — initialised once on first use
_router = None

def get_router():
    global _router
    if _router is None:
        from router import SupervisorRouter
        _router = SupervisorRouter()
    return _router


# ── Helpers ───────────────────────────────────────────────────────────────────

def split_text(text: str, limit: int = DISCORD_CHAR_LIMIT) -> list[str]:
    """Split a long response into Discord-safe chunks at paragraph boundaries."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Try to split at the last newline within the limit
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()
    return chunks


def build_embed(agent_name: str, response: str, query: str) -> list[discord.Embed]:
    """Build one or more Discord embeds for an agent response."""
    meta = AGENT_META.get(agent_name, {"name": agent_name.title(), "emoji": "🤖", "color": 0x888888})
    color  = meta["color"]
    title  = f"{meta['emoji']}  {meta['name']}"

    # Split if response is too long for a single embed
    chunks = textwrap.wrap(response, EMBED_DESC_LIMIT, break_long_words=False,
                           replace_whitespace=False) if len(response) > EMBED_DESC_LIMIT else [response]

    embeds = []
    for i, chunk in enumerate(chunks):
        e = discord.Embed(
            title=title if i == 0 else f"{title} (cont.)",
            description=chunk,
            color=color,
        )
        if i == 0:
            e.set_footer(text=f'Query: "{query[:80]}{"…" if len(query) > 80 else ""}"')
        embeds.append(e)
    return embeds


async def route_and_reply(ctx_or_message, user_text: str, force_agent: str | None = None):
    """Call the router in a thread (it's synchronous/blocking) and send reply."""
    is_message = isinstance(ctx_or_message, discord.Message)
    channel = ctx_or_message.channel if is_message else ctx_or_message.channel

    # Show typing indicator while the LLM thinks
    async with channel.typing():
        try:
            router = get_router()

            # Run blocking LangChain call in a separate thread
            if force_agent:
                agent_name, response = await asyncio.to_thread(
                    router.chat_direct, force_agent, user_text
                )
            else:
                agent_name, response = await asyncio.to_thread(
                    router.chat, user_text
                )

            embeds = build_embed(agent_name, response, user_text)
            for embed in embeds:
                if is_message:
                    await ctx_or_message.reply(embed=embed, mention_author=False)
                else:
                    await ctx_or_message.reply(embed=embed)

        except Exception as e:
            err_embed = discord.Embed(
                title="⚠️  Error",
                description=f"Something went wrong:\n```{e}```\nMake sure your `.env` has a valid `MISTRAL_API_KEY`.",
                color=0xFF2244,
            )
            if is_message:
                await ctx_or_message.reply(embed=err_embed, mention_author=False)
            else:
                await ctx_or_message.reply(embed=err_embed)


# ── Events ────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅  CassanovaL bot online as {bot.user} (ID: {bot.user.id})")
    print(f"    Serving {len(bot.guilds)} server(s)")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="!ask | 9 agents ready"
        )
    )


@bot.event
async def on_message(message: discord.Message):
    # Ignore own messages
    if message.author.bot:
        return

    # DM mode: plain message (no prefix) → auto-route
    if isinstance(message.channel, discord.DMChannel):
        content = message.content.strip()
        if content and not content.startswith("!"):
            await route_and_reply(message, content)
            return  # don't also process as command

    # Process normal commands
    await bot.process_commands(message)


# ── Commands ──────────────────────────────────────────────────────────────────

@bot.command(name="ask")
async def cmd_ask(ctx, *, message: str):
    """Auto-route your message to the best agent."""
    await route_and_reply(ctx, message, force_agent=None)


@bot.command(name="alfred")
async def cmd_alfred(ctx, *, message: str):
    """Send a message directly to Alfred (Task manager)."""
    await route_and_reply(ctx, message, force_agent="task")


@bot.command(name="cicero")
async def cmd_cicero(ctx, *, message: str):
    """Send a message directly to Cicero (Notes & research)."""
    await route_and_reply(ctx, message, force_agent="notes")


@bot.command(name="najwa")
async def cmd_najwa(ctx, *, message: str):
    """Send a message directly to Najwa (News briefing)."""
    await route_and_reply(ctx, message, force_agent="news")


@bot.command(name="linus")
async def cmd_linus(ctx, *, message: str):
    """Send a message directly to Linus (Coding tutor)."""
    await route_and_reply(ctx, message, force_agent="coding")


@bot.command(name="miyamoto")
async def cmd_miyamoto(ctx, *, message: str):
    """Send a message directly to Miyamoto (Schedule & calendar)."""
    await route_and_reply(ctx, message, force_agent="schedule")


@bot.command(name="mansa")
async def cmd_mansa(ctx, *, message: str):
    """Send a message directly to Mansa (Budget & finance)."""
    await route_and_reply(ctx, message, force_agent="budget")


@bot.command(name="ferry")
async def cmd_ferry(ctx, *, message: str):
    """Send a message directly to Ferry (Deep research)."""
    await route_and_reply(ctx, message, force_agent="research")


@bot.command(name="lavoiser")
async def cmd_lavoiser(ctx, *, message: str):
    """Send a message directly to Lavoiser (Fitness & nutrition)."""
    await route_and_reply(ctx, message, force_agent="fitness")


@bot.command(name="dostyevsky")
async def cmd_dostyevsky(ctx, *, message: str):
    """Send a message directly to Dostoyevsky (Personal journal)."""
    await route_and_reply(ctx, message, force_agent="journal")


@bot.command(name="agents")
async def cmd_agents(ctx):
    """List all available agents."""
    lines = []
    for cmd, agent in COMMAND_TO_AGENT.items():
        if agent is None:
            lines.append(f"`!ask`  — 🔀 Auto-route to the best agent")
        else:
            m = AGENT_META[agent]
            lines.append(f"`!{cmd}`  — {m['emoji']} **{m['name']}**")
    embed = discord.Embed(
        title="🤖  CassanovaL — Agent Directory",
        description="\n".join(lines),
        color=0x7C3AED,
    )
    embed.set_footer(text="DM me without a prefix to auto-route any message.")
    await ctx.reply(embed=embed)


@bot.command(name="help")
async def cmd_help(ctx):
    """Show usage help."""
    desc = (
        "**Commands**\n"
        "`!ask <msg>`        — Auto-route to best agent\n"
        "`!alfred <msg>`     — 📋 Tasks & reminders\n"
        "`!cicero <msg>`     — 📚 Notes & research\n"
        "`!najwa <msg>`      — 📰 Latest news\n"
        "`!linus <msg>`      — 💻 Coding help\n"
        "`!miyamoto <msg>`   — 📅 Calendar\n"
        "`!mansa <msg>`      — 💰 Budget & finance\n"
        "`!ferry <msg>`      — 🔬 Deep research\n"
        "`!lavoiser <msg>`   — 💪 Fitness & nutrition\n"
        "`!dostyevsky <msg>` — 📔 Personal journaling\n"
        "`!agents`           — List all agents\n\n"
        "**DM Mode**\n"
        "Send any plain message in DM → auto-routed, no prefix needed."
    )
    embed = discord.Embed(title="📖  CassanovaL Help", description=desc, color=0x7C3AED)
    await ctx.reply(embed=embed)


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(BOT_TOKEN)
