from langchain_openai import ChatOpenAI
from langchain.tools import tool
from dotenv import load_dotenv

load_dotenv(override=True)

llm = ChatOpenAI(model="gpt-4o", temperature=0)

@tool("feedback_tool")
def feedback_tool(
    user_name: str,
    user_level: str,
    target_language: str,
    scenario: str,
    messages: list
) -> str:
    """Provide feedback for user and print message_id for each message."""

    system_prompt = f"""
        You are an experienced language tutor evaluating a conversation in {target_language}.
        The student, {user_name}, is currently at a {user_level} level and has been practicing the scenario: "{scenario}".

        Your task is to analyze the student's language use and provide clear, constructive feedback for each message the student sent.

        For every user message, return a JSON object with the following fields:
        - message: (The student's original message)
        - overall_impression: (Brief summary of the effectiveness of this message)
        - fluency: (Was the message smooth and natural?)
        - grammar: (Any grammatical issues?)
        - vocabulary: (Was the word choice appropriate and varied?)
        - suggestions_for_improvement: (Specific tips or corrections)

        Use simple, beginner-friendly language. Be supportive and focus on how the student can improve.
        """

    conversation = [{"role": "assistant", "content": system_prompt}] + messages
    response = llm.invoke(conversation)
    return response

