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

from .chat_agent import chat_agent
from .models import (
    ChatRequest, ChatResponse, Feedback, ConversationHistory, User,
    UserLevel, Partner, CreatePartnerRequest, GreetRequest, GreetingResponse,
    ConversationThread, Message
)
from .feedback_tool import feedback_tool
from .level_evaluator_tool import level_evaluator_tool

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

# ============================================================================
# FastAPI Application Setup
# ============================================================================

app = FastAPI(
    title="PolyNot Language Learning API",
    description="API for language learning conversations with user-specific thread IDs",
    version="2.0.0"
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
        response = supabase.table("users").select("count", count="exact").limit(1).execute()
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
        user_response = supabase_client.table("users").select("*").eq("user_name", req.user_name).execute()
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
        user_response = supabase_client.table("users").select("*").eq("user_name", req.user_name).execute()
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

        # Process chat with AI
        response = process_chat(req, partner, thread_id, supabase_client)

        # Store AI response
        save_message(thread_id, response, "assistant", supabase_client)

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
        response = supabase.table("users").select("count", count="exact").limit(1).execute()
        
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
    try:
        # This would migrate old ConversationHistory to new ConversationThread/Message system
        # Implementation depends on your migration strategy
        return {
            "status": "migration_ready",
            "message": "Migration endpoint ready - implement based on your needs",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "migration_failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# ============================================================================
# User Management Endpoints
# ============================================================================

@app.post("/users/", status_code=201)
def create_user(user: User, supabase_client: Client = Depends(get_supabase)):
    """Create a new user."""
    try:
        user_data = {
            "user_name": user.user_name,
            "user_level": user.user_level,  # Remove .value since UserLevel is already a string enum
            "target_language": user.target_language,
            "created_at": datetime.now().isoformat()
        }
        
        response = supabase_client.table("users").insert(user_data).execute()
        if response.data:
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user"
            )
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

@app.get("/users/{user_name}")
def get_user(user_name: str, supabase_client: Client = Depends(get_supabase)):
    """Get user information."""
    try:
        response = supabase_client.table("users").select("*").eq("user_name", user_name).execute()
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
            # Get user's custom partners
            user_response = supabase_client.table("users").select("id").eq("user_name", user_name).execute()
            if user_response.data:
                user_id = user_response.data[0]["id"]
                query = query.eq("user_id", user_id)
        
        response = query.execute()
        return response.data if response.data else []
        
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
        
        response = supabase_client.table("partners").insert(partner_data).execute()
        if response.data:
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create partner"
            )
    except Exception as e:
        logger.error(f"Error creating partner: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create partner"
        ) 