from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import AnyMessage
from dotenv import load_dotenv
from .states import CustomState
from .feedback_tool import feedback_tool

import sqlite3
import getpass
import os
from typing import List
import uuid

# --- Environment setup ---
load_dotenv(override=True)

# --- LangGraph setup ---
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
sqlite_conn = sqlite3.connect("checkpoint.sqlite", check_same_thread=False)
memory = SqliteSaver(sqlite_conn)
tools = [feedback_tool]

def build_prompt(state: CustomState) -> List[AnyMessage]:
    system_prompt = f"""
        You are an AI language partner helping a student improve their {state['target_language']} skills.
        The student, {state['user_name']}, is currently at a {state['user_level']} level and practicing the scenario: "{state['scenario']}".

        You can use tools when appropriate. You currently have access to:
        - feedback_tool: Use this when the user asks for feedback on their conversation so far.

        Your role:
        - Act as {state['ai_role']} within the context of the scenario.
        - Use tools when helpful to enhance the learning experience.
        - Assist the user in improving their {state['target_language']}, especially in conversation.
        - Use simple, beginner-friendly language.
        - Encourage the user and keep the conversation flowing naturally.
        - Be kind and supportive.
        - Avoid overwhelming the user with complex or rapid-fire questions.
        """

    return [{   
                "message_id":str(uuid.uuid4()),
                "role": "assistant",
                "content": system_prompt}] + state["messages"]

chat_agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=build_prompt,
    state_schema=CustomState,
    checkpointer=memory
)


