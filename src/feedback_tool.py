from langchain_openai import ChatOpenAI
from langchain.tools import tool

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

    system_prompt = f"""
        You are an experienced language tutor evaluating a conversation in {target_language}.
        The student, {user_name}, is currently at a {user_level} level and has been practicing the scenario: "{scenario}".

        Analyze the student's language use and provide structured, actionable feedback. For each message, provide:

        1. Message Analysis:
           - Original message
           - Corrected version (if needed)
           - Key grammar points used
           - Vocabulary highlights

        2. Learning Points:
           - 1-2 specific grammar rules demonstrated
           - 2-3 useful phrases/expressions
           - Common mistakes to avoid
           - Alternative expressions to try

        3. Progress Tracking:
           - Areas of improvement
           - Strengths demonstrated
           - Next learning goals

        Format your response as a JSON object with these sections:
        {{
            "conversation_summary": "Brief overview of the conversation",
            "messages_analysis": [
                {{
                    "original": "student's message",
                    "corrected": "corrected version if needed",
                    "grammar_points": ["point1", "point2"],
                    "vocabulary": ["word1", "word2"],
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
            "practice_suggestions": [
                "suggestion1",
                "suggestion2"
            ]
        }}

        Be specific, encouraging, and focus on practical learning points. Use simple, clear language appropriate for the student's level.
        """

    conversation = [{"role": "assistant", "content": system_prompt}] + messages
    response = llm.invoke(conversation)
    return response

