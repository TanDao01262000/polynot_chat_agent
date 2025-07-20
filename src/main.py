"""
PolyNot Language Learning API
----------------------------
A FastAPI-based application for language learning conversations with AI partners.
The system supports both predefined and custom conversation scenarios, with features
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

from .chat_agent import chat_agent
from .models import (
    ChatRequest, Feedback, ConversationHistory, User,
    UserLevel, CustomScenario, PremadeScenario, CreateCustomScenarioRequest
)
from .feedback_tool import feedback_tool
from .level_evaluator_tool import level_evaluator_tool

# ============================================================================
# Configuration and Setup
# ============================================================================

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
        
        # Initialize premade scenarios if they don't exist
        scenarios_response = supabase.table("premade_scenarios").select("*").execute()
        existing_scenarios = scenarios_response.data
        
        if not existing_scenarios:
            logger.info("Initializing premade scenarios...")
            for scenario_data in INITIAL_PREMADE_SCENARIOS:
                supabase.table("premade_scenarios").insert(scenario_data).execute()
            logger.info("Premade scenarios initialized successfully")
        else:
            logger.info(f"Found {len(existing_scenarios)} existing premade scenarios")
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise Exception(f"Database initialization failed: {str(e)}")

def get_supabase():
    """Dependency for Supabase client."""
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
# Initial Premade Scenarios
# ============================================================================

# Initial premade scenarios data
INITIAL_PREMADE_SCENARIOS = [
    {
        "id": "coffee_shop",
        "ai_role": "barista",
        "scenario": "Ordering a drink at a coffee shop",
        "target_language": "English",
        "user_level": UserLevel.A2
    },
    {
        "id": "job_interview",
        "ai_role": "Hiring Manager",
        "scenario": "Job interview for a marketing assistant position",
        "target_language": "English",
        "user_level": UserLevel.B2
    },
    {
        "id": "first_date",
        "ai_role": "date partner",
        "scenario": "First date at a casual restaurant",
        "target_language": "English",
        "user_level": UserLevel.B1
    },
    {
        "id": "travel_planning",
        "ai_role": "travel agent",
        "scenario": "Planning a vacation trip",
        "target_language": "English",
        "user_level": UserLevel.B1
    },
    {
        "id": "doctor_visit",
        "ai_role": "doctor",
        "scenario": "Visit to the doctor's office",
        "target_language": "English",
        "user_level": UserLevel.B2
    },
    {
        "id": "shopping",
        "ai_role": "shop assistant",
        "scenario": "Shopping for clothes",
        "target_language": "English",
        "user_level": UserLevel.A2
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

@app.patch("/users/{user_name}", response_model=User)
def update_user_level(
    user_name: str,
    user_level: UserLevel,
    supabase_client: Client = Depends(get_supabase)
):
    """Update user's language level."""
    try:
        # Convert enum to string value
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
        logger.error(f"Error updating user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
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
    2. Get scenario configuration
    3. Store user message
    4. Process chat with AI
    5. Store AI response
    6. Return response to user
    
    Args:
        req: ChatRequest containing user input and context
        supabase_client: Supabase client
    
    Returns:
        Dict containing thread_id and AI response
    
    Raises:
        HTTPException: If user not found or scenario invalid
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

        # Get scenario configuration
        scenario = get_scenario_config(req, user)
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid scenario configuration"
            )

        # Store user message
        user_message = store_message(
            supabase_client,
            req.thread_id,
            user["id"],
            "user",
            req.user_input,
            req.scenario_id,
            "premade" if req.scenario_id in ["coffee_shop", "job_interview", "first_date", "travel_planning", "doctor_visit", "shopping"] else "custom"
        )

        # Process chat with AI
        response = process_chat(req, scenario)

        # Store AI response
        ai_message = store_message(
            supabase_client,
            req.thread_id,
            user["id"],
            "assistant",
            response,
            req.scenario_id,
            "premade" if req.scenario_id in ["coffee_shop", "job_interview", "first_date", "travel_planning", "doctor_visit", "shopping"] else "custom"
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

        # Get scenario from the first message
        scenario = conversation_history[0].get("scenario_id", "") if conversation_history else ""

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

        # Get scenario from the first message
        scenario = conversation_history[0].get("scenario_id", "") if conversation_history else ""

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
# Custom Scenario Management
# ============================================================================

@app.post("/scenarios/", status_code=status.HTTP_201_CREATED)
def create_custom_scenario(scenario: CreateCustomScenarioRequest, supabase_client: Client = Depends(get_supabase)):
    """
    Create a new custom conversation scenario.
    
    Process:
    1. Verify user exists
    2. Generate unique scenario ID
    3. Store scenario in database
    
    Args:
        scenario: CreateCustomScenarioRequest model containing scenario details
        supabase_client: Supabase client
    
    Returns:
        Created scenario object
    
    Raises:
        HTTPException: If user not found or creation fails
    """
    try:
        # Verify user exists and get user_id
        user_response = supabase_client.table("users").select("*").eq("user_name", scenario.user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user = user_response.data[0]
        logger.info(f"Found user: {user['user_name']} with ID: {user['id']}")

        # Generate unique ID for the scenario
        scenario_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        # Convert string user_level to UserLevel enum
        try:
            user_level_enum = UserLevel(scenario.user_level)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid user_level: {scenario.user_level}. Must be one of: {[level.value for level in UserLevel]}"
            )
        
        scenario_data = {
            "id": scenario_id,
            "user_id": user["id"],  # Use user_id instead of user_name
            "ai_role": scenario.ai_role,
            "scenario": scenario.scenario,
            "target_language": scenario.target_language,
            "user_level": user_level_enum.value,  # Use enum value
            "created_at": created_at,
            "is_active": True
        }
        
        logger.info(f"Attempting to insert scenario data: {scenario_data}")
        response = supabase_client.table("custom_scenarios").insert(scenario_data).execute()
        
        if response.data:
            logger.info(f"Created new custom scenario: {scenario_id} by {scenario.user_name}")
            # Return raw database response instead of trying to validate against model
            return response.data[0]
        else:
            logger.error("No data returned from scenario creation")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create scenario"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating custom scenario: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create custom scenario"
        )

