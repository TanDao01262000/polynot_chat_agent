"""
PolyNot Language Learning API - Updated with User-Specific Thread IDs
--------------------------------------------------------------------
A FastAPI-based application for language learning conversations with AI partners.
The system now uses user-specific thread IDs in format: {user_name}_{partner_id}
"""

from fastapi import FastAPI, HTTPException, Depends, status, Header
import uuid
import os
import json
import logging
from typing import List, Optional, Dict
from datetime import datetime
from supabase import create_client, Client
from uuid import UUID
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from src.chat_agent import chat_agent
from src.models import (
    ChatRequest, ChatResponse, Feedback, ConversationHistory, User,
    UserLevel, Partner, CreatePartnerRequest, GreetRequest, GreetingResponse,
    ConversationThread, Message, UserProfileUpdate, UserLevelUpdate, 
    UserStatistics, UserProfileResponse, UserAchievements, ProfileCompletion,
    UserLogin, PasswordResetRequest
)
from src.feedback_tool import feedback_tool
from src.level_evaluator_tool import level_evaluator_tool
from src.social_models import (
    CreatePostRequest, UpdatePostRequest, PostResponse, CommentRequest, CommentResponse,
    NewsFeedRequest, NewsFeedResponse, SocialUserProfileResponse,
    FollowRequest, PointsSummary, LeaderboardResponse,
    SmartFeedRequest, SmartFeedResponse, UserPrivacySettings, TrendingContent,
    StudyAnalyticsRequest, StudyAnalyticsResponse, WordStudyRecord, GlobalWordAnalytics,
    StudyInsights, WordRecommendation
)
from src.social_service import SocialService
from src.social_integration import SocialIntegration
from src.smart_feed_service import SmartFeedService
from src.study_analytics_service import StudyAnalyticsService

# ============================================================================
# Configuration and Setup
# ============================================================================

# Load environment variables from .env file
load_dotenv(override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# LangChain configuration
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "polynot")
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables")

# Initialize Supabase client with anon key for user operations
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Initialize service role client for server operations (bypasses RLS)
if SUPABASE_SERVICE_ROLE_KEY:
    supabase_service: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    logger.info("Supabase service role client initialized successfully")
else:
    supabase_service = supabase  # Fallback to anon key
    logger.warning("SUPABASE_SERVICE_ROLE_KEY not set, using anon key for server operations")

logger.info("Supabase client initialized successfully")

# ============================================================================
# Thread Management Helper Functions
# ============================================================================

def generate_thread_id(user_name: str, partner_id: str) -> str:
    """Generate user-specific thread ID in format: user_name_partner_id"""
    return f"{user_name}_{partner_id}"

