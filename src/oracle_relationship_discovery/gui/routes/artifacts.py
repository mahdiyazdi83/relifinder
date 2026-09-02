from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse

from oracle_relationship_discovery.gui.schemas.artifacts import ArtifactListResponse
from oracle_relationship_discovery.gui.schemas.errors import ApiErrorResponse
from oracle_relationship_discovery.gui.services.artifacts import ArtifactService

router = APIRouter(prefix="/runs/{run_id}/artifacts", tags=["artifacts"])
ERROR_RESPONSES = {code: {"model": ApiErrorResponse} for code in (404, 409, 422)}


def get_artifact_service(request: Request) -> ArtifactService:
    return request.app.state.artifact_service


@router.get("", response_model=ArtifactListResponse, responses=ERROR_RESPONSES)
def list_artifacts(request: Request, run_id: str) -> ArtifactListResponse:
    return get_artifact_service(request).list(run_id)


@router.get("/{artifact_id}", response_class=FileResponse, responses=ERROR_RESPONSES)
def get_artifact(
    request: Request,
    run_id: str,
    artifact_id: str,
    download: bool = Query(default=False),
) -> FileResponse:
    artifact = get_artifact_service(request).resolve(run_id, artifact_id)
    disposition = "attachment" if download or artifact.metadata.type == "csv" else "inline"
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Content-Disposition": f'{disposition}; filename="{artifact.metadata.filename}"',
    }
    if artifact.metadata.type == "html":
        headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "img-src data:; connect-src 'none'; object-src 'none'; base-uri 'none'; "
            "form-action 'none'; frame-ancestors 'none'"
        )
    return FileResponse(
        artifact.path,
        media_type=artifact.media_type,
        filename=None,
        headers=headers,
    )
