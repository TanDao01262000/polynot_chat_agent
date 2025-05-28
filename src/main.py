from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import create_engine, Session, SQLModel, select
import uuid
import os
import json

from .chat_agent import chat_agent
from .models import ChatRequest
from .user_models import User

# --- Environment Variables for LangChain ---
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "polynot")
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"

# --- Database Setup ---
sqlite_url = f"sqlite:///users.db"
engine = create_engine(sqlite_url, echo=True)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

# --- FastAPI app ---
app = FastAPI()

# --- Predefined Scenario List ---
PREMADE_SCENARIOS = [
    {
        "id": "coffee_shop",
        "ai_role": "barista",
        "scenario": "Ordering a drink at a coffee shop",
        "target_language": "English",
        "user_level": "Beginner"
    },
    {
        "id": "job_interview",
        "ai_role": "Hiring Manager",
        "scenario": "Job interview for a marketing assistant position",
        "target_language": "English",
        "user_level": "Intermediate"
    },
    {
        "id": "first_date",
        "ai_role": "date partner",
        "scenario": "First date at a casual restaurant",
        "target_language": "English",
        "user_level": "Intermediate"
    }
]

# --- Startup Event: Create DB Tables ---
@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# --- User Endpoints ---
@app.post("/users/", response_model=User)
def create_user(user: User, session: Session = Depends(get_session)):
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

@app.get("/users/{user_name}", response_model=User)
def read_user(user_name: str, session: Session = Depends(get_session)):
    statement = select(User).where(User.user_name == user_name)
    user = session.exec(statement).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.patch("/users/{user_name}", response_model=User)
def update_user_level(user_name: str, user_level: str, session: Session = Depends(get_session)):
    statement = select(User).where(User.user_name == user_name)
    user = session.exec(statement).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.user_level = user_level
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

# --- Chat Endpoint ---
@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    # Use scenario_id if provided
    if req.scenario_id:
        scenario = next((s for s in PREMADE_SCENARIOS if s["id"] == req.scenario_id), None)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario ID not found")
    else:
        # Fall back to custom values
        scenario = {
            "ai_role": req.ai_role,
            "scenario": req.scenario,
            "target_language": req.target_language,
            "user_level": req.user_level
        }

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
    response = result["messages"][-1].content

    return {
        "thread_id": req.thread_id,
        "response": response
    }

