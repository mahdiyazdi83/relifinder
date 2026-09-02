import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from oracle_relationship_discovery.gui.schemas.errors import ApiErrorDetail, ApiErrorResponse

LOGGER = logging.getLogger(__name__)


class ApiProblem(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


SAFE_HTTP_MESSAGES = {
    400: "The request is invalid.",
    401: "Authentication is required.",
    403: "The request is not permitted.",
    404: "Not Found",
    405: "The request method is not supported.",
    409: "The request conflicts with the current state.",
}


def _response(status_code: int, code: str, message: str) -> JSONResponse:
    payload = ApiErrorResponse(error=ApiErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiProblem)
    async def api_problem(_request: Request, exc: ApiProblem) -> JSONResponse:
        return _response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        message = SAFE_HTTP_MESSAGES.get(exc.status_code, "The request could not be completed.")
        return _response(exc.status_code, "http_error", message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return _response(422, "validation_error", "The request contains invalid data.")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        LOGGER.error(
            "Unhandled GUI API error on %s (type=%s)",
            request.url.path,
            type(exc).__name__,
        )
        return _response(500, "internal_error", "An unexpected local API error occurred.")
