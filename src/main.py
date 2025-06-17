"""
PolyNot Language Learning API
----------------------------
A FastAPI-based application for language learning conversations with AI partners.
The system supports both predefined and custom conversation scenarios, with features
for user management, conversation history, feedback, and level evaluation.
"""

from fastapi import FastAPI, HTTPException, Depends, status
from sqlmodel import create_engine, Session, SQLModel, select
import uuid
import os
import json
import logging
from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy import inspect
from langchain_core.messages import AIMessage

from .chat_agent import chat_agent
from .models import (
    ChatRequest, Feedback, ConversationHistory, User,
    UserLevel, CustomScenario, PremadeScenario
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

# Database configuration using SQLite
sqlite_url = f"sqlite:///users.db"
engine = create_engine(sqlite_url, echo=True)

def create_db_and_tables():
    """
    Initialize database tables on application startup.
    Creates all necessary tables and verifies their structure.
    """
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created successfully")
    
    # Initialize premade scenarios if they don't exist
    with Session(engine) as session:
        # Check if premade scenarios exist
        existing_scenarios = session.exec(select(PremadeScenario)).all()
        if not existing_scenarios:
            logger.info("Initializing premade scenarios...")
            for scenario_data in INITIAL_PREMADE_SCENARIOS:
                scenario = PremadeScenario(
                    id=scenario_data["id"],
                    ai_role=scenario_data["ai_role"],
                    scenario=scenario_data["scenario"],
                    target_language=scenario_data["target_language"],
                    user_level=scenario_data["user_level"],
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat()
                )
                session.add(scenario)
            session.commit()
            logger.info("Premade scenarios initialized successfully")
        
        # Verify tables exist and have correct structure
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"Created tables: {tables}")
        
        if "conversationhistory" in tables:
            columns = inspector.get_columns("conversationhistory")
            logger.info(f"ConversationHistory columns: {[col['name'] for col in columns]}")

def get_session():
    """
    Database session dependency for FastAPI endpoints.
    Provides a session for database operations and ensures proper cleanup.
    """
    with Session(engine) as session:
        yield session

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
def create_user(user: User, session: Session = Depends(get_session)):
    """
    Create a new user in the system.
    
    Args:
        user: User model containing username, level, and target language
        session: Database session
    
    Returns:
        Created user object
    
    Raises:
        HTTPException: If user creation fails
    """
    try:
        db_user = User(
            user_name=user.user_name,
            user_level=user.user_level,
            target_language=user.target_language,
            created_at=datetime.now().isoformat()
        )
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        logger.info(f"Created new user: {user.user_name}")
        return db_user
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

@app.get("/users/{user_name}", response_model=User)
def get_user(user_name: str, session: Session = Depends(get_session)):
    """Get user by username."""
    statement = select(User).where(User.user_name == user_name)
    user = session.exec(statement).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@app.patch("/users/{user_name}", response_model=User)
def update_user_level(
    user_name: str,
    user_level: UserLevel,
    session: Session = Depends(get_session)
):
    """Update user's language level."""
    statement = select(User).where(User.user_name == user_name)
    user = session.exec(statement).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    user.user_level = user_level
    session.add(user)
    session.commit()
    session.refresh(user)
    logger.info(f"Updated user level for {user_name} to {user_level}")
    return user

# ============================================================================
# Chat System Endpoints
# ============================================================================

