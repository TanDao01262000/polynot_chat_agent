from fastapi import FastAPI
from .chat_agent import chat_agent
from .models import ChatRequest


# --- FastAPI app ---
app = FastAPI()

@app.get('/')
def hello():
    return 'fk tk Danh'


@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    config = {
        "configurable": {
            "thread_id": req.thread_id,
            "user_id": req.user_id
        }
    }

    new_state = {
        "messages": [{"role": "user", "content": req.user_input}],
        "user_name": req.user_name,
        "user_level": req.user_level,
        "ai_role": req.ai_role,
        "scenario": req.scenario,
        "target_language": req.target_language,
    }

    result = chat_agent.invoke(new_state, config=config)
    response = result["messages"][-1].content

    return {
        "thread_id": req.thread_id,
        "response": response
    }