@app.get("/scenarios/{user_name}")
def get_user_scenarios(user_name: str, supabase_client: Client = Depends(get_supabase)):
    """Get all custom scenarios created by a user."""
    try:
        # First get the user to get their user_id
        user_response = supabase_client.table("users").select("*").eq("user_name", user_name).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user = user_response.data[0]
        
        # Then get scenarios using user_id
        response = supabase_client.table("custom_scenarios").select("*").eq("user_id", user["id"]).eq("is_active", True).execute()
        # Return raw database response instead of trying to validate against model
        return response.data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user scenarios: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch scenarios"
        )

@app.delete("/scenarios/{scenario_id}")
def delete_custom_scenario(scenario_id: str, supabase_client: Client = Depends(get_supabase)):
    """Soft delete a custom scenario by setting is_active to False."""
    try:
        response = supabase_client.table("custom_scenarios").update({"is_active": False}).eq("id", scenario_id).execute()
        
        if response.data:
            logger.info(f"Deleted custom scenario: {scenario_id}")
            return {"message": "Scenario deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scenario not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting scenario: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete scenario"
        )

# ============================================================================
# Premade Scenario Management
# ============================================================================

@app.get("/premade-scenarios/", response_model=List[PremadeScenario])
def get_premade_scenarios(
    user_level: Optional[UserLevel] = None,
    target_language: Optional[str] = None,
    supabase_client: Client = Depends(get_supabase)
):
    """
    Get all active premade scenarios, optionally filtered by level and language.
    
    Args:
        user_level: Optional CEFR level filter
        target_language: Optional language filter
        supabase_client: Supabase client
    
    Returns:
        List of premade scenarios
    """
    try:
        query = supabase_client.table("premade_scenarios").select("*").eq("is_active", True)
        
        if user_level:
            # Convert enum to string value
            user_level_str = user_level.value if hasattr(user_level, 'value') else str(user_level)
            logger.info(f"Filtering by user_level: {user_level_str}")
            query = query.eq("user_level", user_level_str)
        if target_language:
            logger.info(f"Filtering by target_language: {target_language}")
            query = query.eq("target_language", target_language)
            
        response = query.execute()
        logger.info(f"Found {len(response.data)} premade scenarios")
        return response.data
    except Exception as e:
        logger.error(f"Error fetching premade scenarios: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch scenarios"
        )

