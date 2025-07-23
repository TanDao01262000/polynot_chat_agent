"""
PolyNot Language Learning API
----------------------------
A FastAPI-based application for language learning conversations with AI partners.
The system supports both predefined and custom conversation partners, with features
for user management, conversation history, feedback, and level evaluation.
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
    ChatRequest, Feedback, ConversationHistory, User,
    UserLevel, Partner, CreatePartnerRequest
)
from .feedback_tool import feedback_tool
from .level_evaluator_tool import level_evaluator_tool

# ============================================================================
# Configuration and Setup
# ============================================================================

# Load environment variables from .env file
load_dotenv(override=True)

# Configure logging for application-wide logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# LangChain configuration for AI model integration
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
# Database Helper Functions
# ============================================================================

def create_db_and_tables():
    """
    Initialize database tables on application startup.
    Creates all necessary tables and verifies their structure.
    """
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
# FastAPI Application Setup
# ============================================================================

app = FastAPI(
    title="PolyNot Language Learning API",
    description="API for language learning conversations and feedback",
    version="1.0.0"
)

# ============================================================================
# Initial Premade Partners
# ============================================================================

# Initial premade partners data
INITIAL_PREMADE_PARTNERS = [
    {
        "id": str(UUID("11111111-1111-1111-1111-111111111111")),
        "name": "Emily Carter",
        "ai_role": "barista",
        "scenario": "Ordering a drink at a coffee shop",
        "target_language": "English",
        "user_level": UserLevel.A2,
        "personality": "Emily is a warm, enthusiastic barista who loves coffee and people. She's patient, friendly, and always ready to help customers find their perfect drink. She has a positive attitude and enjoys chatting with customers about their day.",
        "background": "Emily has been working as a barista for 3 years at this popular local coffee shop. She studied hospitality in college and has a passion for coffee culture. She's originally from Seattle and loves sharing her knowledge about different coffee beans and brewing methods.",
        "communication_style": "Emily speaks in a friendly, casual manner. She uses simple, clear language and is very patient with non-native speakers. She often asks follow-up questions to ensure she gets orders right and makes helpful suggestions.",
        "expertise": "Emily is an expert in coffee preparation, different brewing methods, and coffee bean varieties. She knows about espresso, cappuccino, latte, Americano, and specialty drinks. She can recommend drinks based on preferences and explain coffee terminology.",
        "interests": "Emily loves trying new coffee beans, reading about coffee culture, and experimenting with latte art. She also enjoys hiking and photography in her free time.",
        "is_premade": True,
        "is_active": True
    },
    {
        "id": str(UUID("22222222-2222-2222-2222-222222222222")),
        "name": "Michael Lee",
        "ai_role": "Hiring Manager",
        "scenario": "Job interview for a marketing assistant position",
        "target_language": "English",
        "user_level": UserLevel.B2,
        "personality": "Michael is a professional, experienced hiring manager who is fair and thorough in his evaluations. He's direct but encouraging, and he genuinely wants to help candidates succeed. He values preparation and clear communication.",
        "background": "Michael has 8 years of experience in human resources and has conducted hundreds of interviews. He has a degree in Business Administration and has worked for both startups and established companies. He's currently the HR Manager at a growing marketing agency.",
        "communication_style": "Michael speaks in a professional, formal manner appropriate for business settings. He asks clear, structured questions and provides constructive feedback. He uses business terminology and expects professional responses.",
        "expertise": "Michael is an expert in recruitment, interviewing techniques, and evaluating candidate qualifications. He understands marketing roles, digital marketing trends, and what makes successful marketing professionals. He can assess both technical skills and cultural fit.",
        "interests": "Michael enjoys reading business books, attending HR conferences, and mentoring young professionals. He's also interested in digital marketing trends and often attends industry events.",
        "is_premade": True,
        "is_active": True
    },
    {
        "id": str(UUID("33333333-3333-3333-3333-333333333333")),
        "name": "Sophie Martin",
        "ai_role": "date partner",
        "scenario": "First date at a casual restaurant",
        "target_language": "English",
        "user_level": UserLevel.B1,
        "personality": "Sophie is a friendly, outgoing person who enjoys meeting new people. She's curious, has a good sense of humor, and is genuinely interested in learning about others. She's comfortable with casual conversation and likes to share stories about her life.",
        "background": "Sophie is a 28-year-old graphic designer who moved to the city 2 years ago. She grew up in a small town and loves the energy of city life. She's been on several dates and enjoys the process of getting to know someone new.",
        "communication_style": "Sophie speaks in a casual, friendly manner. She uses everyday language and often asks personal questions to get to know her date better. She shares personal stories and shows genuine interest in the other person's experiences.",
        "expertise": "Sophie is knowledgeable about art, design, and creative work. She can discuss current events, popular culture, and city life. She's experienced in dating and knows how to keep conversations flowing naturally.",
        "interests": "Sophie loves art galleries, trying new restaurants, hiking, and photography. She's also interested in travel and enjoys learning about different cultures. She's always looking for new creative projects and adventures.",
        "is_premade": True,
        "is_active": True
    },
    {
        "id": str(UUID("44444444-4444-4444-4444-444444444444")),
        "name": "Carlos Rivera",
        "ai_role": "travel agent",
        "scenario": "Planning a vacation trip",
        "target_language": "English",
        "user_level": UserLevel.B1,
        "personality": "Carlos is an enthusiastic and knowledgeable travel agent who loves helping people plan their dream vacations. He's patient, detail-oriented, and genuinely excited about travel. He takes pride in finding the perfect destinations and deals for his clients.",
        "background": "Carlos has been a travel agent for 12 years and has visited over 30 countries himself. He studied Tourism Management and has worked with clients planning all types of trips, from budget backpacking to luxury vacations. He's originally from Mexico and speaks Spanish fluently.",
        "communication_style": "Carlos speaks in a friendly, professional manner. He asks detailed questions to understand preferences and budget. He uses travel terminology but explains unfamiliar terms. He's very thorough in his recommendations.",
        "expertise": "Carlos is an expert in travel planning, destination knowledge, booking systems, and travel regulations. He knows about different types of accommodations, transportation options, and travel insurance. He can recommend activities and attractions for various destinations.",
        "interests": "Carlos loves exploring new destinations, learning about different cultures, and trying local cuisines. He enjoys photography and often shares travel tips on social media. He's also interested in sustainable tourism and eco-friendly travel options.",
        "is_premade": True,
        "is_active": True
    },
    {
        "id": str(UUID("55555555-5555-5555-5555-555555555555")),
        "name": "Dr. Olivia Smith",
        "ai_role": "doctor",
        "scenario": "Visit to the doctor's office",
        "target_language": "English",
        "user_level": UserLevel.B2,
        "personality": "Dr. Smith is a caring, professional physician who puts her patients at ease. She's thorough, compassionate, and explains medical information clearly. She's patient with questions and takes time to ensure patients understand their health situation.",
        "background": "Dr. Smith has been practicing medicine for 15 years and specializes in family medicine. She completed her medical degree at a top university and has worked in both urban and rural settings. She's known for her excellent bedside manner and clear communication.",
        "communication_style": "Dr. Smith speaks in a professional but warm manner. She uses medical terminology but always explains terms in simple language. She asks clear questions and provides detailed but understandable explanations. She's very patient with non-native speakers.",
        "expertise": "Dr. Smith is an expert in general medicine, common illnesses, preventive care, and patient education. She can diagnose various conditions, prescribe medications, and provide lifestyle advice. She's knowledgeable about symptoms, treatments, and when to refer to specialists.",
        "interests": "Dr. Smith enjoys staying updated on medical research, reading medical journals, and attending conferences. She's also interested in preventive medicine and public health. In her free time, she enjoys yoga and hiking.",
        "is_premade": True,
        "is_active": True
    },
    {
        "id": str(UUID("66666666-6666-6666-6666-666666666666")),
        "name": "Anna Kim",
        "ai_role": "shop assistant",
        "scenario": "Shopping for clothes",
        "target_language": "English",
        "user_level": UserLevel.A2,
        "personality": "Anna is a friendly, helpful shop assistant who loves fashion and helping customers find the perfect outfit. She's patient, has a good eye for style, and enjoys making customers feel confident about their choices. She's always positive and encouraging.",
        "background": "Anna has worked in retail for 5 years and has experience in various clothing stores. She studied Fashion Design in college and has a natural talent for styling. She's worked with customers of all ages and body types, helping them find clothes that make them feel great.",
        "communication_style": "Anna speaks in a friendly, casual manner. She uses simple, clear language and is very patient with customers who need help. She asks questions to understand preferences and makes helpful suggestions. She's encouraging and positive about fashion choices.",
        "expertise": "Anna is an expert in fashion, clothing styles, sizing, and current trends. She knows about different fabrics, care instructions, and how to style various pieces. She can recommend outfits for different occasions and help with fit issues.",
        "interests": "Anna loves following fashion trends, reading fashion magazines, and experimenting with different styles. She enjoys helping customers discover new looks and building their confidence. She's also interested in sustainable fashion and ethical shopping.",
        "is_premade": True,
        "is_active": True
    }
]

# ============================================================================
# Application Lifecycle Events
# ============================================================================

@app.on_event("startup")
def on_startup():
    """Initialize database on application startup."""
    create_db_and_tables()

# ============================================================================
# User Management Endpoints
# ============================================================================

@app.post("/users/", response_model=User, status_code=status.HTTP_201_CREATED)
def create_user(user: User, supabase_client: Client = Depends(get_supabase)):
    """
    Create a new user in the system.
    
    Args:
        user: User model containing username, level, and target language
        supabase_client: Supabase client
    
    Returns:
        Created user object
    
    Raises:
        HTTPException: If user creation fails
    """
    try:
        # Validate user_name
        if not user.user_name or not user.user_name.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Username cannot be empty"
            )
        
        # Validate target_language
        if not user.target_language or not user.target_language.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Target language cannot be empty"
            )
        
        # Validate user_level
        try:
            user_level_str = user.user_level.value if hasattr(user.user_level, 'value') else str(user.user_level)
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid user_level: {user.user_level}. Must be one of: {[level.value for level in UserLevel]}"
            )
        
        user_data = {
            "user_name": user.user_name.strip(),
            "user_level": user_level_str,
            "target_language": user.target_language.strip(),
            "created_at": datetime.now().isoformat()
        }
        
        response = supabase_client.table("users").insert(user_data).execute()
        
        if response.data:
            logger.info(f"Created new user: {user.user_name}")
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

@app.get("/users/{user_name}", response_model=User)
def get_user(user_name: str, supabase_client: Client = Depends(get_supabase)):
    """Get user by username."""
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

@app.patch("/users/{user_name}")
def update_user_level(
    user_name: str,
    user_level: UserLevel,
    supabase_client: Client = Depends(get_supabase)
):
    """Update user's language level."""
    try:
        user_level_str = user_level.value if hasattr(user_level, 'value') else str(user_level)
        
        response = supabase_client.table("users").update({"user_level": user_level_str}).eq("user_name", user_name).execute()
        
        if response.data:
            logger.info(f"Updated user level for {user_name} to {user_level_str}")
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user level: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user level"
        )

