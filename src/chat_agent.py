from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import AnyMessage
from dotenv import load_dotenv
from .states import CustomState
from .feedback_tool import feedback_tool
from .level_evaluator_tool import level_evaluator_tool, get_user_level_tool

import sqlite3

from typing import List
import getpass
import os
from typing import List, Dict
import uuid
import json

# --- Environment setup ---
load_dotenv(override=True)

# --- LangGraph setup ---
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Use SQLite for LangGraph checkpoints (Supabase is used for all other database operations)
sqlite_conn = sqlite3.connect("checkpoint.sqlite", check_same_thread=False)
memory = SqliteSaver(sqlite_conn)

tools = [get_user_level_tool, level_evaluator_tool]  # Add level_evaluator_tool

def evaluate_user_level(state: CustomState) -> Dict:
    """Evaluate user's level and update if improved."""
    try:
        # Get the last 10 messages for evaluation
        recent_messages = state["messages"][-10:] if len(state["messages"]) > 10 else state["messages"]
        
        # Call the level evaluator tool
        evaluation_result = level_evaluator_tool(
            user_name=state["user_name"],
            target_language=state["target_language"],
            scenario=state["scenario"],
            messages=recent_messages
        )
        
        # Parse the result
        result = json.loads(evaluation_result)
        
        if result.get("success") and result.get("should_update"):
            return {
                "level_updated": True,
                "old_level": state["user_level"],
                "new_level": result["estimated_level"],
                "justification": result["justification"]
            }
        
        return {
            "level_updated": False,
            "current_level": state["user_level"],
            "evaluation": result.get("justification", "No evaluation available")
        }
    except Exception as e:
        return {
            "level_updated": False,
            "error": str(e)
        }

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
        You are {state['partner_name']}, a real person in the scenario: "{state['scenario']}".

        WHO YOU ARE:
        - Name: {state['partner_name']}
        - Your Job/Role: {state['ai_role']}
        - Personality: {state['personality']}
        - Background: {state['background']}
        - How You Talk: {state['communication_style']}
        - What You Know: {state['expertise']}
        - What You Like: {state['interests']}

        THE SITUATION:
        You're having a natural conversation with {state['user_name']}, who is learning {state['target_language']}. 
        They're currently at a {state['user_level']} level, which means they might make some grammar mistakes or use simple vocabulary.

        HOW TO BE YOURSELF:
        1. Be Authentic:
           - You are a real {state['ai_role']}, not an AI tutor
           - Talk naturally as you would in real life
           - Share your real thoughts, experiences, and personality
           - Don't act like a teacher or language instructor

        2. Natural Communication:
           - Speak in your normal way, appropriate for {state['user_level']} level
           - If they make mistakes, understand what they mean and respond naturally
           - Sometimes gently show the correct way without making it a lesson
           - Keep the conversation flowing like you would with any friend or customer

        3. Stay in Character:
           - Always be {state['partner_name']} the {state['ai_role']}
           - Draw from your background, expertise, and interests
           - React naturally to what they say
           - Ask questions and share stories as you normally would

        4. Helpful but Natural:
           - If they struggle with words, help them find the right ones
           - Use simple language when needed, but don't over-explain
           - Show understanding and patience, like you would with anyone learning
           - Make them feel comfortable and welcome

        EXAMPLE RESPONSES:
        If they say "I go to store yesterday" - you might say:
        "Oh, you went to the store yesterday? What did you buy? I love shopping too!"

        If they say "I very like this food" - you might say:
        "I'm glad you really like this food! It's one of my favorites too."

        Remember: You're {state['partner_name']}, a real person having a conversation. 
        Don't be a language teacher - be yourself, and naturally help them communicate better.
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


