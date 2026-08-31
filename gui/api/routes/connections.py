from fastapi import APIRouter, Request, Response, status

from gui.api.schemas.connections import (
    ConnectionCreateRequest,
    ConnectionResponse,
    SchemaListResponse,
)
from gui.api.schemas.errors import ApiErrorResponse
from gui.api.services.connections import ConnectionService

router = APIRouter(prefix="/connections", tags=["connections"])
CONNECTION_ERROR_RESPONSES = {
    code: {"model": ApiErrorResponse} for code in (400, 401, 403, 422, 502, 503, 504)
}
SESSION_ERROR_RESPONSES = {
    404: {"model": ApiErrorResponse},
    422: {"model": ApiErrorResponse},
}


def get_connection_service(request: Request) -> ConnectionService:
    return request.app.state.connection_service


@router.post(
    "",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=CONNECTION_ERROR_RESPONSES,
)
def create_connection(request: Request, payload: ConnectionCreateRequest) -> ConnectionResponse:
    return get_connection_service(request).create(payload)


@router.get(
    "/{connection_id}/schemas",
    response_model=SchemaListResponse,
    responses=SESSION_ERROR_RESPONSES,
)
def list_schemas(request: Request, connection_id: str) -> SchemaListResponse:
    return get_connection_service(request).list_schemas(connection_id)


@router.delete(
    "/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=SESSION_ERROR_RESPONSES,
)
def disconnect(request: Request, connection_id: str) -> Response:
    get_connection_service(request).disconnect(connection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
