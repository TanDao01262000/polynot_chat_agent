from langchain_openai import ChatOpenAI
from langchain.tools import tool
import json
import os
from supabase import create_client, Client
from langchain_core.messages import AIMessage

# Use the same Supabase configuration as main.py
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

llm = ChatOpenAI(model="gpt-4o", temperature=0)

# Define CEFR levels for comparison
CEFR_LEVELS = {
    "A1": 1,
    "A2": 2,
    "B1": 3,
    "B2": 4,
    "C1": 5,
    "C2": 6
}

def compare_levels(current: str, new: str) -> bool:
    """Compare two CEFR levels, return True if new level is higher."""
    return CEFR_LEVELS.get(new, 0) > CEFR_LEVELS.get(current, 0)

@tool("level_evaluator_tool")
def level_evaluator_tool(
    user_name: str,
    target_language: str,
    scenario: str,
    messages: list
) -> str:
    """
    Evaluate user's language proficiency and update if improved.
    Returns a JSON object with:
    - estimated_level: A1/A2/B1/B2/C1/C2
    - justification: Explanation of the assessment
    - should_update: Whether level should be updated
    - update_success: Whether update was successful (if applicable)
    - update_message: Details about the update (if applicable)
    """
    # Get current level first
    try:
        response = supabase.table("profiles").select("*").eq("user_name", user_name).execute()
        if not response.data:
            return json.dumps({
                "success": False,
                "message": f"User {user_name} not found"
            })
        current_level = response.data[0]["user_level"]
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"Error getting current level: {str(e)}"
        })

    # Convert messages to the correct format
    formatted_messages = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            formatted_messages.append({
                "role": "assistant",
                "content": msg.content
            })
        else:
            formatted_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

    system_prompt = f"""
        Evaluate {user_name}'s {target_language} proficiency in the scenario: "{scenario}".
        Current level is {current_level}. Return a JSON object with:
        {{
            "estimated_level": "A1/A2/B1/B2/C1/C2",
            "justification": "Brief explanation",
            "should_update": true/false
        }}

        Consider: grammar, vocabulary, fluency, communication.
        Set should_update to true ONLY if estimated_level is higher than {current_level}.
        Use clear, simple language.
        """

    conversation = [{"role": "assistant", "content": system_prompt}] + formatted_messages
    response = llm.invoke(conversation)
    
    # Ensure the response is valid JSON
    try:
        if isinstance(response, AIMessage):
            response_data = json.loads(response.content)
        else:
            response_data = json.loads(response)
            
        if "estimated_level" not in response_data or "justification" not in response_data:
            return json.dumps({
                "success": False,
                "estimated_level": current_level,
                "justification": "Unable to properly evaluate level from the conversation.",
                "should_update": False
            })

        # Double check level comparison
        should_update = compare_levels(current_level, response_data["estimated_level"])
        response_data["should_update"] = should_update

        # If should_update is true, update the level
        if should_update:
            try:
                update_response = supabase.table("profiles").update({"user_level": response_data["estimated_level"]}).eq("user_name", user_name).execute()
                if update_response.data:
                    response_data["update_success"] = True
                    response_data["update_message"] = f"Level updated from {current_level} to {response_data['estimated_level']}"
                else:
                    response_data["update_success"] = False
                    response_data["update_message"] = "Failed to update user level"
            except Exception as e:
                response_data["update_success"] = False
                response_data["update_message"] = f"Error updating level: {str(e)}"

        response_data["success"] = True
        return json.dumps(response_data)
    except json.JSONDecodeError:
        return json.dumps({
            "success": False,
            "estimated_level": current_level,
            "justification": "Unable to properly evaluate level from the conversation.",
            "should_update": False
        })
    
@tool("get_user_level_tool")
def get_user_level_tool(user_name: str) -> str:
    """
    Get the user's current language proficiency level from the database.
    Returns a JSON object with 'level' and 'status'.
    """
    try:
        response = supabase.table("profiles").select("*").eq("user_name", user_name).execute()
        
        if not response.data:
            return json.dumps({
                "success": False,
                "message": f"User {user_name} not found"
            })
        
        user_level = response.data[0]["user_level"]
        return json.dumps({
            "success": True,
            "level": user_level,
            "message": f"Current level: {user_level}"
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"Error getting user level: {str(e)}"
        }) 