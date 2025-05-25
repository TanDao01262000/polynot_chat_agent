from pydantic import BaseModel

class Message(BaseModel):
    role: str
    content: str


class MessageRequest(BaseModel):
    user_id: int
    message_id: int


class Conversation(BaseModel):
    messages: list[Message]

class ChatRequest(BaseModel):
    thread_id: str
    user_id: str
    user_input: str
    user_name: str
    user_level: str
    ai_role: str
    scenario: str
    target_language: str