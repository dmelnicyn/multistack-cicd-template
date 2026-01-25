"""Pydantic models for the API."""

from pydantic import BaseModel, EmailStr, Field


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str


class Item(BaseModel):
    """Response model for item endpoint."""

    id: int
    name: str
    description: str


class UserCreate(BaseModel):
    """Request model for creating a user."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: str | None = None


class User(BaseModel):
    """Response model for user endpoint."""

    id: int
    username: str
    email: str
    full_name: str | None = None
    is_active: bool = True
