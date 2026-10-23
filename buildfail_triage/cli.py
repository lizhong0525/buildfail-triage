"""Command-line interface.

Usage:
    python -m buildfail_triage LOGFILE [--format markdown|json]
                [--output FILE] [--git-dir DIR] [--enable-ai]

LOGFILE may be ``-`` to read from stdin. No GitHub credentials are needed.
"""

from __future__ import annotations

import argparse
import os
import sys

from .ai_adapter import ENV_VAR, AIAdapterError, generate_hypotheses, load_adapter
from .detectors import detect
from .gitmeta import find_repo, recent_commits
from .redaction import redact
from .report import build_report, render_json, render_markdown


def _read_log(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    if not os.path.isfile(path):
        raise FileNotFoundError(f"log file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError as exc:
        raise OSError(f"could not read log file {path}: {exc}") from exc


def _git_context(log_path: str, git_dir: str | None):
    repo = git_dir
    if repo is None and log_path != "-":
        repo = find_repo(os.path.dirname(os.path.abspath(log_path)))
    if repo is None:
        return None
    return recent_commits(repo)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="buildfail-triage",
        description="Turn CI failure logs into actionable diagnostic reports. "
        "Fully offline; no GitHub credentials required.",
    )
    parser.add_argument("logfile", help="Path to a CI log file, or '-' for stdin.")
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format (default: markdown).",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Write the report to FILE instead of stdout.",
    )
    parser.add_argument(
        "--git-dir",
        metavar="DIR",
        help="Git repository to pull recent commits from "
        "(default: auto-detect near the log file).",
    )
    parser.add_argument(
        "--enable-ai",
        action="store_true",
        help=f"Enable the AI explanation adapter configured via {ENV_VAR}. "
        "Disabled by default; hypotheses are labeled as unverified.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        raw = _read_log(args.logfile)
    except (FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not raw.strip():
        print(f"error: log input is empty ({args.logfile})", file=sys.stderr)
        return 2

    text = redact(raw)
    detections = detect(text)
    commits = _git_context(args.logfile, args.git_dir)

    ai_hypotheses = None
    if args.enable_ai:
        try:
            adapter = load_adapter()
        except AIAdapterError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if adapter is None:
            print(
                f"error: --enable-ai was given but no adapter is configured. "
                f"Set {ENV_VAR}=module:function first.",
                file=sys.stderr,
            )
            return 2
        ai_hypotheses = generate_hypotheses(adapter, detections)

    report = build_report(
        source=args.logfile,
        lines_analyzed=len(text.splitlines()),
        detections=detections,
        commits=commits,
        ai_hypotheses=ai_hypotheses,
    )
    rendered = (
        render_json(report) if args.format == "json" else render_markdown(report)
    )

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(rendered + "\n")
        except OSError as exc:
            print(f"error: could not write report to {args.output}: {exc}", file=sys.stderr)
            return 2
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(rendered)
    return 0
