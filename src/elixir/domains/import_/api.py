import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from elixir.domains.import_.schemas import (
    ColumnMappingConfirmRequest,
    ImportJobDetailResponse,
    ImportJobResponse,
    ImportSourceType,
    ImportStartResponse,
)
from elixir.domains.import_.services import ImportService
from elixir.runtime.dependencies import RequestCtx, get_db_session

router = APIRouter()


def get_import_service(
    request: Request,
    db=Depends(get_db_session),
) -> ImportService:
    return ImportService(db=db, settings=request.app.state.settings)


ImportSvc = Annotated[ImportService, Depends(get_import_service)]


@router.post(
    "/upload",
    response_model=ImportStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_import_file(
    ctx: RequestCtx,
    svc: ImportSvc,
    request: Request,
    file: UploadFile = File(...),
    source_type: ImportSourceType = Form(...),
    original_filename: str | None = Form(default=None),
):
    file_content = await file.read()
    fname = original_filename or file.filename
    return await svc.upload_file(
        user_id=ctx.user_id,
        file_content=file_content,
        source_type=source_type,
        original_filename=fname,
        storage_client=request.app.state.storage,
        temporal_client=request.app.state.temporal_client,
    )


@router.get("", response_model=list[ImportJobResponse])
async def list_import_jobs(
    ctx: RequestCtx,
    svc: ImportSvc,
):
    return await svc.list_jobs(ctx.user_id)


@router.get("/{job_id}", response_model=ImportJobDetailResponse)
async def get_import_job(
    job_id: uuid.UUID,
    ctx: RequestCtx,
    svc: ImportSvc,
):
    return await svc.get_job_status(ctx.user_id, job_id)


@router.get("/{job_id}/stream")
async def stream_import_events(job_id: uuid.UUID):
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


@router.post("/{job_id}/confirm-mapping")
async def confirm_mapping(
    job_id: uuid.UUID,
    body: ColumnMappingConfirmRequest,
    ctx: RequestCtx,
    svc: ImportSvc,
    request: Request,
):
    await svc.confirm_mapping(
        user_id=ctx.user_id,
        job_id=job_id,
        mappings=[mapping.model_dump() for mapping in body.mappings],
        temporal_client=request.app.state.temporal_client,
    )
    return {"status": "processing"}


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_import_job(
    job_id: uuid.UUID,
    ctx: RequestCtx,
    svc: ImportSvc,
):
    await svc.delete_import(user_id=ctx.user_id, job_id=job_id)
