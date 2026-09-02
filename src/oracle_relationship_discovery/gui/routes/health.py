from fastapi import APIRouter

from oracle_relationship_discovery.gui.schemas.health import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", application="relifinder")
