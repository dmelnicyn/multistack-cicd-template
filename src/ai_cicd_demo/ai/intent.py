"""Intent classification using OpenAI."""

from __future__ import annotations

from ai_cicd_demo.ai.openai_client import call_openai

# Allowed intent labels
ALLOWED_INTENTS = ["QUESTION", "REQUEST", "COMPLAINT", "OTHER"]

# System prompt for intent classification
SYSTEM_PROMPT = """\
You are an intent classifier. Classify the user's message into exactly one \
of these categories:
- QUESTION: The user is asking a question or seeking information
- REQUEST: The user is asking for an action to be performed
- COMPLAINT: The user is expressing dissatisfaction or a problem
- OTHER: The message doesn't fit the above categories

Respond with ONLY the category name in uppercase \
(QUESTION, REQUEST, COMPLAINT, or OTHER).
Do not include any other text, punctuation, or explanation."""


def classify_intent(text: str) -> str:
    """Classify the intent of a text message.

    Args:
        text: The text to classify.

    Returns:
        One of: QUESTION, REQUEST, COMPLAINT, OTHER

    Raises:
        OpenAIError: If API call fails.
        ValueError: If response is not a valid intent.
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")

    response = call_openai(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=text,
        model="gpt-4o-mini",
        temperature=0.0,
        max_tokens=10,
    )

    # Normalize response: uppercase and strip whitespace
    intent = response.upper().strip()

    # Validate response is one of allowed intents
    if intent not in ALLOWED_INTENTS:
        raise ValueError(
            f"Invalid intent '{intent}' returned by model. "
            f"Expected one of: {ALLOWED_INTENTS}"
        )

    return intent
