"""Unit tests for tools/ai_pr_summary.py."""

from ai_pr_summary import redact_secrets


class TestRedactSecrets:
    """Tests for the redact_secrets function."""

    def test_redacts_aws_access_keys(self) -> None:
        """AWS access keys (AKIA...) should be redacted."""
        content = "aws_access_key_id = AKIAIOSFODNN7EXAMPLE"
        result = redact_secrets(content)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "[REDACTED_AWS_KEY]" in result

    def test_redacts_github_tokens(self) -> None:
        """GitHub tokens (ghp_, ghs_) should be redacted."""
        # Token without key-like prefix - uses GitHub-specific pattern
        content = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx1234"
        result = redact_secrets(content)
        assert "ghp_" in result  # Prefix preserved
        assert "[REDACTED]" in result
        assert "xxxx" not in result

    def test_redacts_bearer_tokens(self) -> None:
        """Bearer tokens should be redacted."""
        content = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = redact_secrets(content)
        assert "Bearer" in result
        assert "[REDACTED]" in result

    def test_redacts_sk_api_keys(self) -> None:
        """sk-... API keys (OpenAI, Stripe) should be redacted."""
        # Standalone sk- key (not preceded by key-like word)
        content = "key is sk-proj-abc123def456ghi789jkl012mno345 here"
        result = redact_secrets(content)
        assert "sk-proj-abc123" not in result
        assert "[REDACTED_SK_KEY]" in result

    def test_redacts_stripe_keys(self) -> None:
        """Stripe secret keys should be redacted."""
        content = "payment uses sk-live-51234567890abcdefghijklmnop"
        result = redact_secrets(content)
        assert "sk-live-" not in result
        assert "[REDACTED_SK_KEY]" in result

    def test_redacts_jwt_tokens(self) -> None:
        """JWT tokens (xxx.yyy.zzz base64url) should be redacted."""
        # Real JWT structure: header.payload.signature (all base64url)
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
            "Sfl_KxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        content = f"Authorization: {jwt}"
        result = redact_secrets(content)
        assert "eyJhbGciOiJIUzI1NiI" not in result
        assert "[REDACTED_JWT]" in result

    def test_redacts_pem_private_keys(self) -> None:
        """PEM private key blocks should be redacted."""
        content = """
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy
base64encodedkeydata+more/key==
-----END RSA PRIVATE KEY-----
"""
        result = redact_secrets(content)
        assert "BEGIN RSA PRIVATE KEY" not in result
        assert "MIIEowIBAAKCAQEA" not in result
        assert "[REDACTED_PEM_KEY]" in result

    def test_redacts_ec_private_keys(self) -> None:
        """EC private key blocks should be redacted."""
        content = """-----BEGIN EC PRIVATE KEY-----
MHQCAQEEIBYa...
-----END EC PRIVATE KEY-----"""
        result = redact_secrets(content)
        assert "BEGIN EC PRIVATE KEY" not in result
        assert "[REDACTED_PEM_KEY]" in result

    def test_redacts_generic_private_keys(self) -> None:
        """Generic PRIVATE KEY blocks should be redacted."""
        content = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBg...
-----END PRIVATE KEY-----"""
        result = redact_secrets(content)
        assert "BEGIN PRIVATE KEY" not in result
        assert "[REDACTED_PEM_KEY]" in result

    def test_redacts_env_var_assignments(self) -> None:
        """Environment variable assignments with sensitive names should be redacted."""
        content = """
export API_KEY=super_secret_value_12345
DATABASE_URL=postgres://user:pass@host/db
SECRET_TOKEN=mysecrettoken123456789
"""
        result = redact_secrets(content)
        assert "super_secret_value" not in result
        assert "postgres://user:pass" not in result
        assert "mysecrettoken" not in result

    def test_redacts_generic_long_tokens(self) -> None:
        """Long tokens after key-like words should be redacted."""
        content = 'api_key: "abcdefghij1234567890klmnopqrst"'
        result = redact_secrets(content)
        assert "abcdefghij1234567890" not in result
        assert "[REDACTED]" in result

    def test_preserves_normal_content(self) -> None:
        """Normal code and text should not be redacted."""
        content = """
def hello_world():
    print("Hello, World!")
    return 42

# This is a comment about API design
class ApiHandler:
    pass
"""
        result = redact_secrets(content)
        assert 'print("Hello, World!")' in result
        assert "return 42" in result
        assert "ApiHandler" in result

    def test_handles_empty_string(self) -> None:
        """Empty string should return empty string."""
        assert redact_secrets("") == ""

    def test_handles_no_secrets(self) -> None:
        """Content without secrets should be unchanged."""
        content = "This is just regular text with no secrets."
        result = redact_secrets(content)
        assert result == content
