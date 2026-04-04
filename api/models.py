from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ResearchBrief(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    product_name: str
    product_description: str
    target_customer_guess: str
    pricing_model: str
    competitor_examples: list[str]
    research_goal: str


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None


class JobListItem(JobStatus):
    product_name: str


class JobCreateResponse(BaseModel):
    job_id: str
    status: Literal["queued"]


class ResearchResult(BaseModel):
    job_id: str
    brief: ResearchBrief
    tabs: dict[str, list[dict[str, Any]]]
    strategy_summary: str
    validation: dict[str, Any]
    sources_count: int
    live_signals_count: int
    created_at: datetime


class JobRecord(BaseModel):
    job_id: str
    brief: ResearchBrief
    status: Literal["queued", "running", "done", "failed"]
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    result: ResearchResult | None = None
    workspace: str
