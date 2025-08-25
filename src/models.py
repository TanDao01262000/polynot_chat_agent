from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from enum import Enum
from pydantic import validator, field_validator

if False:
    from sqlmodel import Session

# ============================================================================
# User Models
# ============================================================================

class UserLevel(str, Enum):
    """User language proficiency levels based on CEFR"""
    A1 = "A1"  # Beginner
    A2 = "A2"  # Elementary
    B1 = "B1"  # Intermediate
    B2 = "B2"  # Upper Intermediate
    C1 = "C1"  # Advanced
    C2 = "C2"  # Mastery

class User(SQLModel, table=True):
    """User model for language learners - maps to profiles table"""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_name: str = Field(unique=True, description="Unique username")
    user_level: UserLevel = Field(description="User's language proficiency level")
    target_language: str = Field(description="Language the user wants to learn (will be stored as array in DB)")
    email: str = Field(description="User's email address (required for account creation)")
    first_name: Optional[str] = Field(default=None, description="User's first name")
    last_name: Optional[str] = Field(default=None, description="User's last name")
    native_language: Optional[str] = Field(default=None, description="User's native language")
    country: Optional[str] = Field(default=None, description="User's country")
    interests: Optional[str] = Field(default=None, description="User's interests (comma-separated)")
    proficiency_level: Optional[str] = Field(default=None, description="User's proficiency level")
    bio: Optional[str] = Field(default=None, description="User's bio")
    learning_goals: Optional[str] = Field(default=None, description="User's learning goals")
    preferred_topics: Optional[str] = Field(default=None, description="Preferred conversation topics")
    study_time_preference: Optional[str] = Field(default=None, description="Preferred study time")
    avatar_url: Optional[str] = Field(default=None, description="User's avatar URL")
    is_active: bool = Field(default=True, description="Whether user account is active")
    last_login: Optional[str] = Field(default=None, description="Last login timestamp")
    total_conversations: int = Field(default=0, description="Total conversations")
    total_messages: int = Field(default=0, description="Total messages")
    streak_days: int = Field(default=0, description="Current streak days")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    @validator('user_name')
    def validate_username(cls, v):
        if not v or not v.strip():
            raise ValueError('Username cannot be empty')
        return v.strip()
    
    @validator('target_language')
    def validate_target_language(cls, v):
        if not v or not v.strip():
            raise ValueError('Target language cannot be empty')
        return v.strip()

# ============================================================================
# Partner Models
# ============================================================================

class Partner(SQLModel, table=True):
    """AI conversation partner model"""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(description="Partner's name")
    user_id: Optional[uuid.UUID] = Field(default=None, description="ID of the creator (null for premade)")
    ai_role: str = Field(description="Partner's role or profession")
    scenario: str = Field(description="Conversation scenario or context")
    target_language: str = Field(description="Language the partner speaks")
    user_level: UserLevel = Field(description="Appropriate user level for this partner")
    personality: str = Field(description="Partner's personality traits")
    background: str = Field(description="Partner's background story")
    communication_style: str = Field(description="How the partner communicates")
    expertise: str = Field(description="Partner's areas of expertise")
    interests: str = Field(description="Partner's interests and hobbies")
    is_premade: bool = Field(default=False, description="Whether this is a premade partner")
    is_active: bool = Field(default=True, description="Whether this partner is available")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    @validator('name', 'ai_role', 'scenario', 'target_language', 'personality', 'background', 'communication_style', 'expertise', 'interests')
    def validate_required_fields(cls, v):
        if not v or not v.strip():
            raise ValueError('This field cannot be empty')
        return v.strip()

# ============================================================================
# Chat and Conversation Models
# ============================================================================

class ChatRequest(SQLModel):
    """Request model for chat interactions"""
    user_name: str = Field(description="Username of the person chatting")
    user_input: str = Field(description="User's message input")
    partner_id: uuid.UUID = Field(description="ID of the AI partner")
    thread_id: Optional[str] = Field(default=None, description="Conversation thread ID")

class ChatResponse(SQLModel):
    """Response model for chat interactions"""
    response: str = Field(description="AI partner's response")
    thread_id: str = Field(description="Conversation thread ID")

class Message(SQLModel, table=True):
    """Individual message in a conversation"""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    thread_id: str = Field(description="Conversation thread ID")
    role: str = Field(description="Message sender (user/assistant)")
    content: str = Field(description="Message content")
    message_timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    @validator('content', 'role')
    def validate_required_fields(cls, v):
        if not v or not v.strip():
            raise ValueError('This field cannot be empty')
        return v.strip()

class ConversationThread(SQLModel, table=True):
    """Conversation thread model"""
    id: str = Field(primary_key=True, description="Thread ID")
    user_name: str = Field(description="Username")
    partner_id: uuid.UUID = Field(description="Partner ID")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class ConversationHistory(SQLModel):
    """Model for conversation history"""
    thread_id: str = Field(description="Thread ID")
    messages: List[Message] = Field(description="List of messages")

# ============================================================================
# Feedback and Evaluation Models
# ============================================================================

class Feedback(SQLModel):
    """Model for conversation feedback"""
    thread_id: str = Field(description="Thread ID")
    feedback: Dict[str, Any] = Field(description="Detailed feedback")

class FeedbackRequest(SQLModel):
    """Request model for feedback"""
    thread_id: str = Field(description="Thread ID")
    user_name: str = Field(description="Username")

class EvaluationRequest(SQLModel):
    """Request model for level evaluation"""
    thread_id: str = Field(description="Thread ID")
    user_name: str = Field(description="Username")

