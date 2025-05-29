from fastapi import FastAPI, HTTPException, Depends, status
from sqlmodel import create_engine, Session, SQLModel, select
import uuid
import os
import json
import logging
from typing import List, Optional, Dict
from datetime import datetime

from .chat_agent import chat_agent
from .models import (
    ChatRequest, Feedback, ConversationHistory, User,
    UserLevel
)
from .feedback_tool import feedback_tool
from .level_evaluator_tool import level_evaluator_tool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Environment Variables for LangChain ---
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "polynot")
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"

# --- Database Setup ---
sqlite_url = f"sqlite:///users.db"
engine = create_engine(sqlite_url, echo=True)

def create_db_and_tables():
    """Create database tables on startup."""
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created successfully")

def get_session():
    """Dependency for database session."""
    with Session(engine) as session:
        yield session

# --- FastAPI app ---
app = FastAPI(
    title="PolyNot Language Learning API",
    description="API for language learning conversations and feedback",
    version="1.0.0"
)

# --- Predefined Scenario List ---
PREMADE_SCENARIOS = [
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

# --- Startup Event ---
@app.on_event("startup")
def on_startup():
    """Initialize database on startup."""
    create_db_and_tables()

# --- User Management Endpoints ---
@app.post("/users/", response_model=User, status_code=status.HTTP_201_CREATED)
def create_user(user: User, session: Session = Depends(get_session)):
    """Create a new user."""
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

# --- Chat Endpoint ---
@app.post("/chat")
def chat_endpoint(req: ChatRequest, session: Session = Depends(get_session)):
    """Handle chat interactions."""
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

        # Process chat
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

# --- Feedback Endpoint ---
@app.post("/feedback")
def get_feedback(
    user_name: str,
    thread_id: str,
    session: Session = Depends(get_session)
):
    """Get feedback for a conversation."""
    try:
        # Get user and conversation history
        user = get_user(user_name, session)
        conversation_history = get_conversation_history(session, thread_id)
        
        # Get feedback
        feedback = feedback_tool(
            user_name=user_name,
            user_level=user.user_level,
            target_language=user.target_language,
            scenario=conversation_history[0].scenario_id or "",
            messages=[{
                "role": msg.role,
                "content": msg.content
            } for msg in conversation_history]
        )

        return json.loads(feedback)
    except Exception as e:
        logger.error(f"Error getting feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get feedback"
        )

# --- Level Evaluation Endpoint ---
@app.post("/evaluate")
def evaluate_level(
    user_name: str,
    thread_id: str,
    session: Session = Depends(get_session)
):
    """Evaluate user's language level."""
    try:
        # Get user and conversation history
        user = get_user(user_name, session)
        conversation_history = get_conversation_history(session, thread_id)
        
        # Get evaluation
        evaluation = level_evaluator_tool(
            user_name=user_name,
            target_language=user.target_language,
            scenario=conversation_history[0].scenario_id or "",
            messages=[{
                "role": msg.role,
                "content": msg.content
            } for msg in conversation_history]
        )

        return json.loads(evaluation)
    except Exception as e:
        logger.error(f"Error evaluating level: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate level"
        )

# --- Helper Functions ---
def get_scenario_config(req: ChatRequest, user: User) -> Optional[Dict]:
    """Get scenario configuration based on request."""
    if req.scenario_id:
        return next((s for s in PREMADE_SCENARIOS if s["id"] == req.scenario_id), None)
    return {
        "ai_role": req.ai_role,
        "scenario": req.scenario,
        "target_language": req.target_language,
        "user_level": user.user_level
    }

def store_message(
    session: Session,
    thread_id: str,
    user_name: str,
    role: str,
    content: str,
    scenario_id: Optional[str]
) -> ConversationHistory:
    """Store a message in the conversation history."""
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
    """Get conversation history for a thread."""
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
    """Process chat request and return response."""
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