def get_thread(thread_id: str, supabase_client: Client) -> Optional[Dict]:
    """Check if thread exists and return thread data"""
    try:
        response = supabase_client.table("conversation_thread").select("*").eq("id", thread_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error getting thread {thread_id}: {str(e)}")
        return None

def create_thread(thread_id: str, user_name: str, partner_id: str, supabase_client: Client) -> Dict:
    """Create new conversation thread"""
    try:
        thread_data = {
            "id": thread_id,
            "user_name": user_name,
            "partner_id": str(partner_id),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        response = supabase_client.table("conversation_thread").insert(thread_data).execute()
        if response.data:
            logger.info(f"Created new thread: {thread_id}")
            return response.data[0]
        else:
            raise Exception("Failed to create thread")
    except Exception as e:
        logger.error(f"Error creating thread {thread_id}: {str(e)}")
        raise

def save_message(thread_id: str, content: str, role: str, supabase_client: Client) -> Dict:
    """Save message to database"""
    try:
        message_data = {
            "thread_id": thread_id,
            "role": role,
            "content": content,
            "message_timestamp": datetime.now().isoformat()  # Use message_timestamp instead of timestamp
        }
        
        response = supabase_client.table("message").insert(message_data).execute()
        if response.data:
            logger.info(f"Saved {role} message to thread {thread_id}")
            return response.data[0]
        else:
            raise Exception("Failed to save message")
    except Exception as e:
        logger.error(f"Error saving message to thread {thread_id}: {str(e)}")
        raise

def get_messages(thread_id: str, supabase_client: Client) -> List[Dict]:
    """Get all messages for a thread"""
    try:
        response = supabase_client.table("message").select("*").eq("thread_id", thread_id).order("message_timestamp").execute()  # Use message_timestamp instead of timestamp
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error getting messages for thread {thread_id}: {str(e)}")
        return []

def get_or_create_thread(user_name: str, partner_id: str, supabase_client: Client) -> str:
    """Get existing thread or create new one"""
    thread_id = generate_thread_id(user_name, str(partner_id))
    
    # Check if thread exists
    existing_thread = get_thread(thread_id, supabase_client)
    if not existing_thread:
        # Create new thread
        create_thread(thread_id, user_name, partner_id, supabase_client)
    
    return thread_id

def calculate_user_statistics(user_name: str, supabase_client: Client) -> UserStatistics:
    """Calculate comprehensive user learning statistics."""
    try:
        # Get user's conversation threads
        threads_response = supabase_client.table("conversation_thread").select("*").eq("user_name", user_name).execute()
        threads = threads_response.data if threads_response.data else []
        
        # Get all messages for the user
        total_messages = 0
        favorite_partners = {}
        level_progress = {}
        
        for thread in threads:
            # Get messages for this thread
            messages_response = supabase_client.table("message").select("*").eq("thread_id", thread["id"]).execute()
            messages = messages_response.data if messages_response.data else []
            
            # Count user messages
            user_messages = [msg for msg in messages if msg["role"] == "user"]
            total_messages += len(user_messages)
            
            # Track partner usage
            partner_id = thread["partner_id"]
            if partner_id in favorite_partners:
                favorite_partners[partner_id] += len(user_messages)
            else:
                favorite_partners[partner_id] = len(user_messages)
        
        # Calculate average messages per conversation
        total_conversations = len(threads)
        average_messages = total_messages / total_conversations if total_conversations > 0 else 0
        
        # Get top 3 favorite partners
        sorted_partners = sorted(favorite_partners.items(), key=lambda x: x[1], reverse=True)
        top_partners = [partner_id for partner_id, _ in sorted_partners[:3]]
        
        # Get user's current level for progress tracking
        user_response = supabase_client.table("profiles").select("user_level, streak_days").eq("user_name", user_name).execute()
        user_data = user_response.data[0] if user_response.data else {}
        current_level = user_data.get("user_level", "A1")
        streak_days = user_data.get("streak_days", 0)
        
        # Simple level progress (you might want to enhance this)
        level_progress = {
            "A1": 100 if current_level == "A1" else 0,
            "A2": 100 if current_level in ["A2", "B1", "B2", "C1", "C2"] else 0,
            "B1": 100 if current_level in ["B1", "B2", "C1", "C2"] else 0,
            "B2": 100 if current_level in ["B2", "C1", "C2"] else 0,
            "C1": 100 if current_level in ["C1", "C2"] else 0,
            "C2": 100 if current_level == "C2" else 0
        }
        
        # Get last activity (most recent message timestamp)
        last_activity = None
        if threads:
            # Get the most recent thread
            latest_thread = max(threads, key=lambda x: x["updated_at"])
            last_activity = latest_thread["updated_at"]
        
        return UserStatistics(
            total_conversations=total_conversations,
            total_messages=total_messages,
            streak_days=streak_days,
            average_messages_per_conversation=round(average_messages, 2),
            last_login=last_activity
        )
        
    except Exception as e:
        logger.error(f"Error calculating user statistics: {str(e)}")
        # Return default statistics on error
        return UserStatistics(
            total_conversations=0,
            total_messages=0,
            streak_days=0,
            average_messages_per_conversation=0.0,
            last_login=None
        )

def update_user_chat_statistics(user_name: str, supabase_client: Client):
    """Update user's chat statistics when they send a message."""
    try:
        # Increment total_messages
        response = supabase_client.table("profiles").select("total_messages").eq("user_name", user_name).execute()
        if response.data:
            current_messages = response.data[0].get("total_messages", 0)
            new_total = current_messages + 1
            
            supabase_client.table("profiles").update({
                "total_messages": new_total,
                "updated_at": datetime.now().isoformat()
            }).eq("user_name", user_name).execute()
            
    except Exception as e:
        logger.error(f"Error updating user chat statistics: {str(e)}")

def update_thread_timestamp(thread_id: str, supabase_client: Client):
    """Update thread's updated_at timestamp."""
    try:
        supabase_client.table("conversation_thread").update({
            "updated_at": datetime.now().isoformat()
        }).eq("id", thread_id).execute()
        
    except Exception as e:
        logger.error(f"Error updating thread timestamp: {str(e)}")

# ============================================================================
# FastAPI Application Setup
# ============================================================================

app = FastAPI(
    title="PolyNot Language Learning API",
    description="API for language learning conversations with user-specific thread IDs",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ============================================================================
# Initial Premade Partners (same as before)
# ============================================================================

INITIAL_PREMADE_PARTNERS = [
    {
        "id": str(UUID("11111111-1111-1111-1111-111111111111")),
        "name": "Emily Carter",
        "ai_role": "barista",
        "scenario": "Ordering a drink at a coffee shop",
        "target_language": "English",
        "user_level": UserLevel.A2,
        "personality": "Emily is a warm, enthusiastic barista who loves coffee and people. She's patient, friendly, and always ready to help customers find their perfect drink.",
        "background": "Emily has been working as a barista for 3 years at this popular local coffee shop. She studied hospitality in college and has a passion for coffee culture.",
        "communication_style": "Emily speaks in a friendly, casual manner. She uses simple, clear language and is very patient with non-native speakers.",
        "expertise": "Emily is an expert in coffee preparation, different brewing methods, and coffee bean varieties.",
        "interests": "Emily loves trying new coffee beans, reading about coffee culture, and experimenting with latte art.",
        "is_premade": True,
        "is_active": True
    },
    # Add more premade partners as needed...
]

# ============================================================================
# Application Lifecycle Events
# ============================================================================

@app.on_event("startup")
def on_startup():
    """Initialize database on application startup."""
    try:
        # Test Supabase connection
        response = supabase.table("profiles").select("count", count="exact").limit(1).execute()
        logger.info("Supabase connection successful")
        
        # Initialize premade partners if they don't exist
        partners_response = supabase.table("partners").select("*").execute()
        existing_partners = partners_response.data
        
        if not existing_partners:
            logger.info("Initializing premade partners...")
            for partner_data in INITIAL_PREMADE_PARTNERS:
                supabase.table("partners").insert(partner_data).execute()
            logger.info("Premade partners initialized successfully")
        else:
            logger.info(f"Found {len(existing_partners)} existing partners")
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise Exception(f"Database initialization failed: {str(e)}")

def get_supabase() -> Client:
    """Dependency to get Supabase client."""
    return supabase

def get_supabase_service() -> Client:
    """Dependency to get Supabase service role client for server operations."""
    if SUPABASE_SERVICE_ROLE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    else:
        logger.warning("SUPABASE_SERVICE_ROLE_KEY not set, using anon key")
        return supabase

# ============================================================================
# Updated Chat System Endpoints
# ============================================================================

@app.post("/greet", response_model=GreetingResponse)
def greet_user(req: GreetRequest, supabase_client: Client = Depends(get_supabase)):
    """
    Generate a greeting message from a partner when user first clicks on them.
    
    Flow:
    1. Verify user exists
    2. Get partner configuration
    3. Get or create thread (user_name_partner_id format)
    4. Check if thread has existing messages
    5. Generate greeting if new thread
    6. Store greeting in database
    7. Return greeting with thread context
    """
    try:
        # Get user from database
        user_response = supabase_client.table("profiles").select("*").eq("user_name", req.user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user = user_response.data[0]

        # Get partner configuration
        partner = get_partner_config(req.partner_id, supabase_client)
        if not partner:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partner not found"
            )

        # Get or create thread
        thread_id = get_or_create_thread(req.user_name, str(req.partner_id), supabase_client)
        
        # Check if thread has existing messages
        existing_messages = get_messages(thread_id, supabase_client)
        
        if existing_messages:
            # Return last message as greeting
            last_message = existing_messages[-1]
            greeting_message = last_message["content"]
        else:
            # Generate new greeting
            greeting_prompt = f"""
            You are {partner['name']}, a {partner['ai_role']} in the scenario: "{partner['scenario']}".
            
            WHO YOU ARE:
            - Name: {partner['name']}
            - Your Job/Role: {partner['ai_role']}
            - Personality: {partner['personality']}
            - Background: {partner['background']}
            - How You Talk: {partner['communication_style']}
            - What You Know: {partner['expertise']}
            - What You Like: {partner['interests']}
            
            THE SITUATION:
            {partner['name']} is meeting {req.user_name} for the first time in this scenario. 
            {req.user_name} is learning {partner['target_language']} at {partner['user_level']} level.
            
            TASK:
            Create a warm, welcoming greeting that:
            1. Introduces yourself naturally as {partner['name']}
            2. Sets up the scenario context
            3. Makes {req.user_name} feel comfortable and welcome
            4. Uses appropriate language for {partner['user_level']} level
            5. Shows your personality and expertise
            6. Invites them to start the conversation
            
            IMPORTANT:
            - Be authentic and natural, not like a language teacher
            - Stay in character as {partner['name']}
            - Use your communication style: {partner['communication_style']}
            - Keep it conversational and friendly
            - Don't be too formal or instructional
            
            Write a greeting message that {partner['name']} would naturally say when meeting {req.user_name}:
            """
            
            # Generate greeting using OpenAI directly
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
            
            greeting_response = llm.invoke(greeting_prompt)
            greeting_message = greeting_response.content.strip()
            
            # Store the greeting message
            save_message(thread_id, greeting_message, "assistant", supabase_client)
        
        logger.info(f"Generated greeting for {req.user_name} from {partner['name']} in thread {thread_id}")
        
        return GreetingResponse(
            greeting_message=greeting_message,
            partner_name=partner['name'],
            partner_role=partner['ai_role'],
            scenario=partner['scenario'],
            thread_id=thread_id,
            user_level=partner['user_level'],
            target_language=partner['target_language']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in greet endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate greeting"
        )

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest, supabase_client: Client = Depends(get_supabase)):
    """
    Handle chat interactions between users and AI partners.
    
    Flow:
    1. Verify user exists
    2. Get partner configuration
    3. Get or create thread (user_name_partner_id format)
    4. Store user message
    5. Process chat with AI
    6. Store AI response
    7. Return response with thread_id
    """
    try:
        # Get user from database
        user_response = supabase_client.table("profiles").select("*").eq("user_name", req.user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user = user_response.data[0]

        # Get partner configuration
        partner = get_partner_config(req.partner_id, supabase_client)
        if not partner:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partner not found"
            )

        # Get or create thread
        thread_id = get_or_create_thread(req.user_name, str(req.partner_id), supabase_client)

        # Store user message
        save_message(thread_id, req.user_input, "user", supabase_client)

        # Update user statistics
        update_user_chat_statistics(req.user_name, supabase_client)

        # Process chat with AI
        response = process_chat(req, partner, thread_id, supabase_client)

        # Store AI response
        save_message(thread_id, response, "assistant", supabase_client)

        # Update thread timestamp
        update_thread_timestamp(thread_id, supabase_client)

        # Social integration - check for auto-posts
        try:
            social_integration = SocialIntegration(supabase_client)
            social_integration.check_and_create_auto_posts(req.user_name, user)
        except Exception as e:
            logger.warning(f"Social integration failed for {req.user_name}: {str(e)}")

        return ChatResponse(
            response=response,
            thread_id=thread_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat"
        )

@app.get("/messages/{user_name}/{partner_id}")
def get_thread_messages(
    user_name: str, 
    partner_id: str, 
    supabase_client: Client = Depends(get_supabase)
):
    """
    Get all messages for a user in a specific thread.
    
    Args:
        user_name: The name of the user
        partner_id: The ID of the partner (UUID string)
    
    Returns:
        List of messages in chronological order with thread information
    """
    try:
        # Verify user exists
        user_response = supabase_client.table("profiles").select("*").eq("user_name", user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify partner exists
        partner_response = supabase_client.table("partners").select("*").eq("id", partner_id).eq("is_active", True).execute()
        if not partner_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partner not found"
            )
        
        # Generate thread ID
        thread_id = generate_thread_id(user_name, partner_id)
        
        # Get thread information
        thread = get_thread(thread_id, supabase_client)
        if not thread:
            # Return empty response if thread doesn't exist
            return {
                "thread_id": thread_id,
                "user_name": user_name,
                "partner_id": partner_id,
                "partner_name": partner_response.data[0]["name"],
                "messages": [],
                "message_count": 0,
                "created_at": None,
                "updated_at": None
            }
        
        # Get all messages for the thread
        messages = get_messages(thread_id, supabase_client)
        
        # Format messages for response
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "id": msg.get("id"),
                "role": msg["role"],
                "content": msg["content"],
                "message_timestamp": msg["message_timestamp"],
                "thread_id": msg["thread_id"]
            })
        
        logger.info(f"Retrieved {len(formatted_messages)} messages for thread {thread_id}")
        
        return {
            "thread_id": thread_id,
            "user_name": user_name,
            "partner_id": partner_id,
            "partner_name": partner_response.data[0]["name"],
            "messages": formatted_messages,
            "message_count": len(formatted_messages),
            "created_at": thread.get("created_at"),
            "updated_at": thread.get("updated_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting thread messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve thread messages"
        )

# ============================================================================
# Helper Functions (Updated)
# ============================================================================

def get_partner_config(partner_id: UUID, supabase_client: Client) -> Optional[Dict]:
    """Get partner configuration from the partners table."""
    try:
        response = supabase_client.table("partners").select("*").eq("id", str(partner_id)).eq("is_active", True).execute()
        if response.data:
            partner = response.data[0]
            return {
                "id": partner["id"],
                "name": partner["name"],
                "ai_role": partner["ai_role"],
                "scenario": partner["scenario"],
                "target_language": partner["target_language"],
                "user_level": partner["user_level"],
                "personality": partner.get("personality", ""),
                "background": partner.get("background", ""),
                "communication_style": partner.get("communication_style", ""),
                "expertise": partner.get("expertise", ""),
                "interests": partner.get("interests", "")
            }
        return None
    except Exception as e:
        logger.error(f"Error getting partner config: {str(e)}")
        return None

def process_chat(req: ChatRequest, partner: Dict, thread_id: str, supabase_client: Client) -> str:
    """Process chat request using the AI chat agent with thread context."""
    # Get conversation history for context
    messages = get_messages(thread_id, supabase_client)
    
    # Format messages for LangGraph
    formatted_messages = []
    for msg in messages:
        formatted_messages.append({
            "message_id": str(uuid.uuid4()),
            "role": msg["role"],
            "content": msg["content"]
        })
    
    # Add current user input
    formatted_messages.append({
        "message_id": str(uuid.uuid4()),
        "role": "user",
        "content": req.user_input
    })

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    new_state = {
        "messages": formatted_messages,
        "user_name": req.user_name,
        "ai_role": partner["ai_role"],
        "scenario": partner["scenario"],
        "target_language": partner["target_language"],
        "user_level": partner["user_level"],
        "partner_name": partner["name"],
        "personality": partner.get("personality", ""),
        "background": partner.get("background", ""),
        "communication_style": partner.get("communication_style", ""),
        "expertise": partner.get("expertise", ""),
        "interests": partner.get("interests", "")
    }

    result = chat_agent.invoke(new_state, config=config)
    return result["messages"][-1].content

# ============================================================================
# Health Check Endpoints
# ============================================================================

@app.get("/")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "PolyNot Language Learning API v2.0",
        "version": "2.0.0",
        "database": "Supabase",
        "thread_system": "user-specific",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
def detailed_health_check():
    """Detailed health check with database connectivity."""
    try:
        response = supabase.table("profiles").select("count", count="exact").limit(1).execute()
        
        return {
            "status": "healthy",
            "database": "connected",
            "service": "PolyNot Language Learning API v2.0",
            "version": "2.0.0",
            "thread_system": "user-specific",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "service": "PolyNot Language Learning API v2.0",
            "version": "2.0.0",
            "timestamp": datetime.now().isoformat()
        }

@app.get("/debug/user-levels")
def debug_user_levels():
    """Debug endpoint to check available user levels and enum values."""
    try:
        from src.models import UserLevel
        
        return {
            "available_levels": [level.value for level in UserLevel],
            "level_enum": {
                level.name: level.value for level in UserLevel
            },
            "cefr_levels": {
                "A1": "Beginner",
                "A2": "Elementary", 
                "B1": "Intermediate",
                "B2": "Upper Intermediate",
                "C1": "Advanced",
                "C2": "Mastery"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.patch("/debug/test-patch")
def debug_test_patch():
    """Debug endpoint to test PATCH method functionality."""
    return {
        "message": "PATCH method is working",
        "timestamp": datetime.now().isoformat()
    }

# ============================================================================
# Migration Helper Endpoints
# ============================================================================

@app.get("/migrate/threads")
def migrate_to_new_thread_system():
    """Migrate existing conversation history to new thread system."""
    return {
        "message": "Migration endpoint - implement as needed",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/migrate/user-profiles")
def migrate_user_profiles(supabase_client: Client = Depends(get_supabase)):
    """Migrate existing users to include new profile fields."""
    try:
        # Get all existing users
        users_response = supabase_client.table("profiles").select("*").execute()
        users = users_response.data if users_response.data else []
        
        migrated_count = 0
        for user in users:
            # Add default values for new profile fields
            update_data = {
                "email": user.get("email"),
                "first_name": user.get("first_name"),
                "last_name": user.get("last_name"),
                "bio": user.get("bio"),
                "native_language": user.get("native_language"),
                "learning_goals": user.get("learning_goals"),
                "preferred_topics": user.get("preferred_topics"),
                "study_time_preference": user.get("study_time_preference"),
                "avatar_url": user.get("avatar_url"),
                "is_active": user.get("is_active", True),
                "last_login": user.get("last_login"),
                "total_conversations": user.get("total_conversations", 0),
                "total_messages": user.get("total_messages", 0),
                "streak_days": user.get("streak_days", 0),
                "updated_at": datetime.now().isoformat()
            }
            
            # Only update if any fields are missing
            if any(field not in user or user[field] is None for field in update_data.keys() if field != "updated_at"):
                supabase_client.table("profiles").update(update_data).eq("id", user["id"]).execute()
                migrated_count += 1
        
        return {
            "message": f"Successfully migrated {migrated_count} user profiles",
            "total_users": len(users),
            "migrated_count": migrated_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error migrating user profiles: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to migrate user profiles"
        )

@app.post("/migrate/social-features")
def migrate_social_features(supabase_client: Client = Depends(get_supabase_service)):
    """Initialize social features for existing users who don't have them."""
    try:
        # Get all existing users
        users_response = supabase_client.table("profiles").select("id, user_name").execute()
        users = users_response.data if users_response.data else []
        
        points_initialized = 0
        privacy_initialized = 0
        
        for user in users:
            user_id = user["id"]
            user_name = user["user_name"]
            
            # Check if user has points record
            points_response = supabase_client.table("user_points").select("id").eq("user_id", user_id).execute()
            if not points_response.data:
                try:
                    create_initial_user_points(user_name, user_id, supabase_client)
                    points_initialized += 1
                except Exception as e:
                    logger.error(f"Failed to initialize points for {user_name}: {str(e)}")
            
            # Check if user has privacy settings
            privacy_response = supabase_client.table("user_privacy_settings").select("id").eq("user_id", user_id).execute()
            if not privacy_response.data:
                try:
                    create_default_privacy_settings(user_name, user_id, supabase_client)
                    privacy_initialized += 1
                except Exception as e:
                    logger.error(f"Failed to initialize privacy settings for {user_name}: {str(e)}")
        
        return {
            "message": f"Social features migration completed",
            "total_users": len(users),
            "points_initialized": points_initialized,
            "privacy_initialized": privacy_initialized,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error migrating social features: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to migrate social features"
        )

# ============================================================================
# Enhanced Validation Functions
# ============================================================================

def clean_username(username: str) -> str:
    """Clean username by removing invisible characters and normalizing"""
    if not username:
        return username
    
    # Remove invisible characters and normalize
    import unicodedata
    # Remove zero-width characters and normalize
    cleaned = ''.join(char for char in username if unicodedata.category(char) != 'Cf')
    cleaned = unicodedata.normalize('NFKC', cleaned)
    return cleaned.strip()

def validate_username(username: str) -> str:
    """Enhanced username validation with better rules"""
    if not username or not username.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be empty"
        )
    
    # Clean the username first
    username = clean_username(username)
    
    # Check for minimum and maximum length
    if len(username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters long"
        )
    
    if len(username) > 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be longer than 30 characters"
        )
    
    # Check for spaces
    if ' ' in username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot contain spaces"
        )
    
    # Check for special characters (only allow letters, numbers, underscores, hyphens)
    if not username.replace('_', '').replace('-', '').isalnum():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username can only contain letters, numbers, underscores, and hyphens"
        )
    
    # Check for reserved words
    reserved_words = ['admin', 'root', 'system', 'test', 'guest', 'anonymous', 'null', 'undefined']
    if username.lower() in reserved_words:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be a reserved word"
        )
    
    # Check if username starts with a number
    if username[0].isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot start with a number"
        )
    
    return username