@app.post("/chat")
def chat_endpoint(req: ChatRequest, session: Session = Depends(get_session)):
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
        session: Database session
    
    Returns:
        Dict containing thread_id and AI response
    
    Raises:
        HTTPException: If user not found or scenario invalid
    """
    try:
        # Get user from database
        statement = select(User).where(User.user_name == req.user_name)
        user = session.exec(statement).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Get scenario configuration
        scenario = get_scenario_config(req, user)
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid scenario configuration"
            )

        # Store user message
        user_message = store_message(
            session,
            req.thread_id,
            req.user_name,
            "user",
            req.user_input,
            req.scenario_id
        )

        # Process chat with AI
        response = process_chat(req, scenario)

        # Store AI response
        ai_message = store_message(
            session,
            req.thread_id,
            req.user_name,
            "assistant",
            response,
            req.scenario_id
        )

        return {
            "thread_id": req.thread_id,
            "response": response
        }
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
    session: Session = Depends(get_session)
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
        session: Database session
    
    Returns:
        Dict containing conversation feedback
    
    Raises:
        HTTPException: If user/conversation not found or processing fails
    """
    try:
        # Get user from database
        statement = select(User).where(User.user_name == user_name)
        user = session.exec(statement).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_name} not found"
            )

        # Get conversation history from the thread
        conversation_history = session.exec(
            select(ConversationHistory)
            .where(
                ConversationHistory.thread_id == thread_id,
                ConversationHistory.user_name == user_name
            )
            .order_by(ConversationHistory.timestamp)
        ).all()

        if not conversation_history:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No conversation history found for thread {thread_id}"
            )

        # Get scenario from the first message
        scenario = conversation_history[0].scenario_id or ""

        # Format messages for feedback tool
        formatted_messages = [{
            "role": msg.role,
            "content": msg.content
        } for msg in conversation_history]

        # Get feedback using the feedback tool
        feedback_response = feedback_tool.invoke({
            "user_name": user_name,
            "user_level": user.user_level,
            "target_language": user.target_language,
            "scenario": scenario,
            "messages": formatted_messages
        })

        # Handle AIMessage response
        if isinstance(feedback_response, AIMessage):
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

    except HTTPException as he:
        raise he
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
    session: Session = Depends(get_session)
):
    """
    Evaluate user's language level based on conversation.
    
    Process: \n
        1. Retrieve user and conversation history
        2. Format messages for evaluation
        3. Generate level assessment using AI
        4. Return evaluation results
    
    Args: \n
        user_name: Username of the participant
        thread_id: Conversation thread identifier
        session: Database session
    
    Returns:
        Dict containing level evaluation
    
    Raises:
        HTTPException: If user/conversation not found or processing fails
    """
    try:
        # Get user from database
        statement = select(User).where(User.user_name == user_name)
        user = session.exec(statement).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_name} not found"
            )

        # Get conversation history from the thread
        conversation_history = session.exec(
            select(ConversationHistory)
            .where(
                ConversationHistory.thread_id == thread_id,
                ConversationHistory.user_name == user_name
            )
            .order_by(ConversationHistory.timestamp)
        ).all()

        if not conversation_history:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No conversation history found for thread {thread_id}"
            )

        # Get scenario from the first message
        scenario = conversation_history[0].scenario_id or ""

        # Format messages for evaluation
        formatted_messages = [{
            "role": msg.role,
            "content": msg.content
        } for msg in conversation_history]

        # Get evaluation using the level evaluator tool
        evaluation_response = level_evaluator_tool.invoke({
            "user_name": user_name,
            "target_language": user.target_language,
            "scenario": scenario,
            "messages": formatted_messages
        })

        # Handle AIMessage response
        if isinstance(evaluation_response, AIMessage):
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

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error evaluating level: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate level: {str(e)}"
        )

# ============================================================================
# Custom Scenario Management
# ============================================================================

@app.post("/scenarios/", response_model=CustomScenario, status_code=status.HTTP_201_CREATED)
def create_custom_scenario(scenario: CustomScenario, session: Session = Depends(get_session)):
    """
    Create a new custom conversation scenario.
    
    Process:
    1. Verify user exists
    2. Generate unique scenario ID
    3. Store scenario in database
    
    Args:
        scenario: CustomScenario model containing scenario details
        session: Database session
    
    Returns:
        Created scenario object
    
    Raises:
        HTTPException: If user not found or creation fails
    """
    try:
        # Verify user exists
        statement = select(User).where(User.user_name == scenario.user_name)
        user = session.exec(statement).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Generate unique ID for the scenario
        scenario.id = str(uuid.uuid4())
        scenario.created_at = datetime.now().isoformat()
        
        session.add(scenario)
        session.commit()
        session.refresh(scenario)
        logger.info(f"Created new custom scenario: {scenario.id} by {scenario.user_name}")
        return scenario
    except Exception as e:
        logger.error(f"Error creating custom scenario: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create custom scenario"
        )

@app.get("/scenarios/{user_name}", response_model=List[CustomScenario])
def get_user_scenarios(user_name: str, session: Session = Depends(get_session)):
    """Get all custom scenarios created by a user."""
    try:
        statement = select(CustomScenario).where(
            CustomScenario.user_name == user_name,
            CustomScenario.is_active == True
        )
        scenarios = session.exec(statement).all()
        return scenarios
    except Exception as e:
        logger.error(f"Error fetching user scenarios: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch scenarios"
        )

@app.delete("/scenarios/{scenario_id}")
def delete_custom_scenario(scenario_id: str, session: Session = Depends(get_session)):
    """Soft delete a custom scenario by setting is_active to False."""
    try:
        statement = select(CustomScenario).where(CustomScenario.id == scenario_id)
        scenario = session.exec(statement).first()
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scenario not found"
            )
        
        scenario.is_active = False
        session.add(scenario)
        session.commit()
        logger.info(f"Deleted custom scenario: {scenario_id}")
        return {"message": "Scenario deleted successfully"}
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
    session: Session = Depends(get_session)
):
    """
    Get all active premade scenarios, optionally filtered by level and language.
    
    Args:
        user_level: Optional CEFR level filter
        target_language: Optional language filter
        session: Database session
    
    Returns:
        List of premade scenarios
    """
    try:
        query = select(PremadeScenario).where(PremadeScenario.is_active == True)
        
        if user_level:
            query = query.where(PremadeScenario.user_level == user_level)
        if target_language:
            query = query.where(PremadeScenario.target_language == target_language)
            
        scenarios = session.exec(query).all()
        return scenarios
    except Exception as e:
        logger.error(f"Error fetching premade scenarios: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch scenarios"
        )

