from __future__ import annotations

import asyncio
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response, status

from api.models import JobCreateResponse, JobListItem, JobRecord, JobStatus, ResearchBrief, ResearchResult
from tools.collectors import collect_all_live_signals
from tools.nepal_market_lib import ensure_directory, run_research_pipeline, write_json

router = APIRouter()

# TODO: replace with Supabase/Redis for multi-user production.
JOB_STORE: dict[str, JobRecord] = {}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def workspace_for_job(job_id: str) -> Path:
    return ensure_directory(Path(".tmp") / "api_jobs" / job_id)


def get_job_or_404(job_id: str) -> JobRecord:
    job = JOB_STORE.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


def to_status(job: JobRecord) -> JobStatus:
    return JobStatus(
        job_id=job.job_id,
        status=job.status,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error=job.error,
    )


async def run_research_job(job_id: str, brief: ResearchBrief) -> None:
    job = get_job_or_404(job_id)
    job.status = "running"
    workspace = Path(job.workspace)
    report_dir = workspace / "report"
    try:
        write_json(workspace / "brief.json", brief.model_dump())
        live_signals = await collect_all_live_signals(brief.model_dump())
        live_path = write_json(workspace / "live_signals.json", live_signals)
        pipeline_result = await asyncio.to_thread(
            run_research_pipeline,
            workspace / "brief.json",
            [live_path],
            report_dir,
        )
        job.result = ResearchResult(
            job_id=job_id,
            brief=brief,
            tabs=pipeline_result["tabs"],
            strategy_summary=pipeline_result["summary"],
            validation=pipeline_result["validation"],
            sources_count=len(live_signals),
            live_signals_count=len(live_signals),
            created_at=job.created_at,
        )
        job.status = "done"
        job.completed_at = utc_now()
    except Exception as exc:  # pragma: no cover
        job.status = "failed"
        job.error = str(exc)
        job.completed_at = utc_now()


@router.post("/api/research", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_research_job(brief: ResearchBrief) -> JobCreateResponse:
    job_id = utc_now().strftime("%Y%m%d%H%M%S%f")
    JOB_STORE[job_id] = JobRecord(
        job_id=job_id,
        brief=brief,
        status="queued",
        created_at=utc_now(),
        workspace=str(workspace_for_job(job_id)),
    )
    asyncio.create_task(run_research_job(job_id, brief))
    return JobCreateResponse(job_id=job_id, status="queued")


@router.get("/api/research", response_model=list[JobListItem])
async def list_research_jobs() -> list[JobListItem]:
    jobs = sorted(JOB_STORE.values(), key=lambda item: item.created_at, reverse=True)
    return [
        JobListItem(
            job_id=job.job_id,
            product_name=job.brief.product_name,
            status=job.status,
            created_at=job.created_at,
            completed_at=job.completed_at,
            error=job.error,
        )
        for job in jobs
    ]


@router.get("/api/research/{job_id}", response_model=JobStatus)
async def get_research_job(job_id: str) -> JobStatus:
    return to_status(get_job_or_404(job_id))


@router.get("/api/research/{job_id}/result", response_model=ResearchResult)
async def get_research_result(job_id: str) -> ResearchResult:
    job = get_job_or_404(job_id)
    if job.status != "done" or job.result is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Research job is not complete.")
    return job.result


@router.delete("/api/research/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_research_job(job_id: str) -> Response:
    job = get_job_or_404(job_id)
    workspace = Path(job.workspace).resolve()
    temp_root = (Path.cwd() / ".tmp" / "api_jobs").resolve()
    if temp_root in workspace.parents or workspace == temp_root:
        shutil.rmtree(workspace, ignore_errors=True)
    del JOB_STORE[job_id]
    return Response(status_code=status.HTTP_204_NO_CONTENT)
