from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.graph.message import add_messages
from typing import Annotated

class CustomState(AgentState):
    messages: Annotated[list, add_messages]
    user_name: str
    user_level: str
    ai_role: str
    scenario: str
    target_language: str