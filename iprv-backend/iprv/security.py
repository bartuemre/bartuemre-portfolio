"""Authenticate hosted APIs and bound uploads before multipart parsing."""

import hashlib
import hmac

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_REQUEST_BYTES = MAX_FILE_BYTES + 256 * 1024


class ApiAccessGuard:
    """A single operator token; never use a provider key or a query-string credential."""

    def __init__(self, app, token):
        self.app = app
        self.expected = hashlib.sha256(token.encode("utf-8")).digest()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)
        authorization = dict(scope.get("headers", [])).get(b"authorization", b"")
        scheme, _, value = authorization.partition(b" ")
        valid = scheme.lower() == b"bearer" and hmac.compare_digest(
            hashlib.sha256(value).digest(), self.expected
        )
        if not valid:
            return await JSONResponse(
                {"detail": "Workspace access key required"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
            )(scope, receive, send)
        return await self.app(scope, receive, send)


class RequestBodyLimit:
    def __init__(self, app, limit=MAX_REQUEST_BYTES):
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        length = headers.get(b"content-length")
        if length is not None:
            try:
                too_large = int(length) > self.limit or int(length) < 0
            except ValueError:
                return await JSONResponse({"detail": "Invalid Content-Length"}, 400)(
                    scope, receive, send
                )
            if too_large:
                return await JSONResponse({"detail": "Request body exceeds upload limit"}, 413)(
                    scope, receive, send
                )
        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > self.limit:
                    raise HTTPException(413, "Request body exceeds upload limit")
            return message

        await self.app(scope, limited_receive, send)
