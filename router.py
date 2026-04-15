"""
Supervisor router that classifies the user's intent and delegates
to the correct specialist agent.
"""
import os
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

# Agent labels and their descriptions for the classifier
AGENT_REGISTRY = {
    "task":     "Managing to-do lists, tasks, reminders, and deadlines",
    "notes":    "Writing notes, saving information, summarizing articles or research URLs",
    "news":     "Latest news, current events, headlines, recent updates",
    "coding":   "Programming help, code explanation, debugging, tutorials, tech questions",
    "schedule": "Calendar, meetings, events, appointments, schedule management",
    "budget":   "Money, expenses, income, spending, finance, budget, cashflow",
    "research": "Deep research, investigating topics, summarizing papers or articles, multi-source analysis, autonomous research reports",
    "fitness":  "Fitness, workout, gym, exercise, nutrition, protein, muscle, lean gain, diet, supplement, training program, body composition",
    "journal":  "Personal diary, daily journaling, reflection, mood tracking, gratitude writing, personal feelings, thoughts and emotions, jurnal harian, refleksi diri, perasaan, curhat, cerita pribadi",
    "davinci":  "Creative brainstorming, out-of-the-box ideas, innovation, ideation, wild ideas, creative thinking, new concepts, invention, inspiration, ide kreatif, brainstorm, ide gila, inovasi, konsep baru, ekspansi ide",
}

CLASSIFY_PROMPT = """You are a routing assistant. Based on the user's message, decide which specialist agent should handle it.

Available agents:
{agent_list}

Examples of correct routing:
- "add a task to call dentist tomorrow" → task
- "remind me to submit the report by Friday" → task
- "what's happening in tech today?" → news
- "latest AI news" → news
- "how do I use async/await in Python?" → coding
- "debug this error: TypeError: 'NoneType'" → coding
- "schedule a meeting with John at 3pm" → schedule
- "what's on my calendar this week?" → schedule
- "save this article for later" → notes
- "what did I write about machine learning?" → notes
- "I spent 50k on food this week" → budget
- "show me my monthly expenses" → budget
- "research the history of quantum computing" → research
- "deep dive into climate change solutions" → research
- "berapa protein yang harus aku makan untuk lean gain?" → fitness
- "workout split terbaik untuk hypertrophy?" → fitness
- "apakah creatine bagus untuk muscle gain?" → fitness
- "how many calories for lean bulk?" → fitness
- "baca wiki fitness aku tentang nutrisi" → fitness
- "hari ini aku merasa cemas tentang masa depan" → journal
- "tulis di jurnalku bahwa aku bersyukur" → journal
- "mau refleksi diri sebentar" → journal
- "ceritain perasaanku hari ini" → journal
- "lihat jurnal aku minggu lalu" → journal
- "aku punya ide gila tentang aplikasi baru" → davinci
- "brainstorm ide untuk startup" → davinci
- "bantu aku kembangkan ide ini" → davinci
- "ide out of the box untuk konten" → davinci
- "lihat semua ide yang sudah aku simpan" → davinci
- "ekspansi ide tentang machine learning" → davinci

Reply with ONLY the agent name (one word, lowercase). Choose the most relevant one.
If the message is ambiguous or a general greeting, choose 'task' as default.

User message: {message}
Agent:"""


class SupervisorRouter:
    def __init__(self):
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY not found in .env file")

        self.llm = ChatMistralAI(
            model="mistral-small-latest",   # fast model for routing (cheaper + quicker)
            temperature=0.0,
            api_key=api_key,
        )
        self._agents: dict = {}
        self._chat_histories: dict = {name: [] for name in AGENT_REGISTRY}

    def _load_agent(self, name: str):
        """Lazy-load agents on first use."""
        if name not in self._agents:
            if name == "task":
                from agents.task_agent import create_task_agent
                self._agents[name] = create_task_agent()
            elif name == "notes":
                from agents.notes_agent import create_notes_agent
                self._agents[name] = create_notes_agent()
            elif name == "news":
                from agents.news_agent import create_news_agent
                self._agents[name] = create_news_agent()
            elif name == "coding":
                from agents.coding_agent import create_coding_agent
                self._agents[name] = create_coding_agent()
            elif name == "schedule":
                from agents.schedule_agent import create_schedule_agent
                self._agents[name] = create_schedule_agent()
            elif name == "budget":
                from agents.budget_agent import create_budget_agent
                self._agents[name] = create_budget_agent()
            elif name == "research":
                from agents.research_agent import create_research_agent
                self._agents[name] = create_research_agent()
            elif name == "fitness":
                from agents.fitness_agent import create_fitness_agent
                self._agents[name] = create_fitness_agent()
            elif name == "journal":
                from agents.dostyevsky_agent import create_dostyevsky_agent
                self._agents[name] = create_dostyevsky_agent()
            elif name == "davinci":
                from agents.davinci_agent import create_davinci_agent
                self._agents[name] = create_davinci_agent()
        return self._agents[name]

    @staticmethod
    def _extract_content(content) -> str:
        """Normalize AIMessage.content to a plain string.
        Mistral can return a list of content blocks instead of a string."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict):
                    parts.append(part.get("text", str(part)))
                else:
                    parts.append(str(part))
            return "".join(parts)
        return str(content)

    def classify(self, message: str) -> str:
        """Classify the message and return the agent name."""
        agent_list = "\n".join(f"- {name}: {desc}" for name, desc in AGENT_REGISTRY.items())
        prompt = CLASSIFY_PROMPT.format(agent_list=agent_list, message=message)
        response = self.llm.invoke([HumanMessage(content=prompt)])
        parts = response.content.strip().lower().split()
        agent_name = parts[0] if parts else "task"
        return agent_name if agent_name in AGENT_REGISTRY else "task"

    def chat(self, user_message: str) -> tuple[str, str]:
        """
        Route the message to the right agent and return (agent_name, response).
        """
        agent_name = self.classify(user_message)
        agent = self._load_agent(agent_name)
        history = self._chat_histories[agent_name]

        messages = history + [HumanMessage(content=user_message)]
        response = agent.invoke({"messages": messages})

        answer = self._extract_content(response["messages"][-1].content)

        # Update this agent's chat history
        history.append(HumanMessage(content=user_message))
        history.append(AIMessage(content=answer))
        if len(history) > 30:
            self._chat_histories[agent_name] = history[-30:]

        # Auto-save to Obsidian history (silently skipped if vault not configured)
        try:
            from tools.obsidian_tools import append_to_history
            append_to_history(agent_name, user_message, answer)
        except Exception:
            pass

        return agent_name, answer

    def chat_direct(self, agent_name: str, user_message: str) -> tuple[str, str]:
        """Directly route to a specific agent, skipping classification."""
        if agent_name not in AGENT_REGISTRY:
            agent_name = "task"
        agent = self._load_agent(agent_name)
        history = self._chat_histories[agent_name]

        messages = history + [HumanMessage(content=user_message)]
        response = agent.invoke({"messages": messages})

        answer = self._extract_content(response["messages"][-1].content)

        history.append(HumanMessage(content=user_message))
        history.append(AIMessage(content=answer))
        if len(history) > 30:
            self._chat_histories[agent_name] = history[-30:]

        # Auto-save to Obsidian history (silently skipped if vault not configured)
        try:
            from tools.obsidian_tools import append_to_history
            append_to_history(agent_name, user_message, answer)
        except Exception:
            pass

        return agent_name, answer
