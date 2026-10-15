"""Request bodies for the HTTP API (responses are plain JSON built in serializers.py)."""

from typing import Optional

from pydantic import BaseModel, Field


class CreateReturnBody(BaseModel):
    """
    Field limits here are only a first guard against huge payloads.
    The real validation (and its messages) lives in services.request_service.
    """
    order_id: str = Field(default="", max_length=64)
    reason: str = Field(default="", max_length=64)
    description: Optional[str] = Field(default=None, max_length=2000)
    client_token: Optional[str] = Field(
        default=None, max_length=64,
        description="One token per form submission; repeating it never creates a second request.",
    )
