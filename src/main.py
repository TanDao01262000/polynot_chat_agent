"""
PolyNot Language Learning API - Updated with User-Specific Thread IDs
--------------------------------------------------------------------
A FastAPI-based application for language learning conversations with AI partners.
The system now uses user-specific thread IDs in format: {user_name}_{partner_id}
"""

from fastapi import FastAPI, HTTPException, Depends, status
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

from src.chat_agent import chat_agent
from src.models import (
    ChatRequest, ChatResponse, Feedback, ConversationHistory, User,
    UserLevel, Partner, CreatePartnerRequest, GreetRequest, GreetingResponse,
    ConversationThread, Message, UserProfileUpdate, UserLevelUpdate, 
    UserStatistics, UserProfileResponse, UserAchievements, ProfileCompletion
)
from src.feedback_tool import feedback_tool
from src.level_evaluator_tool import level_evaluator_tool

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

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
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

# ============================================================================
# Enhanced Validation Functions
# ============================================================================

def validate_username(username: str) -> str:
    """Enhanced username validation with better rules"""
    if not username or not username.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be empty"
        )
    
    username = username.strip()
    
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
        
        # Note: Removed pre-check to avoid race conditions
        # Database constraints will handle duplicate username/email errors properly
        
        # Create user using Supabase Auth signup
        try:
            auth_response = supabase_client.auth.sign_up({
                "email": user_email,
                "password": "TestPassword123!",  # In production, this should be user-provided
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
                    detail="Failed to create authentication account"
                )
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create auth user"
            )
        
        # Prepare profile data with proper array handling
        # Generate a UUID for the profiles table
        import uuid
        profile_id = str(uuid.uuid4())
        profile_data = {
            "id": profile_id,
            "user_name": validated_username,
            "user_level": user.user_level,
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
        
        # Insert into profiles table with simplified error handling
        response = None
        try:
            response = supabase_client.table("profiles").insert(profile_data).execute()
            logger.info(f"Database insert completed successfully")
        except Exception as db_error:
            error_msg = str(db_error)
            logger.error(f"Database error creating profile: {error_msg}")
            
            # For now, just log the error and continue
            # The user might have been created successfully despite the error
            logger.warning(f"Database error occurred, but user might have been created: {error_msg}")
            
            # Don't raise an exception - let's check if the user was actually created
        
        # Check if we have a valid response
        if response and response.data:
            logger.info(f"Response data length: {len(response.data)}")
            logger.info(f"First item in response data: {response.data[0]}")
            
            # Return the user data in the expected format
            user_data = {
                "id": response.data[0]["id"],
                "user_name": response.data[0]["user_name"],
                "user_level": response.data[0]["user_level"],
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
        else:
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
                        "user_level": user_data["user_level"],
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
def update_user_profile(
    user_name: str, 
    profile_update: UserProfileUpdate, 
    supabase_client: Client = Depends(get_supabase)
):
    """Update user profile information."""
    try:
        # Check if user exists
        user_response = supabase_client.table("profiles").select("id").eq("user_name", user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prepare update data (only include non-None values)
        update_data = {}
        for field, value in profile_update.dict(exclude_unset=True).items():
            if value is not None:
                # Handle array fields - convert comma-separated strings to arrays
                if field in ["interests", "preferred_topics"] and isinstance(value, str):
                    # Convert comma-separated string to array format using the helper function
                    update_data[field] = handle_array_field_conversion(field, value)
                elif field in ["interests", "preferred_topics"] and isinstance(value, list):
                    # If already a list, clean it up
                    update_data[field] = [item.strip() for item in value if item and item.strip()]
                else:
                    update_data[field] = value
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid fields to update"
            )
        
        # Add updated timestamp
        update_data["updated_at"] = datetime.now().isoformat()
        
        # Update user profile
        response = supabase_client.table("profiles").update(update_data).eq("user_name", user_name).execute()
        
        if response.data:
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update user profile"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user profile"
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