from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.internal import router as internal_router
from app.api.v1.policy import router as policy_router
from app.api.v1.public import router as public_router
from app.core.config import get_settings
from app.core.errors import (
    ApiError,
    api_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from app.core.request_id import RequestIdMiddleware

app = FastAPI(title="Tourism Decision Support System API", version="0.1.0")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Content-Type",
        "If-Match",
        "Idempotency-Key",
        "X-Demo-User",
        "X-Request-ID",
    ],
)
app.add_middleware(RequestIdMiddleware)
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(404, http_error_handler)
app.add_exception_handler(Exception, unexpected_error_handler)


@app.get("/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def readiness() -> dict[str, str]:
    return {"status": "ok", "repository": "available"}


app.include_router(public_router, prefix="/api/v1/public", tags=["public"])
app.include_router(internal_router, prefix="/api/v1/internal", tags=["internal"])
app.include_router(policy_router, prefix="/api/v1/internal", tags=["policy"])
