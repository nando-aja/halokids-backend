from pydantic import BaseModel, Field


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    session_id: str | None = Field(default=None, min_length=8, max_length=64)


class AIChatResponse(BaseModel):
    session_id: str
    message: str
    intent: str
    actions: list[str] = Field(default_factory=list)
    data: dict | None = None
