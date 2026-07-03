import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redact import redact_secrets


def test_redacts_github_token():
    text = "using token ghp_abcdefghijklmnopqrstuvwxyz0123456789 to auth"
    result = redact_secrets(text)
    assert "ghp_" not in result
    assert "[REDACTED]" in result


def test_redacts_anthropic_key():
    text = "ANTHROPIC_API_KEY=sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789"
    result = redact_secrets(text)
    assert "sk-ant-" not in result


def test_redacts_generic_sk_key():
    text = "Authorization: sk-abcdefghijklmnopqrstuvwxyz0123456789"
    result = redact_secrets(text)
    assert "sk-abcdefghijklmnopqrstuvwxyz0123456789" not in result


def test_redacts_bearer_token():
    text = "curl -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'"
    result = redact_secrets(text)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
    assert "Bearer [REDACTED]" in result


def test_redacts_generic_env_assignment():
    text = "GITHUB_TOKEN=abc123def456\nPASSWORD: hunter2"
    result = redact_secrets(text)
    assert "abc123def456" not in result
    assert "hunter2" not in result
    assert "GITHUB_TOKEN=[REDACTED]" in result


def test_leaves_normal_log_text_untouched():
    text = "npm test\n> playwright test --reporter=list\n6 passed (3.2s)"
    result = redact_secrets(text)
    assert result == text


def test_leaves_unrelated_words_containing_key_substring_untouched():
    text = "keyboard input handled correctly for ArrowDown"
    result = redact_secrets(text)
    assert result == text


def test_handles_empty_and_none_like_input():
    assert redact_secrets("") == ""


def test_redacts_multiple_secrets_in_one_string():
    text = "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789 and ANTHROPIC_API_KEY=sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789"
    result = redact_secrets(text)
    assert "ghp_" not in result
    assert "sk-ant-" not in result
