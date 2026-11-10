from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: list[dict[str, str]] | None = None
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []
        super().__init__(message)


def error_payload(
    request: Request, code: str, message: str, details: list[dict[str, str]] | None = None
) -> dict:
    request_id = request.headers.get("x-request-id") or getattr(request.state, "request_id", "")
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "request_id": request_id,
        }
    }


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        content=error_payload(request, exc.code, exc.message, exc.details),
        status_code=exc.status_code,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"field": ".".join(str(part) for part in item["loc"]), "reason": item["msg"]}
        for item in exc.errors()
    ]
    return JSONResponse(
        content=error_payload(request, "VALIDATION_ERROR", "The request is invalid.", details),
        status_code=422,
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    return JSONResponse(
        content=error_payload(request, code, str(exc.detail)), status_code=exc.status_code
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        content=error_payload(request, "INTERNAL_ERROR", "An unexpected error occurred."),
        status_code=500,
    )
