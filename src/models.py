from sqlmodel import SQLModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

class UserLevel(str, Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

class User(SQLModel, table=True):
    """User model for storing language learner information."""
    user_name: str = Field(primary_key=True, description="Unique username")
    user_level: UserLevel = Field(description="Current CEFR level")
    target_language: str = Field(description="Language being learned")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class PremadeScenario(SQLModel, table=True):
    """Model for storing system-wide premade conversation scenarios."""
    id: str = Field(primary_key=True, description="Unique scenario identifier")
    ai_role: str = Field(description="Role of the AI in the conversation")
    scenario: str = Field(description="Description of the conversation scenario")
    target_language: str = Field(description="Language for the conversation")
    user_level: UserLevel = Field(description="Target CEFR level")
    is_active: bool = Field(default=True, description="Whether the scenario is active")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class CustomScenario(SQLModel, table=True):
    """Model for storing user-created conversation scenarios."""
    id: str = Field(primary_key=True, description="Unique scenario identifier")
    user_name: str = Field(index=True, description="Username of the creator")
    ai_role: str = Field(description="Role of the AI in the conversation")
    scenario: str = Field(description="Description of the conversation scenario")
    target_language: str = Field(description="Language for the conversation")
    user_level: UserLevel = Field(description="Target CEFR level")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = Field(default=True, description="Whether the scenario is active")

class ChatRequest(SQLModel):
    """Request model for chat interactions."""
    user_name: str = Field(description="Username of the chat participant")
    thread_id: str = Field(description="Unique conversation thread identifier")
    user_input: str = Field(description="User's message content")
    scenario_id: Optional[str] = Field(default=None, description="ID of the conversation scenario")
    ai_role: Optional[str] = Field(default=None, description="Role of the AI in the conversation")
    scenario: Optional[str] = Field(default=None, description="Description of the conversation scenario")
    target_language: Optional[str] = Field(default=None, description="Language for the conversation")

class Feedback(SQLModel):
    """Model for storing conversation feedback."""
    conversation_summary: str = Field(description="Overall summary of the conversation")
    message_analysis: List[Dict] = Field(description="Detailed analysis of each message")
    learning_points: List[str] = Field(description="Key learning points from the conversation")
    progress_tracking: Dict = Field(description="Progress metrics and improvements")

class ConversationHistory(SQLModel, table=True):
    """Model for storing conversation history."""
    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: str = Field(index=True, description="Conversation thread identifier")
    user_name: str = Field(index=True, description="Username of the participant")
    message_id: str = Field(description="Unique message identifier")
    role: str = Field(description="Role of the message sender (user/assistant)")
    content: str = Field(description="Message content")
    timestamp: str = Field(description="Message timestamp")
    scenario_id: Optional[str] = Field(default=None, description="Associated scenario ID")

