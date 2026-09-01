from fastapi import APIRouter, Header, Query, Request, status
from fastapi.responses import StreamingResponse

from gui.api.schemas.errors import ApiErrorResponse
from gui.api.schemas.runs import (
    RunCancelResponse,
    RunCreateRequest,
    RunCreateResponse,
    RunStatusResponse,
)
from gui.api.services.runs import RunService

router = APIRouter(prefix="/runs", tags=["runs"])
RUN_ERROR_RESPONSES = {code: {"model": ApiErrorResponse} for code in (400, 404, 409, 422)}


def get_run_service(request: Request) -> RunService:
    return request.app.state.run_service


@router.post(
    "",
    response_model=RunCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=RUN_ERROR_RESPONSES,
)
def create_run(request: Request, payload: RunCreateRequest) -> RunCreateResponse:
    return get_run_service(request).create(payload)


@router.get(
    "/{run_id}",
    response_model=RunStatusResponse,
    responses=RUN_ERROR_RESPONSES,
)
def get_run(request: Request, run_id: str) -> RunStatusResponse:
    return get_run_service(request).get(run_id)


@router.get(
    "/{run_id}/events",
    responses={404: {"model": ApiErrorResponse}},
)
def stream_run_events(
    request: Request,
    run_id: str,
    after: int = Query(default=-1, ge=-1),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    service = get_run_service(request)
    service.get(run_id)
    cursor = after
    if last_event_id and last_event_id.isdigit():
        cursor = max(cursor, int(last_event_id))
    return StreamingResponse(
        service.events(run_id, cursor),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/{run_id}/cancel",
    response_model=RunCancelResponse,
    responses=RUN_ERROR_RESPONSES,
)
def cancel_run(request: Request, run_id: str) -> RunCancelResponse:
    return get_run_service(request).cancel(run_id)
