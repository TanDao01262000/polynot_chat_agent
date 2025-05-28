from langchain_openai import ChatOpenAI
from langchain.tools import tool

llm = ChatOpenAI(model="gpt-4o", temperature=0)

@tool("level_evaluator_tool")
def level_evaluator_tool(
    user_name: str,
    target_language: str,
    scenario: str,
    messages: list
) -> str:
    """
    Estimate the user's language proficiency level (A1, A2, B1, B2, C1, C2) based on their conversation.
    Returns a JSON object with 'estimated_level' and 'justification'.
    """
    system_prompt = f"""
        You are an experienced language teacher. Based on the following conversation in {target_language}, estimate the student's language proficiency level using the CEFR scale (A1, A2, B1, B2, C1, C2).
        The student's name is {user_name}. The scenario is: "{scenario}".

        Consider grammar, vocabulary, fluency, and overall communication effectiveness.
        Return a JSON object with:
        - estimated_level: (A1, A2, B1, B2, C1, or C2)
        - justification: (A brief explanation for your assessment)
        Use simple, clear language.
    """

    conversation = [{"role": "assistant", "content": system_prompt}] + messages
    response = llm.invoke(conversation)
    return response 