class EvaluationResponse(SQLModel):
    """Response model for level evaluation"""
    current_level: str = Field(description="Current language level")
    suggested_level: str = Field(description="Suggested new level")
    confidence: float = Field(description="Confidence in the evaluation")
    reasoning: str = Field(description="Reasoning for the evaluation")

# ============================================================================
# Partner Management Models
# ============================================================================

class CreatePartnerRequest(SQLModel):
    """Request model for creating custom partners"""
    name: str = Field(description="Partner's name")
    ai_role: str = Field(description="Partner's role or profession")
    scenario: str = Field(description="Conversation scenario or context")
    target_language: str = Field(description="Language the partner speaks")
    user_level: UserLevel = Field(description="Appropriate user level for this partner")
    personality: str = Field(description="Partner's personality traits")
    background: str = Field(description="Partner's background story")
    communication_style: str = Field(description="How the partner communicates")
    expertise: str = Field(description="Partner's areas of expertise")
    interests: str = Field(description="Partner's interests and hobbies")
    user_name: Optional[str] = Field(default=None, description="Username of the partner creator (for user-specific partners)")

# ============================================================================
# Greeting Models
# ============================================================================

class GreetRequest(SQLModel):
    """Request model for greeting generation"""
    user_name: str = Field(description="Username")
    partner_id: uuid.UUID = Field(description="Partner ID")

class GreetingResponse(SQLModel):
    """Response model for greeting generation"""
    greeting_message: str = Field(description="Generated greeting message")
    partner_name: str = Field(description="Partner's name")
    partner_role: str = Field(description="Partner's role")
    scenario: str = Field(description="Conversation scenario")
    thread_id: str = Field(description="Thread ID")
    user_level: str = Field(description="User's language level")
    target_language: str = Field(description="Target language")

# ============================================================================
# Enhanced User Profile Models
# ============================================================================

class Achievement(SQLModel):
    """Model for user achievements"""
    id: str = Field(description="Achievement ID")
    name: str = Field(description="Achievement name")
    description: str = Field(description="Achievement description")
    icon: str = Field(description="Achievement icon")
    unlocked_at: Optional[str] = Field(description="When achievement was unlocked")

class Milestone(SQLModel):
    """Model for user milestones"""
    type: str = Field(description="Milestone type")
    current: int = Field(description="Current progress")
    next: int = Field(description="Next milestone target")
    description: str = Field(description="Milestone description")

class UserAchievements(SQLModel):
    """Model for user achievements response"""
    total_achievements: int = Field(description="Total number of achievements")
    achievements: List[Achievement] = Field(description="List of achievements")
    next_milestones: List[Milestone] = Field(description="Next milestones to achieve")

class ProfileCompletion(SQLModel):
    """Model for profile completion response"""
    completion_percentage: float = Field(description="Profile completion percentage")
    completed_fields: int = Field(description="Number of completed fields")
    total_fields: int = Field(description="Total number of required fields")
    missing_fields: List[str] = Field(description="List of missing fields")
    profile_level: str = Field(description="Profile completion level")

class UserProfileUpdate(SQLModel):
    """Model for updating user profile information"""
    first_name: Optional[str] = Field(default=None, description="User's first name")
    last_name: Optional[str] = Field(default=None, description="User's last name")
    native_language: Optional[str] = Field(default=None, description="User's native language")
    country: Optional[str] = Field(default=None, description="User's country")
    interests: Optional[str] = Field(default=None, description="User's interests")
    proficiency_level: Optional[str] = Field(default=None, description="User's proficiency level")
    bio: Optional[str] = Field(default=None, description="User's bio")
    learning_goals: Optional[str] = Field(default=None, description="User's learning goals")
    preferred_topics: Optional[str] = Field(default=None, description="Preferred conversation topics")
    study_time_preference: Optional[str] = Field(default=None, description="Preferred study time")
    avatar_url: Optional[str] = Field(default=None, description="User's avatar URL")

class UserLevelUpdate(SQLModel):
    """Model for updating user's language level"""
    user_level: UserLevel = Field(description="New language level")

class UserStatistics(SQLModel):
    """Model for user learning statistics"""
    total_conversations: int = Field(description="Total number of conversations")
    total_messages: int = Field(description="Total number of messages sent")
    streak_days: int = Field(description="Current login streak")
    average_messages_per_conversation: float = Field(description="Average messages per conversation")
    last_login: Optional[str] = Field(description="Last login timestamp")

class UserProfileResponse(SQLModel):
    """Complete user profile response"""
    id: str = Field(description="User ID")
    user_name: str = Field(description="Username")
    user_level: str = Field(description="User's language level")
    target_language: str = Field(description="Target language")
    email: Optional[str] = Field(description="User's email")
    first_name: Optional[str] = Field(description="User's first name")
    last_name: Optional[str] = Field(description="User's last name")
    native_language: Optional[str] = Field(description="User's native language")
    country: Optional[str] = Field(description="User's country")
    interests: Optional[List[str]] = Field(description="User's interests")
    proficiency_level: Optional[str] = Field(description="User's proficiency level")
    bio: Optional[str] = Field(description="User's bio")
    learning_goals: Optional[str] = Field(description="User's learning goals")
    preferred_topics: Optional[List[str]] = Field(description="Preferred conversation topics")
    study_time_preference: Optional[str] = Field(description="Preferred study time")
    avatar_url: Optional[str] = Field(description="User's avatar URL")
    is_active: Optional[bool] = Field(default=True, description="Whether user account is active")
    created_at: Optional[str] = Field(description="Account creation timestamp")
    last_login: Optional[str] = Field(description="Last login timestamp")
    statistics: Optional[UserStatistics] = Field(default=None, description="User learning statistics")
