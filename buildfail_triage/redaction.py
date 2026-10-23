"""Secret redaction.

Log excerpts are always passed through :func:`redact` before they are shown
or exported, so tokens, keys and passwords that happen to appear in CI logs
never end up in a report.
"""

from __future__ import annotations

import re

# Order matters: more specific patterns come first.
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        "***REDACTED_PRIVATE_KEY***",
    ),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "***REDACTED_GITHUB_PAT***"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "***REDACTED_GITHUB_TOKEN***"),
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), "***REDACTED_API_KEY***"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "***REDACTED_AWS_ACCESS_KEY***"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "***REDACTED_SLACK_TOKEN***"),
    (re.compile(r"npm_[A-Za-z0-9]{30,}"), "***REDACTED_NPM_TOKEN***"),
    (
        re.compile(r"(?i)(authorization:\s*(?:bearer|token|basic)\s+)(\S+)"),
        r"\1***REDACTED***",
    ),
    (
        re.compile(
            r"(?i)\b([A-Za-z0-9_-]*(?:password|passwd|secret|api[_-]?key|token)[A-Za-z0-9_-]*)"
            r"(\s*[:=]\s*)(?!\*\*\*)(\S+)"
        ),
        r"\1\2***REDACTED***",
    ),
)


def redact(text: str) -> str:
    """Return *text* with known secret shapes replaced by placeholders."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
