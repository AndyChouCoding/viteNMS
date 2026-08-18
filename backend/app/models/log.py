from pydantic import BaseModel


class LogEntry(BaseModel):
    id: int
    title: str
    description: str
    created_at: str