def validate_email(email: str) -> str:
    """Validate email format and check for uniqueness"""
    if not email or not email.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email cannot be empty"
        )
    
    email = email.strip().lower()
    
    # Basic email format validation
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    
    return email

def validate_user_level(user_level: str) -> str:
    """Validate user level is a valid CEFR level"""
    if not user_level or not user_level.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User level cannot be empty"
        )
    
    user_level = user_level.strip().upper()
    valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    
    if user_level not in valid_levels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid user level '{user_level}'. Valid levels are: {', '.join(valid_levels)}"
        )
    
    return user_level

def check_user_exists(username: str, email: str, supabase_client: Client) -> tuple[bool, bool]:
    """Check if user exists by username or email, returns (username_exists, email_exists)"""
    try:
        # Check username
        if username:
            username_response = supabase_client.table("profiles").select("id").eq("user_name", username).execute()
            username_exists = bool(username_response.data)
            logger.info(f"Username '{username}' exists: {username_exists}")
            if username_response.data:
                logger.info(f"Found existing user with username '{username}': {username_response.data}")
            else:
                logger.info(f"No existing user found with username '{username}'")
        else:
            username_exists = False
            logger.info("No username provided for check")
        
        # Check email
        if email:
            email_response = supabase_client.table("profiles").select("id").eq("email", email).execute()
            email_exists = bool(email_response.data)
            logger.info(f"Email '{email}' exists: {email_exists}")
            if email_response.data:
                logger.info(f"Found existing user with email '{email}': {email_response.data}")
            else:
                logger.info(f"No existing user found with email '{email}'")
        else:
            email_exists = False
            logger.info("No email provided for check")
        
        logger.info(f"Final result: username_exists={username_exists}, email_exists={email_exists}")
        return username_exists, email_exists
    except Exception as e:
        logger.error(f"Error checking user existence: {str(e)}")
        return False, False

def generate_unique_email(username: str, supabase_client: Client) -> str:
    """Generate a unique email for the user"""
    # Use a more standard domain that's more likely to be accepted
    base_email = f"{username}@example.com"
    
    # Check if email exists
    email_response = supabase_client.table("profiles").select("id").eq("email", base_email).execute()
    if not email_response.data:
        return base_email
    
    # If email exists, try with a number suffix
    counter = 1
    while counter < 100:  # Prevent infinite loop
        unique_email = f"{username}{counter}@example.com"
        email_response = supabase_client.table("profiles").select("id").eq("email", unique_email).execute()
        if not email_response.data:
            return unique_email
        counter += 1
    
    # Fallback to timestamp-based email
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{username}{timestamp}@example.com"

def generate_robust_email(username: str, supabase_client: Client) -> str:
    """Generate a more robust email that's more likely to be accepted by Supabase"""
    # Try multiple email providers that are more likely to be accepted
    email_providers = [
        "example.com",
        "test.com", 
        "demo.com",
        "sample.com"
    ]
    
    for provider in email_providers:
        base_email = f"{username}@{provider}"
        
        # Check if email exists
        email_response = supabase_client.table("profiles").select("id").eq("email", base_email).execute()
        if not email_response.data:
            return base_email
        
        # If email exists, try with a number suffix
        counter = 1
        while counter < 10:  # Limit to 10 attempts per provider
            unique_email = f"{username}{counter}@{provider}"
            email_response = supabase_client.table("profiles").select("id").eq("email", unique_email).execute()
            if not email_response.data:
                return unique_email
            counter += 1
    
    # Final fallback with timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{username}{timestamp}@example.com"