@app.post("/premade-scenarios/", response_model=PremadeScenario, status_code=status.HTTP_201_CREATED)
def create_premade_scenario(scenario: PremadeScenario, supabase_client: Client = Depends(get_supabase)):
    """
    Create a new premade scenario (admin only).
    
    Args:
        scenario: PremadeScenario model containing scenario details
        supabase_client: Supabase client
    
    Returns:
        Created scenario object
    """
    try:
        # Generate unique ID if not provided
        if not scenario.id:
            scenario.id = str(uuid.uuid4())
        
        scenario.created_at = datetime.now().isoformat()
        scenario.updated_at = datetime.now().isoformat()
        
        # Convert enum to string value
        user_level_str = scenario.user_level.value if hasattr(scenario.user_level, 'value') else str(scenario.user_level)
        
        scenario_data = {
            "id": scenario.id,
            "ai_role": scenario.ai_role,
            "scenario": scenario.scenario,
            "target_language": scenario.target_language,
            "user_level": user_level_str,
            "is_active": scenario.is_active,
            "created_at": scenario.created_at,
            "updated_at": scenario.updated_at
        }
        
        response = supabase_client.table("premade_scenarios").insert(scenario_data).execute()
        
        if response.data:
            logger.info(f"Created new premade scenario: {scenario.id}")
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create scenario"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating premade scenario: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create scenario"
        )

@app.patch("/premade-scenarios/{scenario_id}", response_model=PremadeScenario)
def update_premade_scenario(
    scenario_id: str,
    scenario_update: PremadeScenario,
    supabase_client: Client = Depends(get_supabase)
):
    """
    Update an existing premade scenario (admin only).
    
    Args:
        scenario_id: ID of the scenario to update
        scenario_update: Updated scenario data
        supabase_client: Supabase client
    
    Returns:
        Updated scenario object
    """
    try:
        # Get current scenario
        response = supabase_client.table("premade_scenarios").select("*").eq("id", scenario_id).execute()
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scenario not found"
            )
        
        # Prepare update data
        update_data = {
            "updated_at": datetime.now().isoformat()
        }
        
        # Add fields that are provided
        if scenario_update.ai_role:
            update_data["ai_role"] = scenario_update.ai_role
        if scenario_update.scenario:
            update_data["scenario"] = scenario_update.scenario
        if scenario_update.target_language:
            update_data["target_language"] = scenario_update.target_language
        if scenario_update.user_level:
            # Convert enum to string value
            user_level_str = scenario_update.user_level.value if hasattr(scenario_update.user_level, 'value') else str(scenario_update.user_level)
            update_data["user_level"] = user_level_str
        if scenario_update.is_active is not None:
            update_data["is_active"] = scenario_update.is_active
        
        # Update scenario
        update_response = supabase_client.table("premade_scenarios").update(update_data).eq("id", scenario_id).execute()
        
        if update_response.data:
            logger.info(f"Updated premade scenario: {scenario_id}")
            return update_response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update scenario"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating premade scenario: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update scenario"
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

