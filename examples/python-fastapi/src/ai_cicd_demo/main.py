"""FastAPI application with health, item, and user endpoints."""

from fastapi import FastAPI, HTTPException

from ai_cicd_demo.ai.intent import classify_intent
from ai_cicd_demo.ai.openai_client import OpenAIError
from ai_cicd_demo.models import (
    HealthResponse,
    IntentRequest,
    IntentResponse,
    Item,
    User,
    UserCreate,
)

app = FastAPI(
    title="AI CI/CD Demo",
    description="A minimal FastAPI learning template for CI/CD",
    version="0.1.0",
)

# In-memory user storage (for demo purposes)
_users: dict[int, User] = {}
_next_user_id = 1


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


@app.post("/users", response_model=User, status_code=201)
def create_user(user_data: UserCreate) -> User:
    """Create a new user.

    Args:
        user_data: The user data to create.

    Returns:
        The created user with assigned ID.
    """
    global _next_user_id

    # Check for duplicate username
    for existing_user in _users.values():
        if existing_user.username == user_data.username:
            raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        id=_next_user_id,
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
    )
    _users[_next_user_id] = user
    _next_user_id += 1
    return user


@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: int) -> User:
    """Get a user by ID.

    Args:
        user_id: The ID of the user to retrieve.

    Returns:
        The user with the given ID.

    Raises:
        HTTPException: If user not found.
    """
    if user_id not in _users:
        raise HTTPException(status_code=404, detail="User not found")
    return _users[user_id]


@app.get("/users", response_model=list[User])
def list_users() -> list[User]:
    """List all users.

    Returns:
        List of all users.
    """
    return list(_users.values())


@app.post("/ai/classify_intent", response_model=IntentResponse)
def classify_intent_endpoint(request: IntentRequest) -> IntentResponse:
    """Classify the intent of a text message.

    Uses OpenAI to classify text into one of:
    - QUESTION: The user is asking a question
    - REQUEST: The user is asking for an action
    - COMPLAINT: The user is expressing dissatisfaction
    - OTHER: Doesn't fit the above categories

    Args:
        request: The text to classify.

    Returns:
        The classified intent.

    Raises:
        HTTPException: If classification fails.
    """
    try:
        intent = classify_intent(request.text)
        return IntentResponse(intent=intent)
    except OpenAIError as e:
        raise HTTPException(
            status_code=503, detail=f"AI service unavailable: {e}"
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=500, detail=f"Classification error: {e}"
        ) from e
