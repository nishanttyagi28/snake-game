import re

# Ordered from most specific to most general. Later patterns run against
# text already partially redacted by earlier ones, which is harmless (a
# "[REDACTED]" placeholder never matches a secret pattern).
_PATTERNS = [
    # Bearer tokens in Authorization headers, e.g. "Bearer eyJhbGciOi..."
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_.=]+"), "Bearer [REDACTED]"),
    # GitHub tokens: ghp_/gho_/ghu_/ghs_/ghr_ prefixes.
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[REDACTED]"),
    # Anthropic API keys (checked before the generic "sk-" OpenAI-style
    # pattern below, since sk-ant- is a more specific prefix of it).
    (re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b"), "[REDACTED]"),
    # Generic "sk-" style API keys (OpenAI and similar).
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "[REDACTED]"),
    # Catch-all: NAME=value / NAME: value where NAME looks secret-ish,
    # regardless of whether the value matched a known prefix above.
    # We deliberately err toward over-redacting here (e.g. it would also
    # redact "TOKEN_EXPIRED=true") -- a false positive just removes a
    # harmless value from a log line, a false negative could leak a
    # real credential.
    (
        re.compile(
            r"(?i)\b([A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*)\s*[:=]\s*['\"]?[^\s'\"]+['\"]?"
        ),
        r"\1=[REDACTED]",
    ),
]


def redact_secrets(text: str) -> str:
    if not text:
        return text
    redacted = text
    for pattern, replacement in _PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted
