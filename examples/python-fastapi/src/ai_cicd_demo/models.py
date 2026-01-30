"""Pydantic models for the API."""

from typing import Literal

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


class IntentRequest(BaseModel):
    """Request model for intent classification."""

    text: str = Field(..., min_length=1, description="Text to classify")


class IntentResponse(BaseModel):
    """Response model for intent classification."""

    intent: Literal["QUESTION", "REQUEST", "COMPLAINT", "OTHER"]
