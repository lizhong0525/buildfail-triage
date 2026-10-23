"""Optional Git context.

If the log file lives inside a Git repository (or ``--git-dir`` is given),
recent commits are shown as *context only*. No causation is ever asserted:
a commit appearing near a failure in time is not evidence it caused it.
"""

from __future__ import annotations

import os
import subprocess

DISCLAIMER = (
    "Recent commits are provided as context only. Temporal proximity to a "
    "failure is not evidence of causation; no commit below is asserted to "
    "have caused the failure."
)


def find_repo(start: str) -> str | None:
    """Walk upward from *start* looking for a .git directory."""
    current = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def recent_commits(repo: str, count: int = 5) -> list[dict[str, str]] | None:
    """Return up to *count* recent commits, or None if unavailable."""
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                repo,
                "log",
                f"-{count}",
                "--pretty=format:%h|%s|%an|%ad",
                "--date=short",
            ],
            capture_output=True,
            # git writes log output as UTF-8; decoding with the locale
            # encoding (e.g. GBK on Windows) crashes on non-ASCII commits.
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    stdout = proc.stdout or ""
    if proc.returncode != 0 or not stdout.strip():
        return None
    commits = []
    for line in stdout.strip().splitlines():
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        commits.append(
            {"sha": parts[0], "subject": parts[1], "author": parts[2], "date": parts[3]}
        )
    return commits or None
