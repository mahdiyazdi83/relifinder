from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from gui.api.errors import install_error_handlers
from gui.api.routes.connections import router as connections_router
from gui.api.routes.health import router as health_router
from gui.api.services.connection_sessions import ConnectionSessionStore
from gui.api.services.connections import ConnectionService
from gui.api.services.oracle_gateway import CoreOracleGateway, OracleGateway


def create_app(
    *,
    gateway: OracleGateway | None = None,
    sessions: ConnectionSessionStore | None = None,
) -> FastAPI:
    connection_service = ConnectionService(
        gateway or CoreOracleGateway(),
        sessions or ConnectionSessionStore(),
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        connection_service.close()

    app = FastAPI(
        title="ReliFinder GUI API",
        description="Local orchestration boundary for the ReliFinder GUI.",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.state.connection_service = connection_service
    install_error_handlers(app)
    app.include_router(health_router, prefix="/api")
    app.include_router(connections_router, prefix="/api")
    return app


app = create_app()
