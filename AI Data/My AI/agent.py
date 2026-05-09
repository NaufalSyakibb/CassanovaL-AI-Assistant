# Multi-Agent System with WatsonX.ai and CrewAI
# Based on: https://youtu.be/gUrENDkPw_k
# Uses crewAI to orchestrate multiple AI agents (researcher + writer)
# powered by IBM WatsonX LLMs.

from crewai import Crew, Task, Agent
from crewai_tools import SerperDevTool
from langchain_ibm import WatsonxLLM
import os

# ── API Keys ──────────────────────────────────────────────────────────────────
os.environ["WATSONX_APIKEY"] = "YOUR_WATSONX_API_KEY"
os.environ["SERPER_API_KEY"] = "YOUR_SERPER_API_KEY"

# ── Model Parameters ──────────────────────────────────────────────────────────
parameters = {
    "decoding_method": "greedy",
    "max_new_tokens": 500,
}

# ── LLM 1: Llama 3 70B — main generation LLM ─────────────────────────────────
llm = WatsonxLLM(
    model_id="meta-llama/llama-3-70b-instruct",
    url="https://us-south.ml.cloud.ibm.com",
    params=parameters,
    project_id="YOUR_PROJECT_ID",
)

# ── LLM 2: Merlinite 7B — function calling LLM ───────────────────────────────
function_calling_llm = WatsonxLLM(
    model_id="ibm-mistralai/merlinite-7b",
    url="https://us-south.ml.cloud.ibm.com",
    params=parameters,
    project_id="YOUR_PROJECT_ID",
)

# ── Tools ─────────────────────────────────────────────────────────────────────
search = SerperDevTool()

# ── Agent 1: Researcher ───────────────────────────────────────────────────────
researcher = Agent(
    llm=llm,
    function_calling_llm=function_calling_llm,
    role="Senior AI Researcher",
    goal="Find promising research in the field of Quantum Computing",
    backstory=(
        "You're a veteran Quantum Computing researcher with a background "
        "in modern physics."
    ),
    allow_delegation=False,
    tools=[search],
    verbose=1,
)

# ── Agent 2: Writer ───────────────────────────────────────────────────────────
writer = Agent(
    llm=llm,
    role="Senior Speech Writer",
    goal="Write engaging witty keynotes from the provided research",
    backstory=(
        "You're a veteran Quantum Computing writer with a background "
        "in modern physics."
    ),
    allow_delegation=False,
    verbose=1,
)

# ── Task 1: Research ──────────────────────────────────────────────────────────
task1 = Task(
    description="Search the net and find five examples of promising AI research.",
    expected_output=(
        "A detailed bullet point summary on each of the topics. "
        "Each bullet point should cover the topic background and why the research is useful."
    ),
    output_file="task1_output.txt",
    agent=researcher,
)

# ── Task 2: Write keynote ─────────────────────────────────────────────────────
task2 = Task(
    description="Write an engaging keynote speech on Quantum Computing.",
    expected_output=(
        "A detailed keynote speech with an intro, a body, and a conclusion."
    ),
    output_file="task2_output.txt",
    agent=writer,
)

# ── Crew: assemble and run ────────────────────────────────────────────────────
crew = Crew(
    agents=[researcher, writer],
    tasks=[task1, task2],
    verbose=1,
)

print(crew.kickoff())
