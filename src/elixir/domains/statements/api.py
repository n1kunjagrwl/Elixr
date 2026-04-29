import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, status
from fastapi.responses import StreamingResponse

from elixir.domains.statements.schemas import (
    ClassifyRowRequest,
    JobResumeResponse,
    RawRowResponse,
    UploadResponse,
    UploadStartResponse,
    UploadStatusResponse,
)
from elixir.domains.statements.services import StatementsService
from elixir.runtime.dependencies import RequestCtx, get_db_session

router = APIRouter()


# ── Service factory ───────────────────────────────────────────────────────────


def get_statements_service(
    request: Request,
    db=Depends(get_db_session),
) -> StatementsService:
    return StatementsService(
        db=db,
        settings=request.app.state.settings,
    )


StatementsSvc = Annotated[StatementsService, Depends(get_statements_service)]


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/upload",
    response_model=UploadStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_statement(
    ctx: RequestCtx,
    svc: StatementsSvc,
    request: Request,
    file: UploadFile = File(...),
    account_id: uuid.UUID = Form(...),
    account_kind: str = Form(...),
    file_type: str = Form(...),
    original_filename: str | None = Form(default=None),
):
    """Upload a bank or credit card statement file to begin processing."""
    file_content = await file.read()
    fname = original_filename or file.filename

    storage_client = request.app.state.storage
    temporal_client = request.app.state.temporal_client

    return await svc.upload_statement(
        user_id=ctx.user_id,
        account_id=account_id,
        account_kind=account_kind,
        file_content=file_content,
        file_type=file_type,
        original_filename=fname,
        storage_client=storage_client,
        temporal_client=temporal_client,
    )


@router.get("", response_model=list[UploadResponse])
async def list_uploads(ctx: RequestCtx, svc: StatementsSvc):
    """List all statement uploads for the authenticated user."""
    return await svc.list_uploads(ctx.user_id)


@router.get("/jobs/{job_id}", response_model=JobResumeResponse)
async def get_job_resume(
    job_id: uuid.UUID,
    ctx: RequestCtx,
    svc: StatementsSvc,
):
    """Return extraction job status and all rows — used to resume classification."""
    return await svc.get_job_resume(ctx.user_id, job_id)


@router.get("/{upload_id}", response_model=UploadStatusResponse)
async def get_upload_status(
    upload_id: uuid.UUID,
    ctx: RequestCtx,
    svc: StatementsSvc,
):
    """Get the status of a specific upload and its associated extraction job."""
    return await svc.get_upload_status(ctx.user_id, upload_id)


@router.get("/{job_id}/stream")
async def stream_job_events(
    job_id: uuid.UUID,
    ctx: RequestCtx,
):
    """
    SSE stream for real-time job progress updates.

    Stub implementation: yields a single 'connected' event.
    Full queue-backed SSE will be added in a future iteration.
    """
    import json

    async def _event_generator():
        connected_event = json.dumps({"type": "connected", "job_id": str(job_id)})
        yield f"data: {connected_event}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{job_id}/rows/{row_id}/classify")
async def classify_row(
    job_id: uuid.UUID,
    row_id: uuid.UUID,
    body: ClassifyRowRequest,
    ctx: RequestCtx,
    svc: StatementsSvc,
    request: Request,
):
    """Submit a user classification for a single raw extracted row."""
    temporal_client = request.app.state.temporal_client
    await svc.classify_row(
        user_id=ctx.user_id,
        job_id=job_id,
        row_id=row_id,
        data=body,
        temporal_client=temporal_client,
    )
    return {"status": "classified"}


@router.get("/{job_id}/rows", response_model=list[RawRowResponse])
async def list_rows(
    job_id: uuid.UUID,
    ctx: RequestCtx,
    svc: StatementsSvc,
):
    """List all raw extracted rows for a job (used to resume classification UI)."""
    return await svc.get_rows_for_resume(ctx.user_id, job_id)
