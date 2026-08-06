from pydantic import BaseModel


class PingResult(BaseModel):
    success: bool
    latency_ms: float | None = None
