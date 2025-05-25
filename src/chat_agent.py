from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState
from langchain_core.messages import AnyMessage
from typing import List
from langgraph.graph.message import add_messages
from typing import Annotated
from dotenv import load_dotenv

import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

load_dotenv(override=True)

# --- LangGraph setup ---
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
sqlite_conn = sqlite3.connect("checkpoint.sqlite", check_same_thread=False)
memory = SqliteSaver(sqlite_conn)
tools = []

class CustomState(AgentState):
    messages: Annotated[list, add_messages]
    user_name: str
    user_level: str
    ai_role: str
    scenario: str
    target_language: str

def build_prompt(state: CustomState) -> List[AnyMessage]:
    system_prompt = f"""
    You are an AI language partner helping a student improve their {state['target_language']} skills.
    The student's name is {state['user_name']} at a {state['user_level']} level and is currently practicing the scenario: "{state['scenario']}".

    Your roles:
    - Act as {state['ai_role']} in the scenario
    - Help user improve their {state['target_language']}
    - Use beginner-friendly language
    - Encourage, be kind, and keep conversation flowing
    - Avoid overwhelming questions
    """
    return [{"role": "system", "content": system_prompt}] + state["messages"]

chat_agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=build_prompt,
    state_schema=CustomState,
    checkpointer=memory
)

