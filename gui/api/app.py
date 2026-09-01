from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from gui.api.errors import install_error_handlers
from gui.api.routes.artifacts import router as artifacts_router
from gui.api.routes.connections import router as connections_router
from gui.api.routes.erd import router as erd_router
from gui.api.routes.health import router as health_router
from gui.api.routes.relationships import router as relationships_router
from gui.api.routes.runs import router as runs_router
from gui.api.services.artifacts import ArtifactService
from gui.api.services.connection_sessions import ConnectionSessionStore
from gui.api.services.connections import ConnectionService
from gui.api.services.oracle_gateway import CoreOracleGateway, OracleGateway
from gui.api.services.results import RelationshipResultsService
from gui.api.services.runs import AnalysisExecutor, RunService


def create_app(
    *,
    gateway: OracleGateway | None = None,
    sessions: ConnectionSessionStore | None = None,
    analysis_executor: AnalysisExecutor | None = None,
) -> FastAPI:
    session_store = sessions or ConnectionSessionStore()
    connection_service = ConnectionService(
        gateway or CoreOracleGateway(),
        session_store,
    )
    run_service = RunService(session_store, analysis_executor)
    results_service = RelationshipResultsService(run_service)
    artifact_service = ArtifactService(run_service)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        run_service.close()
        results_service.clear()
        connection_service.close()

    app = FastAPI(
        title="ReliFinder GUI API",
        description="Local orchestration boundary for the ReliFinder GUI.",
        version="0.6.0",
        lifespan=lifespan,
    )
    app.state.artifact_service = artifact_service
    app.state.connection_service = connection_service
    app.state.run_service = run_service
    app.state.results_service = results_service
    install_error_handlers(app)
    app.include_router(health_router, prefix="/api")
    app.include_router(artifacts_router, prefix="/api")
    app.include_router(erd_router, prefix="/api")
    app.include_router(connections_router, prefix="/api")
    app.include_router(runs_router, prefix="/api")
    app.include_router(relationships_router, prefix="/api")
    return app


app = create_app()
