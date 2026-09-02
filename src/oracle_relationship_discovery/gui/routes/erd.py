from fastapi import APIRouter, Request

from oracle_relationship_discovery.gui.schemas.erd import ErdGraphResponse
from oracle_relationship_discovery.gui.schemas.errors import ApiErrorResponse
from oracle_relationship_discovery.gui.services.results import RelationshipResultsService

router = APIRouter(prefix="/runs/{run_id}/erd", tags=["erd"])
ERD_ERROR_RESPONSES = {code: {"model": ApiErrorResponse} for code in (404, 409, 422)}


def get_results_service(request: Request) -> RelationshipResultsService:
    return request.app.state.results_service


@router.get("", response_model=ErdGraphResponse, responses=ERD_ERROR_RESPONSES)
def erd_graph(request: Request, run_id: str) -> ErdGraphResponse:
    return get_results_service(request).graph(run_id)
