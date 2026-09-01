from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from gui.api.errors import install_error_handlers
from gui.api.routes.connections import router as connections_router
from gui.api.routes.health import router as health_router
from gui.api.routes.runs import router as runs_router
from gui.api.services.connection_sessions import ConnectionSessionStore
from gui.api.services.connections import ConnectionService
from gui.api.services.oracle_gateway import CoreOracleGateway, OracleGateway
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

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        run_service.close()
        connection_service.close()

    app = FastAPI(
        title="ReliFinder GUI API",
        description="Local orchestration boundary for the ReliFinder GUI.",
        version="0.3.0",
        lifespan=lifespan,
    )
    app.state.connection_service = connection_service
    app.state.run_service = run_service
    install_error_handlers(app)
    app.include_router(health_router, prefix="/api")
    app.include_router(connections_router, prefix="/api")
    app.include_router(runs_router, prefix="/api")
    return app


app = create_app()
