from langchain_openai import ChatOpenAI
from langchain.tools import tool
import json
from sqlmodel import Session, select
from .models import User
from langchain_core.messages import AIMessage
from sqlmodel import create_engine

# Create engine for database access
sqlite_url = f"sqlite:///users.db"
engine = create_engine(sqlite_url, echo=True)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

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
        with Session(engine) as session:
            statement = select(User).where(User.user_name == user_name)
            user = session.exec(statement).first()
            if not user:
                return json.dumps({
                    "success": False,
                    "message": f"User {user_name} not found"
                })
            current_level = user.user_level
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
                with Session(engine) as session:
                    user = session.exec(select(User).where(User.user_name == user_name)).first()
                    if user:
                        user.user_level = response_data["estimated_level"]
                        session.add(user)
                        session.commit()
                        response_data["update_success"] = True
                        response_data["update_message"] = f"Level updated from {current_level} to {response_data['estimated_level']}"
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
        with Session(engine) as session:
            statement = select(User).where(User.user_name == user_name)
            user = session.exec(statement).first()
            
            if not user:
                return json.dumps({
                    "success": False,
                    "message": f"User {user_name} not found"
                })
            
            return json.dumps({
                "success": True,
                "level": user.user_level,
                "message": f"Current level: {user.user_level}"
            })
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"Error getting user level: {str(e)}"
        }) 