from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, Request

from app.core.errors import ApiError


@dataclass(frozen=True)
class DemoIdentity:
    subject: str
    display_name: str
    permissions: frozenset[str]


_USERS = {
    "admin": DemoIdentity("demo-admin", "Demo Administrator", frozenset({"*"})),
    "editor": DemoIdentity(
        "demo-editor",
        "Demo Data Editor",
        frozenset(
            {
                "destinations:read",
                "destinations:write",
                "observations:read",
                "observations:write",
                "imports:create",
                "imports:read",
                "imports:validate",
                "audit:read",
                "policy:simulate",
                "policy:read",
                "recommendations:write",
                "recommendations:read",
                "reports:create",
                "reports:read",
            }
        ),
    ),
    "viewer": DemoIdentity(
        "demo-viewer", "Demo Viewer", frozenset({"destinations:read", "observations:read"})
    ),
}


def current_identity(request: Request) -> DemoIdentity:
    user = request.headers.get("x-demo-user")
    identity = _USERS.get(user or "")
    if identity is None:
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "A valid application session is required.")
    return identity


def require_permission(permission: str) -> Callable:
    def dependency(identity: DemoIdentity = Depends(current_identity)) -> DemoIdentity:
        if "*" not in identity.permissions and permission not in identity.permissions:
            raise ApiError(
                403,
                "FORBIDDEN",
                "The current user lacks the required permission.",
                [{"field": "permission", "reason": permission}],
            )
        return identity

    return dependency
