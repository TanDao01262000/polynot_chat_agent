from fastapi import FastAPI, HTTPException
from .chat_agent import chat_agent
from .models import ChatRequest, FeedbackRequest
from .feedback_tool import feedback_tool
import uuid
import os

os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "polynot")
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"

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

# --- /chat endpoint ---
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

# --- /feedback endpoint ---
@app.post("/feedback")
def get_feedback(req: FeedbackRequest):
    response = feedback_tool(
        user_name=req.user_name,
        user_level=req.user_level,
        target_language=req.target_language,
        scenario=req.scenario,
        messages=req.messages
    )
    return {"response": response}
