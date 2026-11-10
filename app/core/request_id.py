from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send


def _valid_request_id(value: str | None) -> bool:
    if not value or len(value) > 128:
        return False
    return all(character.isalnum() or character in "._:-" for character in value)


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = next(
            (
                value.decode()
                for key, value in scope.get("headers", [])
                if key.lower() == b"x-request-id"
            ),
            None,
        )
        request_id = incoming if _valid_request_id(incoming) else str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_request_id)