@app.get("/debug/premade-scenarios")
def debug_premade_scenarios():
    """Debug endpoint to check premade scenarios data."""
    try:
        # Get all scenarios without any filters
        response = supabase.table("premade_scenarios").select("*").execute()
        
        return {
            "total_count": len(response.data),
            "scenarios": response.data,
            "message": "Raw data from premade_scenarios table"
        }
    except Exception as e:
        return {
            "error": str(e),
            "message": "Failed to fetch premade scenarios"
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
        
        # Test 2: Check premade scenarios
        try:
            response = supabase.table("premade_scenarios").select("*").execute()
            results["premade_scenarios"] = f"✅ Found {len(response.data)} scenarios"
        except Exception as e:
            results["premade_scenarios"] = f"❌ Failed: {str(e)}"
        
        # Test 3: Check users table
        try:
            response = supabase.table("users").select("*").execute()
            results["users_table"] = f"✅ Found {len(response.data)} users"
        except Exception as e:
            results["users_table"] = f"❌ Failed: {str(e)}"
        
        # Test 4: Check custom scenarios table
        try:
            response = supabase.table("custom_scenarios").select("*").execute()
            results["custom_scenarios"] = f"✅ Found {len(response.data)} scenarios"
        except Exception as e:
            results["custom_scenarios"] = f"❌ Failed: {str(e)}"
        
        # Test 5: Check conversation history table
        try:
            response = supabase.table("conversation_history").select("*").execute()
            results["conversation_history"] = f"✅ Found {len(response.data)} messages"
        except Exception as e:
            results["conversation_history"] = f"❌ Failed: {str(e)}"
        
        # Test 6: Test enum filtering
        try:
            response = supabase.table("premade_scenarios").select("*").eq("user_level", "B1").execute()
            results["enum_filtering"] = f"✅ Found {len(response.data)} B1 scenarios"
        except Exception as e:
            results["enum_filtering"] = f"❌ Failed: {str(e)}"
        
        return {
            "status": "Test completed",
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "Test failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
# ============================================================================
# Get Chat History
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



# ============================================================================
# Helper Functions
# ============================================================================

def get_scenario_config(req: ChatRequest, user: User) -> Optional[Dict]:
    """
    Get scenario configuration from either custom or premade scenarios.
    
    Priority:
    1. Custom scenarios (if scenario_id provided)
    2. Premade scenarios (if scenario_id matches)
    3. Request parameters (if ai_role and scenario provided)
    
    Args:
        req: ChatRequest containing scenario information
        user: User object for default values
    
    Returns:
        Dict containing scenario configuration or None if invalid
    """
    try:
        # First check if it's a custom scenario
        if req.scenario_id:
            # Check custom scenarios
            custom_response = supabase.table("custom_scenarios").select("*").eq("id", req.scenario_id).eq("is_active", True).execute()
            if custom_response.data:
                custom_scenario = custom_response.data[0]
                return {
                    "id": custom_scenario["id"],
                    "ai_role": custom_scenario["ai_role"],
                    "scenario": custom_scenario["scenario"],
                    "target_language": custom_scenario["target_language"],
                    "user_level": custom_scenario["user_level"]
                }
            
            # Check premade scenarios
            premade_response = supabase.table("premade_scenarios").select("*").eq("id", req.scenario_id).eq("is_active", True).execute()
            if premade_response.data:
                premade_scenario = premade_response.data[0]
                return {
                    "id": premade_scenario["id"],
                    "ai_role": premade_scenario["ai_role"],
                    "scenario": premade_scenario["scenario"],
                    "target_language": premade_scenario["target_language"],
                    "user_level": premade_scenario["user_level"]
                }

        # If no scenario ID provided, use the request parameters
        if req.ai_role and req.scenario:
            return {
                "id": str(uuid.uuid4()),
                "ai_role": req.ai_role,
                "scenario": req.scenario,
                "target_language": req.target_language or user["target_language"],
                "user_level": user["user_level"]
            }

        return None
    except Exception as e:
        logger.error(f"Error getting scenario config: {str(e)}")
        return None

def store_message(
    supabase_client: Client,
    thread_id: str,
    user_id: str,
    role: str,
    content: str,
    scenario_id: Optional[str],
    scenario_type: Optional[str] = None
) -> Dict:
    """
    Store a message in the conversation history.
    
    Args:
        supabase_client: Supabase client
        thread_id: Conversation thread identifier
        user_id: User ID of the participant
        role: Message sender role (user/assistant)
        content: Message content
        scenario_id: Associated scenario ID
        scenario_type: Type of scenario ('premade' or 'custom')
    
    Returns:
        Stored message data
    """
    message_data = {
        "thread_id": thread_id,
        "user_id": user_id,
        "message_id": str(uuid.uuid4()),
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "scenario_id": scenario_id,
        "scenario_type": scenario_type
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

def process_chat(req: ChatRequest, scenario: Dict) -> str:
    """
    Process chat request using the AI chat agent.
    
    Args:
        req: ChatRequest containing user input
        scenario: Scenario configuration
    
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
        "ai_role": scenario["ai_role"],
        "scenario": scenario["scenario"],
        "target_language": scenario["target_language"],
        "user_level": scenario["user_level"]
    }

    result = chat_agent.invoke(new_state, config=config)
    return result["messages"][-1].content