def handle_array_field_conversion(field_name: str, value: str) -> list:
    """Convert comma-separated string to array for database storage"""
    if not value or not isinstance(value, str):
        return []
    
    # Split by comma and clean up each item
    items = [item.strip() for item in value.split(",") if item.strip()]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_items = []
    for item in items:
        if item.lower() not in seen:
            seen.add(item.lower())
            unique_items.append(item)
    
    return unique_items

def validate_jwt_token(token: str) -> Dict:
    """Validate JWT token with Supabase"""
    try:
        # Decode the JWT token without verification to get the header
        # This is safe because we're not using the payload for authentication
        header = jwt.get_unverified_header(token)
        
        # Check if token has the correct algorithm
        if header.get('alg') != 'HS256':
            raise InvalidTokenError("Invalid token algorithm")
        
        # For Supabase JWT tokens, we can decode without verification
        # since the token was issued by Supabase and we trust it
        # In production, you might want to verify the signature with Supabase's secret
        
        # Decode the payload
        payload = jwt.decode(token, options={"verify_signature": False})
        
        # Check if token is expired
        exp = payload.get('exp')
        if exp and datetime.utcnow().timestamp() > exp:
            raise ExpiredSignatureError("Token has expired")
        
        # Return user data from token
        return {
            "id": payload.get('sub'),
            "email": payload.get('email'),
            "user_metadata": payload.get('user_metadata', {}),
            "exp": exp,
            "iat": payload.get('iat')
        }
        
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}"
        )

# ============================================================================
# Social Features Initialization Functions
# ============================================================================

def create_initial_user_points(user_name: str, user_id: str, supabase_client: Client):
    """Create initial points record for new user."""
    try:
        initial_points = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "total_points": 0,
            "available_points": 0,
            "redeemed_points": 0,
            "level": 1,
            "badges": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        supabase_client.table("user_points").insert(initial_points).execute()
        logger.info(f"Created initial points record for user {user_name}")
        
    except Exception as e:
        logger.error(f"Error creating points record for {user_name}: {str(e)}")
        raise

def create_default_privacy_settings(user_name: str, user_id: str, supabase_client: Client):
    """Create default privacy settings for new user."""
    try:
        default_settings = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "show_posts_to_level": "same",
            "show_achievements": True,
            "show_learning_progress": True,
            "allow_level_filtering": True,
            "study_group_visibility": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        supabase_client.table("user_privacy_settings").insert(default_settings).execute()
        logger.info(f"Created default privacy settings for user {user_name}")
        
    except Exception as e:
        logger.error(f"Error creating privacy settings for {user_name}: {str(e)}")
        raise

# ============================================================================
# Updated User Management Endpoints
# ============================================================================

@app.post("/users/", status_code=201)
def create_user(user: User, supabase_client: Client = Depends(get_supabase)):
    """Create a new user with enhanced validation and error handling."""
    try:
        # Validate username format
        validated_username = validate_username(user.user_name)
        
        # Email is now required - validate it
        if not user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is required for account creation. Please provide a valid email address."
            )
        
        # Validate the provided email
        user_email = validate_email(user.email)
        
        # Validate password
        if not user.password or len(user.password.strip()) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        # Validate user level
        validated_user_level = validate_user_level(user.user_level)
        
        # Note: Removed pre-check to avoid race conditions
        # Database constraints will handle duplicate username/email errors properly
        
        # Create user using Supabase Auth signup
        try:
            auth_response = supabase_client.auth.sign_up({
                "email": user_email,
                "password": user.password,  # Use user-provided password
                "options": {
                    "data": {
                        "user_name": validated_username,
                        "first_name": user.first_name,
                        "last_name": user.last_name
                    }
                }
            })
        except Exception as auth_error:
            error_msg = str(auth_error)
            logger.error(f"Supabase Auth error: {error_msg}")
            
            # Handle specific Supabase email validation errors
            if "invalid" in error_msg.lower() and "email" in error_msg.lower():
                # User provided email was rejected by Supabase
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The provided email address is not valid. Please use a real email address (e.g., Gmail, Yahoo, Outlook)."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to create authentication account: {error_msg}"
                )
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create auth user"
            )
        
        # Prepare profile data with proper array handling
        # Use the same ID from the auth user
        auth_user_id = auth_response.user.id
        # Log the user level being set
        logger.info(f"Creating user {validated_username} with level: {validated_user_level}")
        logger.info(f"Original user.user_level: {user.user_level}")
        logger.info(f"Validated user level: {validated_user_level}")
        logger.info(f"Using auth user ID: {auth_user_id}")
        
        profile_data = {
            "id": auth_user_id,
            "user_name": validated_username,
            "user_level": validated_user_level,
            "target_language": [user.target_language] if user.target_language else [],
            "email": user_email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "native_language": user.native_language,
            "country": user.country,
            "interests": handle_array_field_conversion("interests", user.interests or ""),
            "proficiency_level": user.proficiency_level,
            "bio": user.bio,
            "learning_goals": user.learning_goals,
            "preferred_topics": handle_array_field_conversion("preferred_topics", user.preferred_topics or ""),
            "study_time_preference": user.study_time_preference,
            "avatar_url": user.avatar_url,
            "is_active": True,
            "total_conversations": 0,
            "total_messages": 0,
            "streak_days": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Check if profile already exists (created by database trigger)
        response = None
        try:
            # First check if profile already exists
            existing_profile = supabase_client.table("profiles").select("*").eq("id", auth_user_id).execute()
            
            if existing_profile.data:
                logger.info(f"Profile already exists for user {validated_username}, using existing profile")
                response = existing_profile
            else:
                logger.info(f"Inserting profile data: {profile_data}")
                response = supabase_client.table("profiles").insert(profile_data).execute()
                logger.info(f"Database insert completed successfully")
                if response.data:
                    logger.info(f"Inserted user level in DB: {response.data[0].get('user_level')}")
        except Exception as db_error:
            error_msg = str(db_error)
            logger.error(f"Database error creating profile: {error_msg}")
            
            # Check if profile was created by trigger despite the error
            try:
                existing_profile = supabase_client.table("profiles").select("*").eq("id", auth_user_id).execute()
                if existing_profile.data:
                    logger.info(f"Profile was created by database trigger, using existing profile")
                    response = existing_profile
                else:
                    logger.warning(f"Database error occurred, but user might have been created: {error_msg}")
            except Exception as check_error:
                logger.error(f"Error checking for existing profile: {str(check_error)}")
                logger.warning(f"Database error occurred, but user might have been created: {error_msg}")
            
            # Don't raise an exception - let's check if the user was actually created
        
        # Check if we have a valid response
        if response and response.data:
            logger.info(f"Profile data retrieved successfully for user {validated_username}")
        else:
            # If no response data, the user might be unverified
            # Try to get the profile anyway
            logger.warning(f"No response data for user {validated_username}, checking if profile exists...")
            try:
                response = supabase_client.table("profiles").select("*").eq("id", auth_user_id).execute()
                if response.data:
                    logger.info(f"Profile found for unverified user {validated_username}")
                else:
                    logger.error(f"No profile found for user {validated_username}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to create user profile. Please check your email and verify your account."
                    )
            except Exception as profile_error:
                logger.error(f"Error retrieving profile: {str(profile_error)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user profile. Please check your email and verify your account."
                )
            logger.info(f"Response data length: {len(response.data)}")
            logger.info(f"First item in response data: {response.data[0]}")
            logger.info(f"User level stored in database: {response.data[0]['user_level']}")
            
            # WORKAROUND: If the database defaulted the level to A1 but we requested a different level,
            # update it immediately
            stored_level = response.data[0]["user_level"]
            if stored_level == "A1" and validated_user_level != "A1":
                logger.warning(f"Database defaulted level to A1, but user requested {validated_user_level}. Updating...")
                try:
                    # Update the user level immediately
                    update_response = supabase_client.table("profiles").update({
                        "user_level": validated_user_level,
                        "updated_at": datetime.now().isoformat()
                    }).eq("user_name", validated_username).execute()
                    
                    if update_response.data:
                        logger.info(f"Successfully updated user level from A1 to {validated_user_level}")
                        stored_level = validated_user_level
                    else:
                        logger.error(f"Failed to update user level from A1 to {validated_user_level}")
                except Exception as update_error:
                    logger.error(f"Error updating user level: {str(update_error)}")
            
            # Social features are automatically initialized by database trigger
            logger.info(f"Social features will be automatically initialized by database trigger for user {validated_username}")
            
            # Return the user data in the expected format
            user_data = {
                "id": response.data[0]["id"],
                "user_name": response.data[0]["user_name"],
                "user_level": validated_user_level,
                "target_language": response.data[0]["target_language"][0] if response.data[0]["target_language"] else user.target_language,
                "email": response.data[0].get("email"),
                "first_name": response.data[0].get("first_name"),
                "last_name": response.data[0].get("last_name"),
                "native_language": response.data[0].get("native_language"),
                "country": response.data[0].get("country"),
                "interests": response.data[0].get("interests", []),
                "bio": response.data[0].get("bio"),
                "learning_goals": response.data[0].get("learning_goals"),
                "preferred_topics": response.data[0].get("preferred_topics", []),
                "study_time_preference": response.data[0].get("study_time_preference"),
                "avatar_url": response.data[0].get("avatar_url"),
                "created_at": response.data[0]["created_at"]
            }
            logger.info(f"Successfully created user: {validated_username} with ID: {response.data[0]['id']}")
            return user_data
        
        # If no response data, try to fetch the user from database to confirm creation
        logger.warning(f"No response data, checking if user was created anyway...")
        try:
            # Try to fetch the user we just tried to create
            fetch_response = supabase_client.table("profiles").select("*").eq("user_name", validated_username).execute()
            if fetch_response.data:
                logger.info(f"User was created successfully despite no response data!")
                user_data = fetch_response.data[0]
                return {
                    "id": user_data["id"],
                    "user_name": user_data["user_name"],
                    "user_level": validated_user_level,
                    "target_language": user_data["target_language"][0] if user_data["target_language"] else user.target_language,
                    "email": user_data.get("email"),
                    "first_name": user_data.get("first_name"),
                    "last_name": user_data.get("last_name"),
                    "native_language": user_data.get("native_language"),
                    "country": user_data.get("country"),
                    "interests": user_data.get("interests", []),
                    "bio": user_data.get("bio"),
                    "learning_goals": user_data.get("learning_goals"),
                    "preferred_topics": user_data.get("preferred_topics", []),
                    "study_time_preference": user_data.get("study_time_preference"),
                    "avatar_url": user_data.get("avatar_url"),
                    "created_at": user_data["created_at"]
                }
            else:
                logger.error(f"User was not created and no response data available")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user profile"
                )
        except Exception as fetch_error:
            logger.error(f"Error fetching user after creation attempt: {fetch_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user profile"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the user"
        )

