"""A rule the request broke, explained for a person: 422 with {message, field}.

Raise FieldError anywhere in a request; the handler registered in main.py turns it into the
response, so endpoints don't catch and format errors themselves.
"""

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class FieldErrorOut(BaseModel):
    message: str
    field: str | None  # the form field to point at, if any


class FieldError(Exception):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


async def field_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, FieldError)
    return JSONResponse(status_code=422, content=FieldErrorOut(message=str(exc), field=exc.field).model_dump())


async def validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """FastAPI's own 422 (a body or query that doesn't match its schema), plus the same {message, field}
    as FieldError, so clients handle one shape. FastAPI's standard `detail` list is kept, so the
    documented HTTPValidationError schema still holds."""
    assert isinstance(exc, RequestValidationError)
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = [str(part) for part in first.get("loc", ()) if part not in ("body", "query", "path")]
    message = first.get("msg", "Check the fields and try again.")
    return JSONResponse(
        status_code=422,
        content={"message": f"{message}.", "field": loc[-1] if loc else None, "detail": jsonable_encoder(errors)},
    )


# For endpoint decorators: documents the 422 shape in the OpenAPI schema (and so in the TS client).
FIELD_ERROR_RESPONSE = {422: {"model": FieldErrorOut}}
