"""FastAPI application with health and item endpoints."""

from fastapi import FastAPI

from ai_cicd_demo.models import HealthResponse, Item

app = FastAPI(
    title="AI CI/CD Demo",
    description="A minimal FastAPI learning template for CI/CD",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Check if the service is healthy."""
    return HealthResponse(status="ok")


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int) -> Item:
    """Get an item by ID.

    This is a simple example endpoint that returns mock data.
    In a real application, this would fetch from a database.
    """
    return Item(
        id=item_id,
        name=f"Item {item_id}",
        description=f"This is item number {item_id}",
    )