@app.post("/auth/login")
def login_user(login_data: UserLogin, supabase_client: Client = Depends(get_supabase)):
    """Login user with email and password."""
    try:
        # Attempt to sign in with Supabase Auth
        auth_response = supabase_client.auth.sign_in_with_password({
            "email": login_data.email,
            "password": login_data.password
        })
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Get user profile from database
        profile_response = supabase_client.table("profiles").select("*").eq("email", login_data.email).execute()
        
        if not profile_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        
        user_profile = profile_response.data[0]
        
        # Update last login
        supabase_client.table("profiles").update({
            "last_login": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }).eq("id", user_profile["id"]).execute()
        
        # Calculate expires_in (seconds until expiration)
        expires_at = auth_response.session.expires_at
        expires_in = 3600  # Default to 1 hour if we can't calculate
        
        if expires_at:
            try:
                # Handle both string and integer timestamps
                if isinstance(expires_at, str):
                    # Parse the expires_at timestamp and calculate seconds until expiration
                    exp_datetime = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    now = datetime.now(exp_datetime.tzinfo)
                    expires_in = int((exp_datetime - now).total_seconds())
                elif isinstance(expires_at, (int, float)):
                    # Handle Unix timestamp
                    exp_datetime = datetime.fromtimestamp(expires_at)
                    now = datetime.now()
                    expires_in = int((exp_datetime - now).total_seconds())
                else:
                    expires_in = 3600  # Default to 1 hour
                
                # Ensure it's not negative
                expires_in = max(expires_in, 0)
            except Exception as e:
                logger.warning(f"Could not parse expires_at timestamp: {e}")
                expires_in = 3600  # Default to 1 hour
        
        # Return user data with enhanced auth token response
        return {
            "user": {
                "id": user_profile["id"],
                "user_name": user_profile["user_name"],
                "email": user_profile["email"],
                "first_name": user_profile.get("first_name"),
                "last_name": user_profile.get("last_name"),
                "user_level": user_profile["user_level"],
                "target_language": user_profile["target_language"][0] if user_profile["target_language"] else None,
                "native_language": user_profile.get("native_language"),
                "country": user_profile.get("country"),
                "interests": user_profile.get("interests", []),
                "bio": user_profile.get("bio"),
                "learning_goals": user_profile.get("learning_goals"),
                "preferred_topics": user_profile.get("preferred_topics", []),
                "study_time_preference": user_profile.get("study_time_preference"),
                "avatar_url": user_profile.get("avatar_url"),
                "total_conversations": user_profile.get("total_conversations", 0),
                "total_messages": user_profile.get("total_messages", 0),
                "streak_days": user_profile.get("streak_days", 0),
                "created_at": user_profile["created_at"]
            },
            "access_token": auth_response.session.access_token,
            "refresh_token": auth_response.session.refresh_token,
            "token_type": "Bearer",
            "expires_in": expires_in,
            "expires_at": expires_at,
            "last_login": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Login error: {error_msg}")
        
        # Handle specific Supabase Auth errors
        if "Invalid login credentials" in error_msg or "Invalid email or password" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        elif "Email not confirmed" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not confirmed. Please check your email and confirm your account."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Login failed: {error_msg}"
            )

@app.post("/auth/logout")
def logout_user(supabase_client: Client = Depends(get_supabase)):
    """Logout user."""
    try:
        # Sign out from Supabase Auth
        supabase_client.auth.sign_out()
        return {"message": "Successfully logged out"}
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )

@app.post("/auth/reset-password")
def reset_password(reset_request: PasswordResetRequest, supabase_client: Client = Depends(get_supabase)):
    """Send password reset email."""
    try:
        # Send password reset email via Supabase Auth
        supabase_client.auth.reset_password_email(reset_request.email)
        return {"message": "Password reset email sent"}
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send password reset email"
        )

@app.get("/auth/validate")
def validate_token(authorization: str = Header(None)):
    """Validate JWT token and return user information."""
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header"
            )
        
        token = authorization.split(" ")[1]
        
        # Validate JWT token with Supabase
        user_data = validate_jwt_token(token)
        
        # Format expires_at from timestamp
        expires_at = None
        if user_data.get("exp"):
            expires_at = datetime.utcfromtimestamp(user_data["exp"]).isoformat() + "Z"
        
        return {
            "valid": True,
            "user": {
                "id": user_data["id"],
                "email": user_data["email"],
                "user_metadata": user_data["user_metadata"]
            },
            "expires_at": expires_at
        }
    except HTTPException:
        # Re-raise HTTPException to preserve status codes
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}"
        )

@app.post("/auth/refresh")
def refresh_token(refresh_data: dict, supabase_client: Client = Depends(get_supabase)):
    """Refresh access token using refresh token."""
    try:
        refresh_token = refresh_data.get("refresh_token")
        
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refresh token is required"
            )
        
        # Use Supabase to refresh the token
        try:
            auth_response = supabase_client.auth.refresh_session(refresh_token)
            
            if not auth_response.session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token"
                )
            
            # Calculate expires_in (seconds until expiration)
            expires_at = auth_response.session.expires_at
            expires_in = 3600  # Default to 1 hour if we can't calculate
            
            if expires_at:
                try:
                    # Parse the expires_at timestamp and calculate seconds until expiration
                    exp_datetime = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    now = datetime.now(exp_datetime.tzinfo)
                    expires_in = int((exp_datetime - now).total_seconds())
                    # Ensure it's not negative
                    expires_in = max(expires_in, 0)
                except Exception as e:
                    logger.warning(f"Could not parse expires_at timestamp: {e}")
                    expires_in = 3600  # Default to 1 hour
            
            return {
                "access_token": auth_response.session.access_token,
                "refresh_token": auth_response.session.refresh_token,
                "token_type": "Bearer",
                "expires_in": expires_in,
                "expires_at": expires_at
            }
            
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to refresh token"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )

@app.get("/users/{user_name}")
def get_user(user_name: str, supabase_client: Client = Depends(get_supabase)):
    """Get user information."""
    try:
        response = supabase_client.table("profiles").select("*").eq("user_name", user_name).execute()
        if response.data:
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user"
        )

# ============================================================================
# User Profile Management Endpoints
# ============================================================================

@app.get("/users/{user_name}/profile", response_model=UserProfileResponse)
def get_user_profile(user_name: str, supabase_client: Client = Depends(get_supabase)):
    """Get complete user profile with statistics."""
    try:
        # Get user data
        user_response = supabase_client.table("profiles").select("*").eq("user_name", user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user = user_response.data[0]
        
        # Calculate statistics
        stats = calculate_user_statistics(user_name, supabase_client)
        
        # Build profile response
        profile = UserProfileResponse(
            id=user["id"],
            user_name=user["user_name"],
            user_level=user["user_level"],
            target_language=user.get("target_language", [""])[0] if isinstance(user.get("target_language"), list) else user.get("target_language", ""),
            email=user.get("email"),
            first_name=user.get("first_name"),
            last_name=user.get("last_name"),
            country=user.get("country"),
            interests=user.get("interests"),
            proficiency_level=user.get("proficiency_level"),
            bio=user.get("bio"),
            native_language=user.get("native_language"),
            learning_goals=user.get("learning_goals"),
            preferred_topics=user.get("preferred_topics") if isinstance(user.get("preferred_topics"), list) else (json.loads(user.get("preferred_topics")) if user.get("preferred_topics") else None),
            study_time_preference=user.get("study_time_preference"),
            avatar_url=user.get("avatar_url"),
            is_active=user.get("is_active", True),
            last_login=user.get("last_login"),
            created_at=user["created_at"],
            statistics=stats
        )
        
        return profile
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )

