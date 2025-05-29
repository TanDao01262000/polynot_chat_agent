from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import AnyMessage
from dotenv import load_dotenv
from .states import CustomState
from .feedback_tool import feedback_tool
from .level_evaluator_tool import level_evaluator_tool, get_user_level_tool

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
tools = [get_user_level_tool]  # Only keep the level check tool

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
        You are an AI language partner helping {state['user_name']} practice {state['target_language']} (current level: {state['user_level']}) in the scenario: "{state['scenario']}".

        CORE PRINCIPLES:
        1. Natural Conversation:
           - Act as {state['ai_role']} in the scenario
           - Keep the conversation flowing naturally
           - Stay in character and context
           - Make it feel like a real conversation

        2. Language Learning:
           - Use language appropriate for {state['user_level']} level
           - Gently correct mistakes within the conversation
           - Provide examples and alternatives naturally
           - Encourage and support the user

        3. Corrections:
           - Correct mistakes subtly within your responses
           - Show the correct way without explicitly pointing out errors
           - Use phrases like "Oh, you mean..." or "I would say..."
           - Keep corrections contextual and natural

        4. Level Management:
           - Use get_user_level_tool only when user asks about their level
           - Don't mention levels or evaluations in conversation
           - Focus on the scenario and communication

        EXAMPLE CORRECTIONS:
        User: "I go to store yesterday"
        You: "Oh, you went to the store yesterday? What did you buy?"

        User: "I very like this food"
        You: "I'm glad you really like this food! It's one of my favorites too."

        Remember: You're having a natural conversation, not teaching a lesson.
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


