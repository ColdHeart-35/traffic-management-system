"""One error shape for the whole API: {"error": "<code>", "detail": "<message>"}."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class TMSError(Exception):
    status_code = 400
    code = "error"

    def __init__(self, detail: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(detail)
        self.detail = detail
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class CommandError(TMSError):
    status_code = 400
    code = "invalid_command"


class AuthError(TMSError):
    status_code = 401
    code = "unauthorised"


class ForbiddenError(TMSError):
    status_code = 403
    code = "forbidden"


class NotFoundError(TMSError):
    status_code = 404
    code = "not_found"


class InterlockError(TMSError):
    status_code = 409
    code = "interlock_conflict"


class ValidationFailure(TMSError):
    status_code = 422
    code = "validation_failed"


def _body(code: str, detail) -> dict:
    return {"error": code, "detail": detail}


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(TMSError)
    async def _tms_error(_: Request, exc: TMSError):
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        errors = exc.errors()
        # Malformed JSON is a 400 (invalid payload); well-formed JSON with bad values is a 422.
        if any(e.get("type") == "json_invalid" for e in errors):
            return JSONResponse(status_code=400, content=_body("invalid_payload", "Request body is not valid JSON"))
        detail = [
            {"field": ".".join(str(p) for p in e.get("loc", []) if p != "body"), "message": e.get("msg", "")}
            for e in errors
        ]
        return JSONResponse(status_code=422, content=_body("validation_failed", detail))
