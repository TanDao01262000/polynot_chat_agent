from pydantic import BaseModel, Field
from typing import Optional

class ChatRequest(BaseModel):
    thread_id: str
    user_input: str
    user_name: str
    
    # optional custom config
    user_level: Optional[str] = None
    ai_role: Optional[str] = None
    scenario: Optional[str] = None
    target_language: Optional[str] = None
    scenario_id: Optional[str] = None

class Feedback(BaseModel):
    name: str
    overall_impression: str
    fluency: str
    grammar: str
    vocabulary: str
    suggestions_for_improvement: str

class FeedbackRequest(BaseModel):
    user_name: str
    user_level: str
    target_language: str
    scenario: str
    messages: list