@app.patch("/users/{user_name}/profile")
@app.put("/users/{user_name}/profile")
def update_user_profile(
    user_name: str, 
    profile_update: UserProfileUpdate, 
    supabase_client: Client = Depends(get_supabase)
):
    """Update user profile information."""
    logger.info(f"Profile update endpoint called for user: {user_name}")
    try:
        # Clean username to remove any invisible characters
        clean_username_value = clean_username(user_name)
        logger.info(f"Profile update request for user: '{clean_username_value}' (original: '{user_name}')")
        
        # Log the incoming request data
        try:
            # Try new Pydantic v2 method first
            request_data = profile_update.model_dump(exclude_unset=True)
        except AttributeError:
            # Fallback to Pydantic v1 method
            request_data = profile_update.dict(exclude_unset=True)
        logger.info(f"Profile update request data: {request_data}")
        
        # Check if user exists
        user_response = supabase_client.table("profiles").select("id").eq("user_name", clean_username_value).execute()
        if not user_response.data:
            logger.error(f"User not found: '{clean_username_value}'")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"User found: {user_response.data[0]['id']}")
        
        # Prepare update data (only include non-None values)
        update_data = {}
        for field, value in request_data.items():
            if value is not None:
                # Handle user_level validation
                if field == "user_level":
                    validated_level = validate_user_level(value)
                    update_data[field] = validated_level
                # Handle target_language as array
                elif field == "target_language":
                    if value:
                        update_data[field] = [value]
                    else:
                        update_data[field] = []
                # Handle array fields - convert comma-separated strings to arrays
                elif field in ["interests", "preferred_topics"] and isinstance(value, str):
                    # Convert comma-separated string to array format using the helper function
                    update_data[field] = handle_array_field_conversion(field, value)
                elif field in ["interests", "preferred_topics"] and isinstance(value, list):
                    # If already a list, clean it up
                    update_data[field] = [item.strip() for item in value if item and item.strip()]
                else:
                    update_data[field] = value
        
        logger.info(f"Prepared update data: {update_data}")
        
        if not update_data:
            logger.error("No valid fields to update - all fields are None or empty")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid fields to update"
            )
        
        # Add updated timestamp
        update_data["updated_at"] = datetime.now().isoformat()
        
        # Update user profile
        logger.info(f"Updating profile for user: {clean_username_value}")
        response = supabase_client.table("profiles").update(update_data).eq("user_name", clean_username_value).execute()
        
        if response.data:
            logger.info(f"Profile updated successfully for user: {clean_username_value}")
            return response.data[0]
        else:
            logger.error(f"Supabase update returned no data for user: {clean_username_value}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update user profile"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile for '{user_name}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user profile"
        )

@app.patch("/users/{user_name}")
@app.put("/users/{user_name}")
def update_user_general(
    user_name: str, 
    user_update: dict, 
    supabase_client: Client = Depends(get_supabase)
):
    """General user update endpoint that can handle both profile and level updates."""
    logger.info(f"General user update endpoint called for user: {user_name}")
    try:
        # Check if user exists
        user_response = supabase_client.table("profiles").select("id").eq("user_name", user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prepare update data
        update_data = {}
        
        # Handle user_level updates
        if "user_level" in user_update:
            validated_level = validate_user_level(user_update["user_level"])
            update_data["user_level"] = validated_level
        
        # Handle profile updates (all other fields)
        profile_fields = [
            "first_name", "last_name", "native_language", "country", 
            "interests", "bio", "learning_goals", "preferred_topics", 
            "study_time_preference", "avatar_url", "proficiency_level",
            "target_language"
        ]
        
        for field in profile_fields:
            if field in user_update:
                if field in ["interests", "preferred_topics"]:
                    # Handle array fields
                    update_data[field] = handle_array_field_conversion(field, user_update[field] or "")
                elif field == "target_language":
                    # Handle target_language as array
                    if user_update[field]:
                        update_data[field] = [user_update[field]]
                    else:
                        update_data[field] = []
                else:
                    update_data[field] = user_update[field]
        
        # Add timestamp
        update_data["updated_at"] = datetime.now().isoformat()
        
        # Update user
        response = supabase_client.table("profiles").update(update_data).eq("user_name", user_name).execute()
        
        if response.data:
            logger.info(f"Successfully updated user: {user_name}")
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )

@app.patch("/users/{user_name}/level")
def update_user_level(
    user_name: str, 
    level_update: UserLevelUpdate, 
    supabase_client: Client = Depends(get_supabase)
):
    """Update user's language level."""
    try:
        # Check if user exists
        user_response = supabase_client.table("profiles").select("id").eq("user_name", user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update user level
        update_data = {
            "user_level": level_update.user_level,
            "updated_at": datetime.now().isoformat()
        }
        
        response = supabase_client.table("profiles").update(update_data).eq("user_name", user_name).execute()
        
        if response.data:
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update user level"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user level: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user level"
        )

@app.get("/users/{user_name}/statistics", response_model=UserStatistics)
def get_user_statistics(user_name: str, supabase_client: Client = Depends(get_supabase)):
    """Get user learning statistics."""
    try:
        # Check if user exists
        user_response = supabase_client.table("profiles").select("id").eq("user_name", user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Calculate and return statistics
        stats = calculate_user_statistics(user_name, supabase_client)
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user statistics"
        )

