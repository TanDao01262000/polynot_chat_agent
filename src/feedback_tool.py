from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain_core.messages import AIMessage

llm = ChatOpenAI(model="gpt-4o", temperature=0)

@tool("feedback_tool")
def feedback_tool(
    user_name: str,
    user_level: str,
    target_language: str,
    scenario: str,
    messages: list
) -> str:
    """Provide detailed feedback for user's language learning progress."""

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
        You are a language tutor evaluating {user_name}'s {target_language} conversation (level: {user_level}) in the scenario: "{scenario}".

        Analyze the conversation and return a JSON object with:
        {{
            "conversation_summary": "Brief overview",
            "messages_analysis": [
                {{
                    "original": "student's message",
                    "corrected": "corrected version if needed",
                    "learning_points": {{
                        "grammar_rules": ["rule1", "rule2"],
                        "useful_phrases": ["phrase1", "phrase2"],
                        "common_mistakes": ["mistake1", "mistake2"],
                        "alternatives": ["alt1", "alt2"]
                    }}
                }}
            ],
            "progress_tracking": {{
                "improvements": ["area1", "area2"],
                "strengths": ["strength1", "strength2"],
                "next_goals": ["goal1", "goal2"]
            }},
            "practice_suggestions": ["suggestion1", "suggestion2"]
        }}

        Be specific, encouraging, and use language appropriate for {user_level} level.
        """

    conversation = [{"role": "assistant", "content": system_prompt}] + formatted_messages
    response = llm.invoke(conversation)
    return response