# ============================================================================
# Chat System Endpoints
# ============================================================================

@app.post("/chat")
def chat_endpoint(req: ChatRequest, supabase_client: Client = Depends(get_supabase)):
    """
    Handle chat interactions between users and AI partners.
    
    Flow:
    1. Verify user exists
    2. Get partner configuration
    3. Store user message
    4. Process chat with AI
    5. Store AI response
    6. Return response to user
    
    Args:
        req: ChatRequest containing user input and partner_id
        supabase_client: Supabase client
    
    Returns:
        Dict containing thread_id and AI response
    
    Raises:
        HTTPException: If user not found or partner invalid
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

        # Store user message
        user_message = store_message(
            supabase_client,
            req.thread_id,
            user["id"],
            "user",
            req.user_input,
            req.partner_id
        )

        # Process chat with AI
        response = process_chat(req, partner)

        # Store AI response
        ai_message = store_message(
            supabase_client,
            req.thread_id,
            user["id"],
            "assistant",
            response,
            req.partner_id
        )

        return {
            "thread_id": req.thread_id,
            "response": response
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat"
        )

# ============================================================================
# Partner Management Endpoints
# ============================================================================

@app.post("/partners/", status_code=status.HTTP_201_CREATED)
def create_partner(
    user_name: str,
    partner: CreatePartnerRequest, 
    supabase_client: Client = Depends(get_supabase)
):
    """
    Create a new custom conversation partner.
    
    Process:
    1. Verify user exists
    2. Generate unique partner ID
    3. Store partner in database
    
    Args:
        user_name: Username of the creator (query parameter)
        partner: CreatePartnerRequest model containing partner details
        supabase_client: Supabase client
    
    Returns:
        Created partner object
    
    Raises:
        HTTPException: If user not found or creation fails
    """
    try:
        # Verify user exists and get user_id
        user_response = supabase_client.table("users").select("*").eq("user_name", user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user = user_response.data[0]
        logger.info(f"Found user: {user['user_name']} with ID: {user['id']}")

        # Generate unique ID for the partner
        partner_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        # Convert string user_level to UserLevel enum
        try:
            user_level_enum = UserLevel(partner.user_level)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid user_level: {partner.user_level}. Must be one of: {[level.value for level in UserLevel]}"
            )
        
        partner_data = {
            "id": partner_id,
            "name": partner.name,
            "user_id": user["id"],
            "ai_role": partner.ai_role,
            "scenario": partner.scenario,
            "target_language": partner.target_language,
            "user_level": user_level_enum.value,
            "personality": partner.personality,
            "background": partner.background,
            "communication_style": partner.communication_style,
            "expertise": partner.expertise,
            "interests": partner.interests,
            "is_premade": False,
            "is_active": True,
            "created_at": created_at,
            "updated_at": created_at
        }
        
        logger.info(f"Attempting to insert partner data: {partner_data}")
        response = supabase_client.table("partners").insert(partner_data).execute()
        
        if response.data:
            logger.info(f"Created new custom partner: {partner_id} by {user_name}")
            return response.data[0]
        else:
            logger.error("No data returned from partner creation")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create partner"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating custom partner: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create custom partner"
        )

@app.get("/partners/")
def get_all_partners(
    user_level: Optional[UserLevel] = None,
    target_language: Optional[str] = None,
    is_premade: Optional[bool] = None,
    supabase_client: Client = Depends(get_supabase)
):
    """
    Get all active partners, optionally filtered by level, language, and type.
    
    Args:
        user_level: Optional CEFR level filter
        target_language: Optional language filter
        is_premade: Optional filter for premade vs custom partners
        supabase_client: Supabase client
    
    Returns:
        List of partners
    """
    try:
        query = supabase_client.table("partners").select("*").eq("is_active", True)
        
        if user_level:
            user_level_str = user_level.value if hasattr(user_level, 'value') else str(user_level)
            logger.info(f"Filtering by user_level: {user_level_str}")
            query = query.eq("user_level", user_level_str)
        if target_language:
            logger.info(f"Filtering by target_language: {target_language}")
            query = query.eq("target_language", target_language)
        if is_premade is not None:
            logger.info(f"Filtering by is_premade: {is_premade}")
            query = query.eq("is_premade", is_premade)
            
        response = query.execute()
        logger.info(f"Found {len(response.data)} partners")
        return response.data
    except Exception as e:
        logger.error(f"Error fetching partners: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch partners"
        )

@app.get("/partners/{user_name}")
def get_user_partners(user_name: str, supabase_client: Client = Depends(get_supabase)):
    """Get all custom partners created by a user."""
    try:
        # First get the user to get their user_id
        user_response = supabase_client.table("users").select("*").eq("user_name", user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user = user_response.data[0]
        
        # Then get partners using user_id
        response = supabase_client.table("partners").select("*").eq("user_id", user["id"]).eq("is_active", True).execute()
        return response.data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user partners: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch partners"
        )

# ============================================================================
# Feedback and Evaluation Endpoints
# ============================================================================

@app.post("/feedback")
def get_feedback(
    user_name: str,
    thread_id: str,
    supabase_client: Client = Depends(get_supabase)
):
    """
    Get detailed feedback for a conversation.
    
    Process:
    1. Retrieve user and conversation history
    2. Format messages for feedback tool
    3. Generate feedback using AI
    4. Return structured feedback
    
    Args:
        user_name: Username of the participant
        thread_id: Conversation thread identifier
        supabase_client: Supabase client
    
    Returns:
        Dict containing conversation feedback
    
    Raises:
        HTTPException: If user/conversation not found or processing fails
    """
    try:
        # Get user from database
        user_response = supabase_client.table("users").select("*").eq("user_name", user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_name} not found"
            )
        user = user_response.data[0]

        # Get conversation history from the thread
        conversation_history = get_conversation_history(supabase_client, thread_id)

        # Get partner from the first message
        partner_id = conversation_history[0].get("partner_id", "") if conversation_history else ""

        # Get partner information to get the scenario
        scenario = "General conversation"
        if partner_id:
            try:
                partner_response = supabase_client.table("partners").select("scenario").eq("id", partner_id).execute()
                if partner_response.data:
                    scenario = partner_response.data[0].get("scenario", "General conversation")
            except Exception as e:
                logger.warning(f"Could not get partner scenario: {str(e)}")

        # Format messages for feedback tool
        formatted_messages = [{
            "role": msg["role"],
            "content": msg["content"]
        } for msg in conversation_history]

        # Get feedback using the feedback tool
        feedback_response = feedback_tool.invoke({
            "user_name": user_name,
            "user_level": user["user_level"],
            "target_language": user["target_language"],
            "scenario": scenario,
            "messages": formatted_messages
        })

        # Handle AIMessage response
        if hasattr(feedback_response, 'content'):
            feedback_content = feedback_response.content
        else:
            feedback_content = str(feedback_response)

        try:
            feedback_data = json.loads(feedback_content)
            return feedback_data
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid feedback format received"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feedback: {str(e)}"
        )

@app.post("/evaluate")
def evaluate_level(
    user_name: str,
    thread_id: str,
    supabase_client: Client = Depends(get_supabase)
):
    """
    Evaluate user's language level based on conversation.
    
    Process:
    1. Retrieve user and conversation history
    2. Format messages for evaluation
    3. Generate level assessment using AI
    4. Return evaluation results
    
    Args:
        user_name: Username of the participant
        thread_id: Conversation thread identifier
        supabase_client: Supabase client
    
    Returns:
        Dict containing level evaluation
    
    Raises:
        HTTPException: If user/conversation not found or processing fails
    """
    try:
        # Get user from database
        user_response = supabase_client.table("users").select("*").eq("user_name", user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_name} not found"
            )
        user = user_response.data[0]

        # Get conversation history from the thread
        conversation_history = get_conversation_history(supabase_client, thread_id)

        # Get partner from the first message
        partner_id = conversation_history[0].get("partner_id", "") if conversation_history else ""

        # Get partner information to get the scenario
        scenario = "General conversation"
        if partner_id:
            try:
                partner_response = supabase_client.table("partners").select("scenario").eq("id", partner_id).execute()
                if partner_response.data:
                    scenario = partner_response.data[0].get("scenario", "General conversation")
            except Exception as e:
                logger.warning(f"Could not get partner scenario: {str(e)}")

        # Format messages for evaluation
        formatted_messages = [{
            "role": msg["role"],
            "content": msg["content"]
        } for msg in conversation_history]

        # Get evaluation using the level evaluator tool
        evaluation_response = level_evaluator_tool.invoke({
            "user_name": user_name,
            "target_language": user["target_language"],
            "scenario": scenario,
            "messages": formatted_messages
        })

        # Handle AIMessage response
        if hasattr(evaluation_response, 'content'):
            evaluation_content = evaluation_response.content
        else:
            evaluation_content = str(evaluation_response)

        try:
            evaluation_data = json.loads(evaluation_content)
            return evaluation_data
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid evaluation format received"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error evaluating level: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate level: {str(e)}"
        )

# ============================================================================
# Health Check Endpoints
# ============================================================================

@app.get("/")
def health_check():
    """Health check endpoint for deployment verification."""
    return {
        "status": "healthy",
        "service": "PolyNot Language Learning API",
        "version": "1.0.0",
        "database": "Supabase",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
def detailed_health_check():
    """Detailed health check with database connectivity."""
    try:
        # Test Supabase connection
        response = supabase.table("users").select("count", count="exact").limit(1).execute()
        
        return {
            "status": "healthy",
            "database": "connected",
            "service": "PolyNot Language Learning API",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "service": "PolyNot Language Learning API",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat()
        }

@app.get("/test/all-endpoints")
def test_all_endpoints():
    """Test endpoint to verify all API functionality."""
    try:
        results = {}
        
        # Test 1: Check database connection
        try:
            response = supabase.table("users").select("count", count="exact").limit(1).execute()
            results["database_connection"] = "✅ Connected"
        except Exception as e:
            results["database_connection"] = f"❌ Failed: {str(e)}"
        
        # Test 2: Check partners
        try:
            response = supabase.table("partners").select("*").execute()
            results["partners"] = f"✅ Found {len(response.data)} partners"
        except Exception as e:
            results["partners"] = f"❌ Failed: {str(e)}"
        
        # Test 3: Check users table
        try:
            response = supabase.table("users").select("*").execute()
            results["users_table"] = f"✅ Found {len(response.data)} users"
        except Exception as e:
            results["users_table"] = f"❌ Failed: {str(e)}"
        
        # Test 4: Check conversation history table
        try:
            response = supabase.table("conversation_history").select("*").execute()
            results["conversation_history"] = f"✅ Found {len(response.data)} messages"
        except Exception as e:
            results["conversation_history"] = f"❌ Failed: {str(e)}"
        
        return {
            "status": "test_completed",
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "test_failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# ============================================================================
# Helper Functions
# ============================================================================

@app.get("/threads/{thread_id}/messages")
def get_messages_by_thread(thread_id: str, supabase_client: Client = Depends(get_supabase)):
    """
    Get all messages from a thread
    """
    try:
        messages = get_conversation_history(supabase_client, thread_id)
        return messages
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching messages for thread {thread_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Fail to fetch message history")

def get_partner_config(partner_id: UUID, supabase_client: Client) -> Optional[Dict]:
    """
    Get partner configuration from the partners table.
    
    Args:
        partner_id: Partner identifier
        supabase_client: Supabase client
    
    Returns:
        Dict containing partner configuration or None if not found
    """
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

def store_message(
    supabase_client: Client,
    thread_id: str,
    user_id: UUID,
    role: str,
    content: str,
    partner_id: UUID
) -> Dict:
    """
    Store a message in the conversation history.
    
    Args:
        supabase_client: Supabase client
        thread_id: Conversation thread identifier
        user_id: User ID of the participant
        role: Message sender role (user/assistant)
        content: Message content
        partner_id: Associated partner ID
    
    Returns:
        Stored message data
    """

    message_data = {
        "thread_id": thread_id,
        "user_id": str(user_id),  
        "message_id": str(uuid.uuid4()),  # make sure to convert to str to not error :)
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "partner_id": str(partner_id)  
    }
    
    response = supabase_client.table("conversation_history").insert(message_data).execute()
    return response.data[0] if response.data else message_data

def get_conversation_history(
    supabase_client: Client,
    thread_id: str
) -> List[Dict]:
    """
    Retrieve conversation history for a thread.
    
    Args:
        supabase_client: Supabase client
        thread_id: Conversation thread identifier
    
    Returns:
        List of conversation messages
    
    Raises:
        HTTPException: If no history found
    """
    response = supabase_client.table("conversation_history").select("*").eq("thread_id", thread_id).order("timestamp").execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No conversation history found"
        )
    return response.data

def process_chat(req: ChatRequest, partner: Dict) -> str:
    """
    Process chat request using the AI chat agent.
    
    Args:
        req: ChatRequest containing user input
        partner: Partner configuration
    
    Returns:
        AI response as string
    """
    config = {
        "configurable": {
            "thread_id": req.thread_id
        }
    }

    new_state = {
        "messages": [{
            "message_id": str(uuid.uuid4()),
            "role": "user",
            "content": req.user_input
        }],
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

