from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class QuestionStatus(StrEnum):
    NEW = "new"
    PINNED = "pinned"
    ANSWERED = "answered"
    SKIPPED = "skipped"


class ChatMessage(BaseModel):
    id: str
    channel_id: str
    user_id: str
    display_name: str
    text: str = Field(min_length=1, max_length=500)
    timestamp: datetime
    received_at: datetime


class Topic(BaseModel):
    id: str
    title: str
    summary: str
    message_ids: list[str]
    message_count: int = Field(ge=1)
    updated_at: datetime


class QuestionGroup(BaseModel):
    id: str
    representative_question: str
    message_ids: list[str]
    unique_viewer_count: int = Field(ge=1)
    priority_score: float = Field(ge=0, le=1)
    status: QuestionStatus = QuestionStatus.NEW
    last_seen_at: datetime


class Spotlight(BaseModel):
    question_id: str | None = None
    question_text: str | None = None
    viewer_count: int = Field(default=0, ge=0)
    updated_at: datetime


class DashboardState(BaseModel):
    messages: list[ChatMessage]
    topics: list[Topic]
    questions: list[QuestionGroup]
    spotlight: Spotlight
    updated_at: datetime


class SimulationRequest(BaseModel):
    scenario: str = "mixed"

