from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import AnyMessage
from dotenv import load_dotenv
from .states import CustomState
from .feedback_tool import feedback_tool
from .level_evaluator_tool import level_evaluator_tool

import sqlite3
import getpass
import os
from typing import List
import uuid
import json

# --- Environment setup ---
load_dotenv(override=True)

# --- LangGraph setup ---
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
sqlite_conn = sqlite3.connect("checkpoint.sqlite", check_same_thread=False)
memory = SqliteSaver(sqlite_conn)
tools = [feedback_tool, level_evaluator_tool]

def format_feedback(feedback_json: str) -> str:
    """Format the JSON feedback into a readable message."""
    try:
        feedback = json.loads(feedback_json)
        
        # Format the feedback into a clear, structured message
        formatted = f"📝 **Conversation Summary**\n{feedback['conversation_summary']}\n\n"
        
        formatted += "🔍 **Message Analysis**\n"
        for msg in feedback['messages_analysis']:
            formatted += f"\n📌 Original: \"{msg['original']}\""
            if msg['corrected']:
                formatted += f"\n✅ Corrected: \"{msg['corrected']}\""
            
            formatted += "\n\n📚 Learning Points:"
            formatted += f"\n• Grammar: {', '.join(msg['learning_points']['grammar_rules'])}"
            formatted += f"\n• Useful Phrases: {', '.join(msg['learning_points']['useful_phrases'])}"
            formatted += f"\n• Common Mistakes: {', '.join(msg['learning_points']['common_mistakes'])}"
            formatted += f"\n• Alternatives: {', '.join(msg['learning_points']['alternatives'])}"
            formatted += "\n"
        
        formatted += "\n📈 **Progress Tracking**\n"
        formatted += f"• Areas for Improvement: {', '.join(feedback['progress_tracking']['improvements'])}"
        formatted += f"\n• Strengths: {', '.join(feedback['progress_tracking']['strengths'])}"
        formatted += f"\n• Next Goals: {', '.join(feedback['progress_tracking']['next_goals'])}"
        
        formatted += "\n\n💡 **Practice Suggestions**\n"
        for suggestion in feedback['practice_suggestions']:
            formatted += f"• {suggestion}\n"
        
        return formatted
    except Exception as e:
        return f"Error formatting feedback: {str(e)}"

def build_prompt(state: CustomState) -> List[AnyMessage]:
    system_prompt = f"""
        You are an AI language partner helping a student improve their {state['target_language']} skills.
        The student, {state['user_name']}, is currently at a {state['user_level']} level and practicing the scenario: "{state['scenario']}".

        You have access to the following tools:
        1. feedback_tool: Use this automatically after every 3-4 messages or when the user asks for feedback to provide feedback on the conversation 
        2. level_evaluator_tool: Use this automatically after every 5-6 messages to evaluate if the student's level has improved.

        Your role:
        - Act as {state['ai_role']} within the context of the scenario.
        - Use tools automatically at appropriate intervals to enhance the learning experience.
        - Assist the user in improving their {state['target_language']}, especially in conversation.
        - Use simple, beginner-friendly language.
        - Encourage the user and keep the conversation flowing naturally.
        - Be kind and supportive.
        - Avoid overwhelming the user with complex or rapid-fire questions.
        - When using tools, explain to the user what you're doing and why.
        - When providing feedback, use the format_feedback function to present it in a clear, structured way.
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