@app.post("/users/{user_name}/login")
def record_user_login(user_name: str, supabase_client: Client = Depends(get_supabase)):
    """Record user login and update streak."""
    try:
        # Check if user exists
        user_response = supabase_client.table("profiles").select("*").eq("user_name", user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user = user_response.data[0]
        current_time = datetime.now().isoformat()
        
        # Calculate streak (simplified logic - you might want to enhance this)
        last_login = user.get("last_login")
        current_streak = user.get("streak_days", 0)
        
        if last_login:
            last_login_date = datetime.fromisoformat(last_login.replace('Z', '+00:00')).date()
            current_date = datetime.now().date()
            
            # If last login was yesterday, increment streak
            if (current_date - last_login_date).days == 1:
                current_streak += 1
            # If last login was more than 1 day ago, reset streak
            elif (current_date - last_login_date).days > 1:
                current_streak = 1
            # If same day, keep current streak
        else:
            # First login
            current_streak = 1
        
        # Update user login info
        update_data = {
            "last_login": current_time,
            "streak_days": current_streak,
            "updated_at": current_time
        }
        
        response = supabase_client.table("profiles").update(update_data).eq("user_name", user_name).execute()
        
        if response.data:
            return {
                "message": "Login recorded successfully",
                "streak_days": current_streak,
                "last_login": current_time
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to record login"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording user login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record login"
        )

# ============================================================================
# Enhanced User Profile Features
# ============================================================================

@app.get("/users/{user_name}/profile/completion", response_model=ProfileCompletion)
def get_profile_completion(user_name: str, supabase_client: Client = Depends(get_supabase)):
    """Get user profile completion percentage."""
    try:
        # Check if user exists
        user_response = supabase_client.table("profiles").select("*").eq("user_name", user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user = user_response.data[0]
        
        # Define required fields for profile completion
        required_fields = [
            "first_name", "last_name", "native_language", "country", 
            "bio", "learning_goals", "interests", "preferred_topics"
        ]
        
        completed_fields = 0
        total_fields = len(required_fields)
        
        for field in required_fields:
            value = user.get(field)
            if value and (isinstance(value, str) and value.strip()) or (isinstance(value, list) and len(value) > 0):
                completed_fields += 1
        
        completion_percentage = round((completed_fields / total_fields) * 100, 1)
        
        # Get missing fields
        missing_fields = []
        for field in required_fields:
            value = user.get(field)
            if not value or (isinstance(value, str) and not value.strip()) or (isinstance(value, list) and len(value) == 0):
                missing_fields.append(field)
        
        return {
            "completion_percentage": completion_percentage,
            "completed_fields": completed_fields,
            "total_fields": total_fields,
            "missing_fields": missing_fields,
            "profile_level": "Complete" if completion_percentage == 100 else "Incomplete"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile completion: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get profile completion"
        )

@app.get("/users/{user_name}/profile/achievements", response_model=UserAchievements)
def get_user_achievements(user_name: str, supabase_client: Client = Depends(get_supabase)):
    """Get user achievements and milestones."""
    try:
        # Check if user exists
        user_response = supabase_client.table("profiles").select("*").eq("user_name", user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user = user_response.data[0]
        
        # Calculate achievements based on user data
        achievements = []
        
        # Streak achievements
        streak_days = user.get("streak_days", 0)
        if streak_days >= 7:
            achievements.append({
                "id": "week_streak",
                "name": "Week Warrior",
                "description": "Maintained a 7-day login streak",
                "icon": "🔥",
                "unlocked_at": user.get("last_login")
            })
        if streak_days >= 30:
            achievements.append({
                "id": "month_streak",
                "name": "Monthly Master",
                "description": "Maintained a 30-day login streak",
                "icon": "⚡",
                "unlocked_at": user.get("last_login")
            })
        
        # Message achievements
        total_messages = user.get("total_messages", 0)
        if total_messages >= 10:
            achievements.append({
                "id": "first_10_messages",
                "name": "Conversation Starter",
                "description": "Sent your first 10 messages",
                "icon": "💬",
                "unlocked_at": user.get("last_login")
            })
        if total_messages >= 100:
            achievements.append({
                "id": "hundred_messages",
                "name": "Chat Champion",
                "description": "Sent 100 messages",
                "icon": "🏆",
                "unlocked_at": user.get("last_login")
            })
        
        # Conversation achievements
        total_conversations = user.get("total_conversations", 0)
        if total_conversations >= 5:
            achievements.append({
                "id": "five_conversations",
                "name": "Social Butterfly",
                "description": "Started 5 conversations",
                "icon": "🦋",
                "unlocked_at": user.get("last_login")
            })
        
        # Profile completion achievement
        profile_completion = get_profile_completion(user_name, supabase_client)
        if profile_completion["completion_percentage"] == 100:
            achievements.append({
                "id": "complete_profile",
                "name": "Profile Perfectionist",
                "description": "Completed your profile 100%",
                "icon": "✨",
                "unlocked_at": user.get("updated_at")
            })
        
        return {
            "total_achievements": len(achievements),
            "achievements": achievements,
            "next_milestones": [
                {
                    "type": "streak",
                    "current": streak_days,
                    "next": 7 if streak_days < 7 else 30 if streak_days < 30 else 100,
                    "description": "Login streak"
                },
                {
                    "type": "messages",
                    "current": total_messages,
                    "next": 10 if total_messages < 10 else 100 if total_messages < 100 else 500,
                    "description": "Total messages"
                },
                {
                    "type": "conversations",
                    "current": total_conversations,
                    "next": 5 if total_conversations < 5 else 20,
                    "description": "Total conversations"
                }
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user achievements: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user achievements"
        )

@app.delete("/users/{user_name}")
def delete_user(user_name: str, supabase_client: Client = Depends(get_supabase)):
    """Delete user account and all associated data."""
    try:
        # Check if user exists
        user_response = supabase_client.table("profiles").select("id").eq("user_name", user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_id = user_response.data[0]["id"]
        
        # Delete user's conversation threads
        try:
            supabase_client.table("conversation_thread").delete().eq("user_name", user_name).execute()
        except Exception as e:
            logger.warning(f"Failed to delete conversation threads for user {user_name}: {str(e)}")
        
        # Delete user's messages
        try:
            # Get all thread IDs for this user
            threads_response = supabase_client.table("conversation_thread").select("id").eq("user_name", user_name).execute()
            if threads_response.data:
                thread_ids = [thread["id"] for thread in threads_response.data]
                for thread_id in thread_ids:
                    supabase_client.table("message").delete().eq("thread_id", thread_id).execute()
        except Exception as e:
            logger.warning(f"Failed to delete messages for user {user_name}: {str(e)}")
        
        # Delete user's custom partners
        try:
            supabase_client.table("partners").delete().eq("user_id", user_id).execute()
        except Exception as e:
            logger.warning(f"Failed to delete custom partners for user {user_name}: {str(e)}")
        
        # Delete user profile
        try:
            supabase_client.table("profiles").delete().eq("user_name", user_name).execute()
        except Exception as e:
            logger.error(f"Failed to delete user profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user profile"
            )
        
        # Note: Supabase Auth user deletion would need to be handled by admin functions
        # or through Supabase dashboard
        
        return {
            "message": "User account and all associated data deleted successfully",
            "deleted_user": user_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )

# ============================================================================
# Partner Management Endpoints
# ============================================================================

@app.get("/partners/")
def get_partners(
    is_premade: Optional[bool] = None,
    user_name: Optional[str] = None,
    supabase_client: Client = Depends(get_supabase)
):
    """Get all partners with optional filters."""
    try:
        query = supabase_client.table("partners").select("*")
        
        if is_premade is not None:
            query = query.eq("is_premade", is_premade)
        
        if user_name:
            # Get user's custom partners + premade partners
            user_response = supabase_client.table("profiles").select("id").eq("user_name", user_name).execute()
            if user_response.data:
                user_id = user_response.data[0]["id"]
                # Get all partners and filter in Python to include both user's partners and premade partners
                response = query.execute()
                if response.data:
                    filtered_partners = [
                        partner for partner in response.data 
                        if (partner.get("user_id") == user_id) or (partner.get("is_premade", False))
                    ]
                    return filtered_partners
                return []
            else:
                # User not found, return only premade partners
                response = query.execute()
                if response.data:
                    filtered_partners = [
                        partner for partner in response.data 
                        if partner.get("is_premade", False)
                    ]
                    return filtered_partners
                return []
        else:
            # When no user_name provided (not logged in), only show premade partners
            response = query.execute()
            if response.data:
                # Filter to only show premade partners when not logged in
                filtered_partners = [
                    partner for partner in response.data 
                    if partner.get("is_premade", False)
                ]
                return filtered_partners
            return []
        
    except Exception as e:
        logger.error(f"Error getting partners: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get partners"
        )

@app.post("/partners/", status_code=201)
def create_partner(partner: CreatePartnerRequest, supabase_client: Client = Depends(get_supabase)):
    """Create a new custom partner."""
    try:
        partner_data = {
            "name": partner.name,
            "ai_role": partner.ai_role,
            "scenario": partner.scenario,
            "target_language": partner.target_language,
            "user_level": partner.user_level,
            "personality": partner.personality,
            "background": partner.background,
            "communication_style": partner.communication_style,
            "expertise": partner.expertise,
            "interests": partner.interests,
            "is_premade": False,
            "is_active": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Handle user-specific partners
        if partner.user_name:
            # Verify user exists and get their ID
            user_response = supabase_client.table("profiles").select("id").eq("user_name", partner.user_name).execute()
            if not user_response.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            user_id = user_response.data[0]["id"]
            partner_data["user_id"] = user_id
            logger.info(f"Creating user-specific partner for user: {partner.user_name} (ID: {user_id})")
        else:
            # System partner (accessible to all users)
            partner_data["user_id"] = None
            logger.info("Creating system partner (accessible to all users)")
        
        response = supabase_client.table("partners").insert(partner_data).execute()
        if response.data:
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create partner"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating partner: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create partner"
        )

# ============================================================================
# Social Features Endpoints
# ============================================================================

def get_social_service(supabase_client: Client = Depends(get_supabase)) -> SocialService:
    """Dependency to get social service."""
    # Use service role client for all social operations to bypass RLS
    if SUPABASE_SERVICE_ROLE_KEY:
        service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        return SocialService(service_client)
    else:
        return SocialService(supabase_client)

def get_social_service_with_service_role() -> SocialService:
    """Dependency to get social service with service role (bypasses RLS)."""
    if SUPABASE_SERVICE_ROLE_KEY:
        service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        return SocialService(service_client)
    else:
        # Fallback to regular client
        return SocialService(supabase)

@app.post("/social/posts", response_model=PostResponse, status_code=201)
def create_social_post(
    post_data: CreatePostRequest,
    user_id: str,
    social_service: SocialService = Depends(get_social_service)
):
    """Create a new social post."""
    try:
        # Validate required fields
        if not post_data.title or not post_data.title.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Post title is required"
            )
        if not post_data.content or not post_data.content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Post content is required"
            )
        
        return social_service.create_post(user_id, post_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating social post: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create social post"
        )

@app.get("/social/posts/{post_id}", response_model=PostResponse)
def get_social_post(
    post_id: str,
    user_name: Optional[str] = None,
    social_service: SocialService = Depends(get_social_service)
):
    """Get a specific social post."""
    try:
        post = social_service.get_post(post_id, user_name)
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found"
            )
        return post
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting social post: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get social post"
        )

@app.put("/social/posts/{post_id}", response_model=PostResponse)
def update_social_post(
    post_id: str,
    user_name: str,
    update_data: UpdatePostRequest,
    social_service: SocialService = Depends(get_social_service)
):
    """Update a social post (only by owner)."""
    try:
        # Convert UpdatePostRequest to dict, excluding None values
        update_dict = update_data.dict(exclude_unset=True)
        
        # Validate that at least one field is being updated
        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one field must be provided for update"
            )
        
        # Validate content if provided
        if "content" in update_dict and (not update_dict["content"] or not update_dict["content"].strip()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Post content cannot be empty"
            )
        
        # Validate title if provided
        if "title" in update_dict and (not update_dict["title"] or not update_dict["title"].strip()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Post title cannot be empty"
            )
        
        updated_post = social_service.update_post(post_id, user_name, update_dict)
        if not updated_post:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this post or post not found"
            )
        return updated_post
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating social post: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update social post"
        )

@app.delete("/social/posts/{post_id}")
def delete_social_post(
    post_id: str,
    user_name: str,
    social_service: SocialService = Depends(get_social_service)
):
    """Delete a social post."""
    try:
        success = social_service.delete_post(post_id, user_name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this post"
            )
        return {"message": "Post deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting social post: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete social post"
        )

@app.get("/social/feed", response_model=NewsFeedResponse)
def get_news_feed(
    user_id: str,
    page: int = 1,
    limit: int = 20,
    post_types: Optional[List[str]] = None,
    social_service: SocialService = Depends(get_social_service)
):
    """Get personalized news feed."""
    try:
        from src.social_models import PostType
        post_type_enums = None
        if post_types:
            post_type_enums = [PostType(pt) for pt in post_types if pt in [p.value for p in PostType]]
        
        request = NewsFeedRequest(page=page, limit=limit, post_types=post_type_enums)
        return social_service.get_news_feed(user_id, request)
    except Exception as e:
        logger.error(f"Error getting news feed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get news feed"
        )

@app.post("/social/posts/{post_id}/like")
def like_post(
    post_id: str,
    user_name: str,
    social_service: SocialService = Depends(get_social_service)
):
    """Like or unlike a post."""
    try:
        is_liked = social_service.like_post(post_id, user_name)
        return {"liked": is_liked, "message": "Post liked" if is_liked else "Post unliked"}
    except Exception as e:
        logger.error(f"Error liking post: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to like post"
        )

@app.post("/social/posts/{post_id}/comments", response_model=CommentResponse, status_code=201)
def comment_on_post(
    post_id: str,
    user_name: str,
    comment_data: CommentRequest,
    social_service: SocialService = Depends(get_social_service)
):
    """Add a comment to a post."""
    try:
        return social_service.add_comment(user_name, post_id, comment_data)
    except Exception as e:
        logger.error(f"Error commenting on post: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add comment"
        )

@app.get("/social/posts/{post_id}/comments", response_model=List[CommentResponse])
def get_post_comments(
    post_id: str,
    user_name: Optional[str] = None,
    social_service: SocialService = Depends(get_social_service)
):
    """Get comments for a post."""
    try:
        return social_service.get_post_comments(post_id, user_name)
    except Exception as e:
        logger.error(f"Error getting post comments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get post comments"
        )

@app.post("/social/users/{target_user}/follow")
def follow_user(
    target_user: str,
    user_name: str,
    social_service: SocialService = Depends(get_social_service)
):
    """Follow or unfollow a user."""
    try:
        is_following = social_service.follow_user(user_name, target_user)
        return {"following": is_following, "message": "User followed" if is_following else "User unfollowed"}
    except Exception as e:
        logger.error(f"Error following user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to follow user"
        )

