from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, Dict, TYPE_CHECKING
from datetime import datetime
from enum import Enum
import uuid
from pydantic import validator

if TYPE_CHECKING:
    from sqlmodel import Session

class UserLevel(str, Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"
    
    def __str__(self):
        return self.value

class User(SQLModel, table=True):
    """User model for storing language learner information."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_name: str = Field(unique=True, index=True, description="Unique username", min_length=1, max_length=50)
    user_level: UserLevel = Field(description="Current CEFR level")
    target_language: str = Field(description="Language being learned", min_length=1, max_length=50)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Relationships
    custom_scenarios: List["CustomScenario"] = Relationship(back_populates="user")
    conversation_history: List["ConversationHistory"] = Relationship(back_populates="user")
    
    @validator('user_name')
    def validate_user_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Username cannot be empty')
        return v.strip()
    
    @validator('target_language')
    def validate_target_language(cls, v):
        if not v or not v.strip():
            raise ValueError('Target language cannot be empty')
        return v.strip()

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
    user_id: str = Field(foreign_key="user.id", description="ID of the creator")
    ai_role: str = Field(description="Role of the AI in the conversation")
    scenario: str = Field(description="Description of the conversation scenario")
    target_language: str = Field(description="Language for the conversation")
    user_level: UserLevel = Field(description="Target CEFR level")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = Field(default=True, description="Whether the scenario is active")
    
    # Relationships
    user: User = Relationship(back_populates="custom_scenarios")

class CreateCustomScenarioRequest(SQLModel):
    """Request model for creating custom scenarios."""
    user_name: str = Field(description="Username of the creator", min_length=1, max_length=50)
    ai_role: str = Field(description="Role of the AI in the conversation", min_length=1, max_length=100)
    scenario: str = Field(description="Description of the conversation scenario", min_length=1, max_length=500)
    target_language: str = Field(description="Language for the conversation", min_length=1, max_length=50)
    user_level: str = Field(description="Target CEFR level as string", min_length=2, max_length=2)
    
    @validator('user_name')
    def validate_user_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Username cannot be empty')
        return v.strip()
    
    @validator('ai_role')
    def validate_ai_role(cls, v):
        if not v or not v.strip():
            raise ValueError('AI role cannot be empty')
        return v.strip()
    
    @validator('scenario')
    def validate_scenario(cls, v):
        if not v or not v.strip():
            raise ValueError('Scenario description cannot be empty')
        return v.strip()
    
    @validator('target_language')
    def validate_target_language(cls, v):
        if not v or not v.strip():
            raise ValueError('Target language cannot be empty')
        return v.strip()
    
    @validator('user_level')
    def validate_user_level(cls, v):
        valid_levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        if v not in valid_levels:
            raise ValueError(f'Invalid user_level: {v}. Must be one of: {valid_levels}')
        return v

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
    user_id: str = Field(foreign_key="user.id", index=True, description="ID of the participant")
    message_id: str = Field(description="Unique message identifier")
    role: str = Field(description="Role of the message sender (user/assistant)")
    content: str = Field(description="Message content")
    timestamp: str = Field(description="Message timestamp")
    scenario_id: Optional[str] = Field(default=None, description="Associated scenario ID")
    scenario_type: Optional[str] = Field(default=None, description="Type of scenario: 'premade' or 'custom'")
    
    # Relationships
    user: User = Relationship(back_populates="conversation_history")
