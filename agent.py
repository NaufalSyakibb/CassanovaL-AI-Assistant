import os
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tools import ALL_TOOLS

load_dotenv()


def create_assistant() -> AgentExecutor:
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY not found in .env file")

    llm = ChatMistralAI(
        model="mistral-large-latest",
        temperature=0.2,
        api_key=api_key,
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a helpful personal assistant that manages the user's tasks. "
            "You can add, list, complete, delete, and update tasks. "
            "Always use the available tools to manage tasks — never make up task data. "
            "Be concise and friendly. When listing tasks, format them clearly. "
            "If the user speaks in Indonesian, respond in Indonesian."
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt)
    return AgentExecutor(agent=agent, tools=ALL_TOOLS, verbose=False)