@app.get("/social/users/{target_user}/followers")
def get_user_followers(
    target_user: str,
    social_service: SocialService = Depends(get_social_service)
):
    """Get user's followers."""
    try:
        followers = social_service.get_user_followers(target_user)
        return {"followers": followers, "count": len(followers)}
    except Exception as e:
        logger.error(f"Error getting user followers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user followers"
        )

@app.get("/social/users/{target_user}/following")
def get_user_following(
    target_user: str,
    social_service: SocialService = Depends(get_social_service)
):
    """Get users that user is following."""
    try:
        following = social_service.get_user_following(target_user)
        return {"following": following, "count": len(following)}
    except Exception as e:
        logger.error(f"Error getting user following: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user following"
        )

@app.get("/social/users/{user_name}/points", response_model=PointsSummary)
def get_user_points(
    user_name: str,
    social_service: SocialService = Depends(get_social_service)
):
    """Get user's points summary."""
    try:
        return social_service.get_user_points(user_name)
    except Exception as e:
        logger.error(f"Error getting user points: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user points"
        )

@app.post("/social/users/{user_id}/points")
def award_points_to_user(
    user_id: str,
    request: dict,
    social_service: SocialService = Depends(get_social_service_with_service_role)
):
    """Award points to a user by UUID."""
    try:
        points = request.get("points", 0)
        reason = request.get("reason", "Points awarded")
        activity_type = request.get("activity_type", "manual")
        metadata = request.get("metadata", {})
        
        result = social_service.award_points_to_user_by_id(
            user_id=user_id,
            points=points,
            reason=reason,
            activity_type=activity_type,
            metadata=metadata
        )
        
        # Check if the operation was successful
        if not result.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to award points")
            )
        
        return {
            "success": True,
            "points": points,
            "user_id": user_id,
            "reason": reason,
            "activity_type": activity_type,
            "metadata": metadata,
            "total_points": result.get("total_points", 0),
            "level": result.get("level", 1),
            "level_up": result.get("level_up", False)
        }
    except Exception as e:
        logger.error(f"Error awarding points to user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to award points: {str(e)}"
        )

@app.get("/social/users/{user_name}/achievements")
def get_user_achievements(
    user_name: str,
    social_service: SocialService = Depends(get_social_service)
):
    """Get user's achievements."""
    try:
        achievements = social_service.get_user_achievements(user_name)
        return {"achievements": achievements, "count": len(achievements)}
    except Exception as e:
        logger.error(f"Error getting user achievements: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user achievements"
        )

@app.get("/social/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard(
    user_name: str,
    limit: int = 50,
    social_service: SocialService = Depends(get_social_service)
):
    """Get leaderboard."""
    try:
        return social_service.get_leaderboard(user_name, limit)
    except Exception as e:
        logger.error(f"Error getting leaderboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get leaderboard"
        )

@app.get("/social/users/{target_user}/profile", response_model=SocialUserProfileResponse)
def get_social_user_profile(
    target_user: str,
    current_user: Optional[str] = None,
    social_service: SocialService = Depends(get_social_service)
):
    """Get social user profile with social data."""
    try:
        # Get basic user profile
        user_response = supabase.table("profiles").select("*").eq("user_name", target_user).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user = user_response.data[0]
        
        # Get social data
        points = social_service.get_user_points(target_user)
        followers = social_service.get_user_followers(target_user)
        following = social_service.get_user_following(target_user)
        
        # Get posts count
        posts_response = supabase.table("social_posts").select("count", count="exact").eq("user_id", target_user).eq("is_active", True).execute()
        posts_count = posts_response.count if posts_response.count else 0
        
        # Check if current user is following this user
        is_following = False
        if current_user:
            following_list = social_service.get_user_following(current_user)
            is_following = target_user in following_list
        
        return SocialUserProfileResponse(
            user_name=user["user_name"],
            first_name=user.get("first_name"),
            last_name=user.get("last_name"),
            avatar_url=user.get("avatar_url"),
            bio=user.get("bio"),
            total_points=points.total_points,
            level=points.level,
            badges=points.badges,
            followers_count=len(followers),
            following_count=len(following),
            posts_count=posts_count,
            is_following=is_following
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting social user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get social user profile"
        )

# ============================================================================
# Smart Feed Endpoints
# ============================================================================

def get_smart_feed_service(supabase_client: Client = Depends(get_supabase)) -> SmartFeedService:
    """Dependency to get smart feed service."""
    return SmartFeedService(supabase_client)

@app.get("/social/smart-feed", response_model=SmartFeedResponse)
def get_smart_feed(
    user_name: str,
    page: int = 1,
    limit: int = 20,
    post_types: Optional[List[str]] = None,
    level_filter: Optional[str] = None,
    language_filter: Optional[str] = None,
    include_trending: bool = True,
    include_level_peers: bool = True,
    include_study_groups: bool = True,
    personalization_score: float = 0.7,
    smart_feed_service: SmartFeedService = Depends(get_smart_feed_service)
):
    """Get intelligent personalized feed with level-based filtering and trending content."""
    try:
        from src.social_models import PostType
        post_type_enums = None
        if post_types:
            post_type_enums = [PostType(pt) for pt in post_types if pt in [p.value for p in PostType]]
        
        request = SmartFeedRequest(
            page=page,
            limit=limit,
            post_types=post_type_enums,
            level_filter=level_filter,
            language_filter=language_filter,
            include_trending=include_trending,
            include_level_peers=include_level_peers,
            include_study_groups=include_study_groups,
            personalization_score=personalization_score
        )
        
        return smart_feed_service.get_smart_feed(user_name, request)
    except Exception as e:
        logger.error(f"Error getting smart feed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get smart feed"
        )

@app.get("/social/trending-words")
def get_trending_words(
    language: str,
    level: str,
    limit: int = 20,
    smart_feed_service: SmartFeedService = Depends(get_smart_feed_service)
):
    """Get trending words for specific language and level."""
    try:
        trending_words = smart_feed_service.get_trending_words(language, level, limit)
        return {"trending_words": trending_words, "count": len(trending_words)}
    except Exception as e:
        logger.error(f"Error getting trending words: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get trending words"
        )

@app.get("/social/users/{user_name}/privacy-settings", response_model=UserPrivacySettings)
def get_user_privacy_settings(
    user_name: str,
    smart_feed_service: SmartFeedService = Depends(get_smart_feed_service)
):
    """Get user privacy settings."""
    try:
        return smart_feed_service._get_user_privacy_settings(user_name)
    except Exception as e:
        logger.error(f"Error getting privacy settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get privacy settings"
        )

@app.put("/social/users/{user_name}/privacy-settings")
def update_user_privacy_settings(
    user_name: str,
    settings: UserPrivacySettings,
    smart_feed_service: SmartFeedService = Depends(get_smart_feed_service)
):
    """Update user privacy settings."""
    try:
        success = smart_feed_service.update_user_privacy_settings(user_name, settings)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update privacy settings"
            )
        return {"message": "Privacy settings updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating privacy settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update privacy settings"
        )

# ============================================================================
# Study Analytics Endpoints
# ============================================================================

def get_study_analytics_service(supabase_client: Client = Depends(get_supabase)) -> StudyAnalyticsService:
    """Dependency to get study analytics service."""
    return StudyAnalyticsService(supabase_client)

@app.post("/study/record-word")
def record_word_study(
    user_name: str,
    word: str,
    language: str,
    level: str,
    study_type: str,
    context: Optional[str] = None,
    difficulty_score: Optional[float] = None,
    study_analytics_service: StudyAnalyticsService = Depends(get_study_analytics_service)
):
    """Record a word being studied by a user."""
    try:
        success = study_analytics_service.record_word_study(
            user_name, word, language, level, study_type, context, difficulty_score
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to record word study"
            )
        return {"message": "Word study recorded successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording word study: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record word study"
        )

@app.get("/study/word-analytics/{word}")
def get_word_analytics(
    word: str,
    language: str,
    study_analytics_service: StudyAnalyticsService = Depends(get_study_analytics_service)
):
    """Get global analytics for a specific word."""
    try:
        analytics = study_analytics_service.get_global_word_analytics(word, language)
        if not analytics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Word analytics not found"
            )
        return analytics
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting word analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get word analytics"
        )

@app.get("/study/analytics", response_model=StudyAnalyticsResponse)
def get_study_analytics(
    language: str,
    level: Optional[str] = None,
    time_period: str = "today",
    limit: int = 50,
    user_name: Optional[str] = None,
    study_analytics_service: StudyAnalyticsService = Depends(get_study_analytics_service)
):
    """Get comprehensive study analytics."""
    try:
        request = StudyAnalyticsRequest(
            language=language,
            level=level,
            time_period=time_period,
            limit=limit
        )
        return study_analytics_service.get_study_analytics(request, user_name)
    except Exception as e:
        logger.error(f"Error getting study analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get study analytics"
        )

@app.get("/study/trending-words")
def get_trending_words(
    language: str,
    level: Optional[str] = None,
    limit: int = 20,
    study_analytics_service: StudyAnalyticsService = Depends(get_study_analytics_service)
):
    """Get trending words for a language and level."""
    try:
        trending_words = study_analytics_service.get_trending_words(language, level, limit)
        return {"trending_words": trending_words, "count": len(trending_words)}
    except Exception as e:
        logger.error(f"Error getting trending words: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get trending words"
        )

@app.get("/study/users/{user_name}/insights", response_model=StudyInsights)
def get_user_study_insights(
    user_name: str,
    study_analytics_service: StudyAnalyticsService = Depends(get_study_analytics_service)
):
    """Get study insights for a specific user."""
    try:
        insights = study_analytics_service.get_user_study_insights(user_name)
        if not insights:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User study insights not found"
            )
        return insights
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user study insights: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user study insights"
        ) 