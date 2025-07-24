from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional, Dict
from datetime import datetime
import uuid
from enum import Enum
from pydantic import validator

if False:
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
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_name: str = Field(unique=True, index=True, description="Unique username", min_length=1, max_length=50)
    user_level: UserLevel = Field(description="Current CEFR level")
    target_language: str = Field(description="Language being learned", min_length=1, max_length=50)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    partners: List["Partner"] = Relationship(back_populates="user")
    # Remove conversation_threads relationship - it uses user_name string, not UUID foreign key
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

class Partner(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(description="Display name for the partner", min_length=1, max_length=100)
    user_id: Optional[uuid.UUID] = Field(foreign_key="user.id", description="ID of the creator (null for premade)")
    ai_role: str = Field(description="Role of the AI in the conversation", min_length=1, max_length=100)
    scenario: str = Field(description="Description of the conversation scenario", min_length=1, max_length=500)
    target_language: str = Field(description="Language for the conversation", min_length=1, max_length=50)
    user_level: UserLevel = Field(description="Target CEFR level")
    
    # Enhanced partner description fields
    personality: str = Field(description="Personality traits and characteristics", min_length=1, max_length=1000)
    background: str = Field(description="Background story and experience", min_length=1, max_length=1000)
    communication_style: str = Field(description="How the partner communicates (formal/informal, tone, etc.)", min_length=1, max_length=500)
    expertise: str = Field(description="Specific knowledge and expertise in their field", min_length=1, max_length=1000)
    interests: str = Field(description="Personal interests and hobbies", min_length=1, max_length=500)
    
    is_premade: bool = Field(default=False, description="Whether this is a premade partner")
    is_active: bool = Field(default=True, description="Whether the partner is active")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    user: Optional[User] = Relationship(back_populates="partners")
    conversation_threads: List["ConversationThread"] = Relationship(back_populates="partner")

class ConversationThread(SQLModel, table=True):
    """New table for managing user-specific conversation threads"""
    id: str = Field(primary_key=True, description="Thread ID in format: user_name_partner_id")
    user_name: str = Field(index=True, description="Username")
    partner_id: uuid.UUID = Field(foreign_key="partner.id", description="Partner ID")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Relationships - only partner relationship since user uses string, not UUID
    partner: Optional[Partner] = Relationship(back_populates="conversation_threads")
    messages: List["Message"] = Relationship(back_populates="thread")

class Message(SQLModel, table=True):
    """New table for individual messages in threads"""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    thread_id: str = Field(foreign_key="conversationthread.id", index=True, description="Thread ID")
    role: str = Field(description="Role of the message sender (user/assistant)")
    content: str = Field(description="Message content")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Relationships
    thread: Optional[ConversationThread] = Relationship(back_populates="messages")

class CreatePartnerRequest(SQLModel):
    name: str = Field(description="Display name for the partner", min_length=1, max_length=100)
    ai_role: str = Field(description="Role of the AI in the conversation", min_length=1, max_length=100)
    scenario: str = Field(description="Description of the conversation scenario", min_length=1, max_length=500)
    target_language: str = Field(description="Language for the conversation", min_length=1, max_length=50)
    user_level: str = Field(description="Target CEFR level as string", min_length=2, max_length=2)
    
    # Enhanced partner description fields
    personality: str = Field(description="Personality traits and characteristics", min_length=1, max_length=1000)
    background: str = Field(description="Background story and experience", min_length=1, max_length=1000)
    communication_style: str = Field(description="How the partner communicates (formal/informal, tone, etc.)", min_length=1, max_length=500)
    expertise: str = Field(description="Specific knowledge and expertise in their field", min_length=1, max_length=1000)
    interests: str = Field(description="Personal interests and hobbies", min_length=1, max_length=500)
    
    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Partner name cannot be empty')
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
        if not v or not v.strip():
            raise ValueError('User level cannot be empty')
        if v not in [level.value for level in UserLevel]:
            raise ValueError(f'Invalid user_level: {v}. Must be one of: {[level.value for level in UserLevel]}')
        return v.strip()
    @validator('personality')
    def validate_personality(cls, v):
        if not v or not v.strip():
            raise ValueError('Personality description cannot be empty')
        return v.strip()
    @validator('background')
    def validate_background(cls, v):
        if not v or not v.strip():
            raise ValueError('Background description cannot be empty')
        return v.strip()
    @validator('communication_style')
    def validate_communication_style(cls, v):
        if not v or not v.strip():
            raise ValueError('Communication style cannot be empty')
        return v.strip()
    @validator('expertise')
    def validate_expertise(cls, v):
        if not v or not v.strip():
            raise ValueError('Expertise description cannot be empty')
        return v.strip()
    @validator('interests')
    def validate_interests(cls, v):
        if not v or not v.strip():
            raise ValueError('Interests description cannot be empty')
        return v.strip()

class ChatRequest(SQLModel):
    """Simplified chat request - thread_id is auto-generated"""
    user_name: str = Field(description="Username of the chat participant")
    partner_id: uuid.UUID = Field(description="ID of the conversation partner")
    user_input: str = Field(description="User's message content")

class GreetRequest(SQLModel):
    """Simplified greeting request - thread_id is auto-generated"""
    user_name: str = Field(description="Username of the user")
    partner_id: uuid.UUID = Field(description="ID of the conversation partner")

class GreetingResponse(SQLModel):
    greeting_message: str = Field(description="The partner's greeting message")
    partner_name: str = Field(description="Name of the partner")
    partner_role: str = Field(description="Role of the partner")
    scenario: str = Field(description="Current conversation scenario")
    thread_id: str = Field(description="Conversation thread ID")
    user_level: str = Field(description="User's current language level")
    target_language: str = Field(description="Target language for the conversation")

class ChatResponse(SQLModel):
    response: str = Field(description="AI partner's response")
    thread_id: str = Field(description="Conversation thread ID")

class Feedback(SQLModel):
    conversation_summary: str = Field(description="Overall summary of the conversation")
    message_analysis: List[Dict] = Field(description="Detailed analysis of each message")
    learning_points: List[str] = Field(description="Key learning points from the conversation")
    progress_tracking: Dict = Field(description="Progress metrics and improvements")

# Keep the old ConversationHistory for backward compatibility during migration
class ConversationHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: str = Field(index=True, description="Conversation thread identifier")
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True, description="ID of the participant")
    message_id: str = Field(description="Unique message identifier")
    role: str = Field(description="Role of the message sender (user/assistant)")
    content: str = Field(description="Message content")
    timestamp: str = Field(description="Message timestamp")
    partner_id: Optional[uuid.UUID] = Field(default=None, description="Associated partner ID")
    # Remove user relationship to avoid conflicts with new system
