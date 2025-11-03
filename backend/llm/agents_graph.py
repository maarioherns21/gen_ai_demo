from agents import Agent
from pathlib import Path
# from backend.llm.agent_tools import tool_search_flights, tool_search_hotels, tool_search_activities
from backend.config.settings import OPENAI_MODEL
from backend.llm.agent_tools import (
    tool_search_flights,
    tool_search_hotels,
    tool_search_activities,
)

PROMPT_DIR = Path(__file__).parents[2] / "docs" / "prompt-templates"


orchestrator = Agent(
    name="Orchestrator",
    instructions=(PROMPT_DIR / "orchestrator_system.md").read_text(),
    model=OPENAI_MODEL,
    # No tools here; it only decides next step + collects inputs
)

planner = Agent(
    name="Planner",
    instructions=(PROMPT_DIR / "planner_agent.md").read_text(),
    model=OPENAI_MODEL,
    tools=[tool_search_flights],  # allow 1 flight probe for price anchor if desired
)

flights = Agent(
    name="Flights",
    instructions=(PROMPT_DIR / "transport_agent.md").read_text(),
    model=OPENAI_MODEL,
    tools=[tool_search_flights],
)

lodging = Agent(
    name="Lodging",
    instructions=(PROMPT_DIR / "lodging_agent.md").read_text(),
    model=OPENAI_MODEL,
    tools=[tool_search_hotels],
)

activities = Agent(
    name="Activities",
    instructions=(PROMPT_DIR / "activity_agent.md").read_text(),
    model=OPENAI_MODEL,
    tools=[tool_search_activities],
)

budget = Agent(
    name="Budget",
    instructions=(PROMPT_DIR / "budget_agent.md").read_text(),
    model=OPENAI_MODEL,
)

critic = Agent(
    name="Critic",
    instructions=(PROMPT_DIR / "critic_agent.md").read_text(),
    model=OPENAI_MODEL,
)
