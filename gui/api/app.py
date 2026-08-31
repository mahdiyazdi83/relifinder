from fastapi import FastAPI

from gui.api.errors import install_error_handlers
from gui.api.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="ReliFinder GUI API",
        description="Local orchestration boundary for the ReliFinder GUI.",
        version="0.1.0",
    )
    install_error_handlers(app)
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()