@app.post("/premade-scenarios/", response_model=PremadeScenario, status_code=status.HTTP_201_CREATED)
def create_premade_scenario(scenario: PremadeScenario, session: Session = Depends(get_session)):
    """
    Create a new premade scenario (admin only).
    
    Args:
        scenario: PremadeScenario model containing scenario details
        session: Database session
    
    Returns:
        Created scenario object
    """
    try:
        # Generate unique ID if not provided
        if not scenario.id:
            scenario.id = str(uuid.uuid4())
        
        scenario.created_at = datetime.now().isoformat()
        scenario.updated_at = datetime.now().isoformat()
        
        session.add(scenario)
        session.commit()
        session.refresh(scenario)
        logger.info(f"Created new premade scenario: {scenario.id}")
        return scenario
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
    session: Session = Depends(get_session)
):
    """
    Update an existing premade scenario (admin only).
    
    Args:
        scenario_id: ID of the scenario to update
        scenario_update: Updated scenario data
        session: Database session
    
    Returns:
        Updated scenario object
    """
    try:
        statement = select(PremadeScenario).where(PremadeScenario.id == scenario_id)
        scenario = session.exec(statement).first()
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scenario not found"
            )
        
        # Update fields
        for field, value in scenario_update.dict(exclude_unset=True).items():
            setattr(scenario, field, value)
        
        scenario.updated_at = datetime.now().isoformat()
        session.add(scenario)
        session.commit()
        session.refresh(scenario)
        logger.info(f"Updated premade scenario: {scenario_id}")
        return scenario
    except Exception as e:
        logger.error(f"Error updating premade scenario: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update scenario"
        )

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
            with Session(engine) as session:
                # Check custom scenarios
                statement = select(CustomScenario).where(
                    CustomScenario.id == req.scenario_id,
                    CustomScenario.is_active == True
                )
                custom_scenario = session.exec(statement).first()
                if custom_scenario:
                    return {
                        "id": custom_scenario.id,
                        "ai_role": custom_scenario.ai_role,
                        "scenario": custom_scenario.scenario,
                        "target_language": custom_scenario.target_language,
                        "user_level": custom_scenario.user_level
                    }
                
                # Check premade scenarios
                statement = select(PremadeScenario).where(
                    PremadeScenario.id == req.scenario_id,
                    PremadeScenario.is_active == True
                )
                premade_scenario = session.exec(statement).first()
                if premade_scenario:
                    return {
                        "id": premade_scenario.id,
                        "ai_role": premade_scenario.ai_role,
                        "scenario": premade_scenario.scenario,
                        "target_language": premade_scenario.target_language,
                        "user_level": premade_scenario.user_level
                    }

        # If no scenario ID provided, use the request parameters
        if req.ai_role and req.scenario:
            return {
                "id": str(uuid.uuid4()),
                "ai_role": req.ai_role,
                "scenario": req.scenario,
                "target_language": req.target_language or user.target_language,
                "user_level": user.user_level
            }

        return None
    except Exception as e:
        logger.error(f"Error getting scenario config: {str(e)}")
        return None

def store_message(
    session: Session,
    thread_id: str,
    user_name: str,
    role: str,
    content: str,
    scenario_id: Optional[str]
) -> ConversationHistory:
    """
    Store a message in the conversation history.
    
    Args:
        session: Database session
        thread_id: Conversation thread identifier
        user_name: Username of the participant
        role: Message sender role (user/assistant)
        content: Message content
        scenario_id: Associated scenario ID
    
    Returns:
        Stored ConversationHistory object
    """
    message = ConversationHistory(
        thread_id=thread_id,
        user_name=user_name,
        message_id=str(uuid.uuid4()),
        role=role,
        content=content,
        timestamp=datetime.now().isoformat(),
        scenario_id=scenario_id
    )
    session.add(message)
    session.commit()
    return message

def get_conversation_history(
    session: Session,
    thread_id: str
) -> List[ConversationHistory]:
    """
    Retrieve conversation history for a thread.
    
    Args:
        session: Database session
        thread_id: Conversation thread identifier
    
    Returns:
        List of ConversationHistory objects
    
    Raises:
        HTTPException: If no history found
    """
    conversation_history = session.exec(
        select(ConversationHistory)
        .where(ConversationHistory.thread_id == thread_id)
        .order_by(ConversationHistory.timestamp)
    ).all()

    if not conversation_history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No conversation history found"
        )
    return conversation_history

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

