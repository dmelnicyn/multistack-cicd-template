"""Thin wrapper around OpenAI client for reusable AI calls."""

from __future__ import annotations

import os

from openai import OpenAI


class OpenAIError(Exception):
    """Custom exception for OpenAI API errors."""

    pass


def get_openai_client() -> OpenAI:
    """Get configured OpenAI client.

    Returns:
        Configured OpenAI client instance.

    Raises:
        OpenAIError: If OPENAI_API_KEY is not set.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIError("OPENAI_API_KEY environment variable is not set")
    return OpenAI(api_key=api_key)


def call_openai(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
    max_tokens: int = 10,
) -> str:
    """Call OpenAI chat completion API.

    Args:
        system_prompt: System message to set context.
        user_prompt: User message with the actual query.
        model: OpenAI model to use.
        temperature: Sampling temperature (0 = deterministic).
        max_tokens: Maximum tokens in response.

    Returns:
        The text content of the assistant's response.

    Raises:
        OpenAIError: If API call fails or response is invalid.
    """
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content
        if content is None:
            raise OpenAIError("OpenAI returned empty response")

        return content.strip()

    except OpenAIError:
        raise
    except Exception as e:
        raise OpenAIError(f"OpenAI API error: {e}") from e
