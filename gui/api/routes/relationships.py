from fastapi import APIRouter, Request

from gui.api.schemas.errors import ApiErrorResponse
from gui.api.schemas.relationships import RelationshipDetail, RelationshipListResponse
from gui.api.services.results import RelationshipResultsService

router = APIRouter(prefix="/runs/{run_id}/relationships", tags=["relationships"])
RESULT_ERROR_RESPONSES = {code: {"model": ApiErrorResponse} for code in (404, 409, 422)}


def get_results_service(request: Request) -> RelationshipResultsService:
    return request.app.state.results_service


@router.get(
    "",
    response_model=RelationshipListResponse,
    responses=RESULT_ERROR_RESPONSES,
)
def list_relationships(request: Request, run_id: str) -> RelationshipListResponse:
    return get_results_service(request).list(run_id)


@router.get(
    "/{relationship_id}",
    response_model=RelationshipDetail,
    responses=RESULT_ERROR_RESPONSES,
)
def relationship_detail(
    request: Request,
    run_id: str,
    relationship_id: str,
) -> RelationshipDetail:
    return get_results_service(request).detail(run_id, relationship_id)
