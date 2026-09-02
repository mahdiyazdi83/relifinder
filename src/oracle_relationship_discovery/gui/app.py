from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from oracle_relationship_discovery.gui.errors import install_error_handlers
from oracle_relationship_discovery.gui.frontend import mount_frontend
from oracle_relationship_discovery.gui.routes.artifacts import router as artifacts_router
from oracle_relationship_discovery.gui.routes.connections import router as connections_router
from oracle_relationship_discovery.gui.routes.erd import router as erd_router
from oracle_relationship_discovery.gui.routes.health import router as health_router
from oracle_relationship_discovery.gui.routes.relationships import router as relationships_router
from oracle_relationship_discovery.gui.routes.runs import router as runs_router
from oracle_relationship_discovery.gui.services.artifacts import ArtifactService
from oracle_relationship_discovery.gui.services.connection_sessions import ConnectionSessionStore
from oracle_relationship_discovery.gui.services.connections import ConnectionService
from oracle_relationship_discovery.gui.services.oracle_gateway import (
    CoreOracleGateway,
    OracleGateway,
)
from oracle_relationship_discovery.gui.services.results import RelationshipResultsService
from oracle_relationship_discovery.gui.services.runs import AnalysisExecutor, RunService


def create_app(
    *,
    gateway: OracleGateway | None = None,
    sessions: ConnectionSessionStore | None = None,
    analysis_executor: AnalysisExecutor | None = None,
    serve_frontend: bool = False,
    frontend_dir: Path | None = None,
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
    if serve_frontend:
        mount_frontend(app, frontend_dir)
    return app


app = create_app()
