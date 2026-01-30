"""Tests for AI intent classification module."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ai_cicd_demo.ai.intent import ALLOWED_INTENTS, classify_intent
from ai_cicd_demo.ai.openai_client import OpenAIError, call_openai, get_openai_client
from ai_cicd_demo.main import app

client = TestClient(app)


class TestClassifyIntent:
    """Tests for classify_intent function."""

    @patch("ai_cicd_demo.ai.intent.call_openai")
    def test_classify_question(self, mock_call: MagicMock) -> None:
        """Test classification of a question."""
        mock_call.return_value = "QUESTION"
        result = classify_intent("What time does the store open?")
        assert result == "QUESTION"
        mock_call.assert_called_once()

    @patch("ai_cicd_demo.ai.intent.call_openai")
    def test_classify_request(self, mock_call: MagicMock) -> None:
        """Test classification of a request."""
        mock_call.return_value = "REQUEST"
        result = classify_intent("Please send me the invoice")
        assert result == "REQUEST"

    @patch("ai_cicd_demo.ai.intent.call_openai")
    def test_classify_complaint(self, mock_call: MagicMock) -> None:
        """Test classification of a complaint."""
        mock_call.return_value = "COMPLAINT"
        result = classify_intent("Your service is terrible")
        assert result == "COMPLAINT"

    @patch("ai_cicd_demo.ai.intent.call_openai")
    def test_classify_other(self, mock_call: MagicMock) -> None:
        """Test classification of other intent."""
        mock_call.return_value = "OTHER"
        result = classify_intent("Hello")
        assert result == "OTHER"

    @patch("ai_cicd_demo.ai.intent.call_openai")
    def test_normalizes_lowercase_response(self, mock_call: MagicMock) -> None:
        """Test that lowercase responses are normalized."""
        mock_call.return_value = "question"
        result = classify_intent("What time?")
        assert result == "QUESTION"

    @patch("ai_cicd_demo.ai.intent.call_openai")
    def test_strips_whitespace(self, mock_call: MagicMock) -> None:
        """Test that whitespace is stripped from response."""
        mock_call.return_value = "  QUESTION  \n"
        result = classify_intent("What time?")
        assert result == "QUESTION"

    @patch("ai_cicd_demo.ai.intent.call_openai")
    def test_invalid_intent_raises_error(self, mock_call: MagicMock) -> None:
        """Test that invalid intent raises ValueError."""
        mock_call.return_value = "INVALID"
        with pytest.raises(ValueError, match="Invalid intent"):
            classify_intent("Some text")

    def test_empty_text_raises_error(self) -> None:
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            classify_intent("")

    def test_whitespace_only_raises_error(self) -> None:
        """Test that whitespace-only text raises ValueError."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            classify_intent("   ")

    def test_allowed_intents_contains_all_values(self) -> None:
        """Test that ALLOWED_INTENTS contains expected values."""
        assert "QUESTION" in ALLOWED_INTENTS
        assert "REQUEST" in ALLOWED_INTENTS
        assert "COMPLAINT" in ALLOWED_INTENTS
        assert "OTHER" in ALLOWED_INTENTS
        assert len(ALLOWED_INTENTS) == 4


class TestOpenAIClient:
    """Tests for OpenAI client wrapper."""

    def test_get_openai_client_missing_key(self) -> None:
        """Test that missing API key raises error."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(OpenAIError, match="OPENAI_API_KEY"):
                get_openai_client()

    @patch("ai_cicd_demo.ai.openai_client.get_openai_client")
    def test_call_openai_success(self, mock_get_client: MagicMock) -> None:
        """Test successful OpenAI call."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "QUESTION"
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = call_openai("system prompt", "user prompt")
        assert result == "QUESTION"

    @patch("ai_cicd_demo.ai.openai_client.get_openai_client")
    def test_call_openai_empty_response(self, mock_get_client: MagicMock) -> None:
        """Test that empty response raises error."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        with pytest.raises(OpenAIError, match="empty response"):
            call_openai("system", "user")

    @patch("ai_cicd_demo.ai.openai_client.get_openai_client")
    def test_call_openai_api_error(self, mock_get_client: MagicMock) -> None:
        """Test that API errors are wrapped."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client

        with pytest.raises(OpenAIError, match="API error"):
            call_openai("system", "user")


class TestClassifyIntentEndpoint:
    """Tests for /ai/classify_intent endpoint."""

    @patch("ai_cicd_demo.main.classify_intent")
    def test_classify_intent_success(self, mock_classify: MagicMock) -> None:
        """Test successful intent classification via API."""
        mock_classify.return_value = "QUESTION"
        response = client.post(
            "/ai/classify_intent",
            json={"text": "What time does the store open?"},
        )
        assert response.status_code == 200
        assert response.json() == {"intent": "QUESTION"}

    @patch("ai_cicd_demo.main.classify_intent")
    def test_classify_intent_openai_error(self, mock_classify: MagicMock) -> None:
        """Test OpenAI error returns 503."""
        mock_classify.side_effect = OpenAIError("Service unavailable")
        response = client.post(
            "/ai/classify_intent",
            json={"text": "Test"},
        )
        assert response.status_code == 503
        assert "AI service unavailable" in response.json()["detail"]

    @patch("ai_cicd_demo.main.classify_intent")
    def test_classify_intent_value_error(self, mock_classify: MagicMock) -> None:
        """Test ValueError returns 500."""
        mock_classify.side_effect = ValueError("Invalid response")
        response = client.post(
            "/ai/classify_intent",
            json={"text": "Test"},
        )
        assert response.status_code == 500
        assert "Classification error" in response.json()["detail"]

    def test_classify_intent_empty_text(self) -> None:
        """Test that empty text returns validation error."""
        response = client.post(
            "/ai/classify_intent",
            json={"text": ""},
        )
        assert response.status_code == 422  # Validation error

    def test_classify_intent_missing_text(self) -> None:
        """Test that missing text returns validation error."""
        response = client.post(
            "/ai/classify_intent",
            json={},
        )
        assert response.status_code == 422
