from typing import Optional
from sqlmodel import SQLModel, Field, create_engine, Session

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_name: str = Field(index=True, unique=True)
    user_level: str
    target_language: str
    created_at: Optional[str] = None  

sqlite_file_name = "users.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=True)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
