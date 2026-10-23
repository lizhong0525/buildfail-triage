"""Rule-based failure detectors.

Each rule is a set of regular expressions matched line by line against the
(redacted) log. Detections are deterministic and explainable: every finding
links back to the exact log lines that triggered it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rule:
    category: str
    title: str
    patterns: tuple[re.Pattern[str], ...]
    suggestions: tuple[str, ...]


@dataclass
class Detection:
    category: str
    title: str
    confidence: float
    match_lines: list[int]
    excerpt: str
    suggestions: list[str]
    rule_based: bool = field(default=True)

    @property
    def confidence_label(self) -> str:
        if self.confidence >= 0.8:
            return "high"
        if self.confidence >= 0.5:
            return "medium"
        return "low"


def _rx(*patterns: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p, re.IGNORECASE) for p in patterns)


RULES: tuple[Rule, ...] = (
    Rule(
        category="dependency_installation",
        title="Dependency installation failure",
        patterns=_rx(
            r"could not find a version that satisfies the requirement",
            r"no matching distribution found",
            r"npm err! code eresolve",
            r"npm err! could not resolve dependency",
            r"modulenotfounderror",
            r"error: failed building wheel for",
            r"pip's dependency resolver does not currently take into account",
            r"failed to fetch .+ from https?://",
        ),
        suggestions=(
            "Pin or relax the failing requirement and retry with a clean cache (pip --no-cache-dir / npm ci).",
            "Check whether the package version was yanked or requires a newer Python/Node than the runner provides.",
            "Compare the lockfile (requirements.txt / package-lock.json) with the versions installed in the last green build.",
        ),
    ),
    Rule(
        category="lint_or_type_error",
        title="Lint or type check error",
        patterns=_rx(
            r"\bE\d{3}\b.*\b(line too long|undefined name|unused import)\b",
            r"\[(error|warn)\]\s+\S+\.(ts|tsx|js|jsx)",
            r"error TS\d{4}",
            r"error: .+ \[(arg-type|assignment|return-value|misc)\]",
            r"would be reformatted",
            r"eslint.*\d+ error",
            r"ruff check.*failed",
        ),
        suggestions=(
            "Run the same linter/type checker locally (ruff/flake8, mypy, eslint, tsc) against the exact failing commit.",
            "Check for a recent config change (pyproject.toml, .eslintrc, mypy.ini) or a tool version bump in CI.",
        ),
    ),
    Rule(
        category="test_failure",
        title="Test failure",
        patterns=_rx(
            r"^FAILED\s+\S+",
            r"\bAssertionError\b",
            r"\d+ failed, \d+ passed",
            r"Failures: \d+",
            r"Tests: .*failed",
            r"✕|✗",
        ),
        suggestions=(
            "Re-run only the failing tests locally with verbose output (pytest -vv -x, or the equivalent for your stack).",
            "Look for ordering/timezone/randomness dependence if the failure does not reproduce locally.",
            "Check whether a recently merged change touched the code under test or its fixtures.",
        ),
    ),
    Rule(
        category="missing_env_var",
        title="Missing environment variable or secret",
        patterns=_rx(
            r"missing required environment variable",
            r"environment variable [\"']?[A-Z_]+[\"']? (is )?not (set|defined)",
            r"KeyError: '[A-Z][A-Z0-9_]*'",
            r"\b[A-Z][A-Z0-9_]+\b is required but (was )?not (provided|set)",
            r"secret [\"']?[A-Z_]+[\"']? is (missing|not set)",
        ),
        suggestions=(
            "Compare the variables referenced in the workflow file with the repository/environment secrets actually configured.",
            "Remember that secrets are not passed to workflows triggered by forked pull requests.",
            "Check for a recent rename of the variable in either the code or the workflow YAML.",
        ),
    ),
    Rule(
        category="network_timeout",
        title="Network timeout or connectivity failure",
        patterns=_rx(
            r"\bETIMEDOUT\b|\bECONNRESET\b|\bECONNREFUSED\b",
            r"timed out",
            r"timeout of \d+ms exceeded",
            r"connection refused",
            r"temporary failure in name resolution",
            r"could not resolve host",
            r"503 service unavailable|502 bad gateway",
        ),
        suggestions=(
            "Retry the job — transient registry/proxy failures are the most common cause.",
            "If it repeats, check the status page of the external service (npmjs, PyPI, Docker Hub) and any corporate proxy.",
            "Consider caching dependencies or pinning to an internal mirror to reduce exposure.",
        ),
    ),
    Rule(
        category="build_config",
        title="Build / CI configuration error",
        patterns=_rx(
            r"invalid workflow file",
            r"yaml\.(scanner|parser)\.",
            r"unexpected value ['\"]\w+['\"]",
            r"a mapping was not expected",
            r"cmake error",
            r"makefile:.*missing separator",
            r"error: .+\.(yml|yaml):\s*line \d+",
            r"no such target|no rule to make target",
        ),
        suggestions=(
            "Validate the workflow/config file locally (actionlint for GitHub Actions, yamllint for YAML).",
            "Diff the config file against the last green build — config errors almost always come from a recent edit.",
            "Check indentation and tabs; YAML and Makefiles fail on whitespace mistakes.",
        ),
    ),
)

_CONTEXT_LINES = 2
_MAX_EXCERPT_LINES = 40


def _build_excerpt(lines: list[str], match_lines: list[int]) -> str:
    windows: list[list[int]] = []
    for ln in match_lines:
        start = max(1, ln - _CONTEXT_LINES)
        end = min(len(lines), ln + _CONTEXT_LINES)
        if windows and start <= windows[-1][1] + 1:
            windows[-1][1] = max(windows[-1][1], end)
        else:
            windows.append([start, end])

    out: list[str] = []
    for i, (start, end) in enumerate(windows):
        if i:
            out.append("  ...")
        for n in range(start, end + 1):
            out.append(f"{n:>5} | {lines[n - 1]}")
            if len(out) >= _MAX_EXCERPT_LINES:
                out.append("  ... (excerpt truncated)")
                return "\n".join(out)
    return "\n".join(out)


def detect(text: str) -> list[Detection]:
    """Scan *text* (already redacted) and return detections, best first."""
    lines = text.splitlines()
    detections: list[Detection] = []
    for rule in RULES:
        match_lines = [
            i + 1
            for i, line in enumerate(lines)
            if any(p.search(line) for p in rule.patterns)
        ]
        if not match_lines:
            continue
        confidence = min(0.5 + 0.15 * len(match_lines), 0.95)
        detections.append(
            Detection(
                category=rule.category,
                title=rule.title,
                confidence=round(confidence, 2),
                match_lines=match_lines,
                excerpt=_build_excerpt(lines, match_lines),
                suggestions=list(rule.suggestions),
            )
        )
    detections.sort(key=lambda d: (-d.confidence, d.match_lines[0]))
    return detections
