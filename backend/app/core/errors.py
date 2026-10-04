"""Errores públicos sanitizados, compatibles con OpenAPI 0.1.1."""

from uuid import UUID, uuid4

from fastapi import Request


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, *, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retry_after = retry_after


def request_id(request: Request) -> UUID:
    return getattr(request.state, "request_id", None) or uuid4()


def error_content(request: Request, code: str, message: str, details: list[dict] | None = None) -> dict:
    return {"code": code, "message": message, "details": details or [], "request_id": str(request_id(request))}
