"""Pydantic models for the API."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str


class Item(BaseModel):
    """Response model for item endpoint."""

    id: int
    name: str
    description: str
