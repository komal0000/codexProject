from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ResearchBrief(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    product_name: str
    product_description: str
    target_customer_guess: str
    pricing_model: str
    competitor_examples: list[str]
    research_goal: str


ResearchMode = Literal["fast_draft", "free_first", "grounded_paid"]


class SourcePage(BaseModel):
    title: str
    url: str
    source: str
    query: str


class ResearchJobRequest(ResearchBrief):
    mode: ResearchMode = "free_first"


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    mode: ResearchMode = "free_first"
    stage: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None


class JobListItem(JobStatus):
    product_name: str


class JobCreateResponse(BaseModel):
    job_id: str
    status: Literal["queued"]
    mode: ResearchMode = "free_first"


class ResearchResult(BaseModel):
    job_id: str
    brief: ResearchBrief
    mode: ResearchMode = "free_first"
    tabs: dict[str, list[dict[str, Any]]]
    strategy_summary: str
    validation: dict[str, Any]
    sources_count: int
    live_signals_count: int
    citations_count: int = 0
    source_pages: list[SourcePage] = Field(default_factory=list)
    created_at: datetime


class JobRecord(BaseModel):
    job_id: str
    brief: ResearchBrief
    status: Literal["queued", "running", "done", "failed"]
    mode: ResearchMode = "free_first"
    stage: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    result: ResearchResult | None = None
    workspace: str
