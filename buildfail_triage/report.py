"""Report assembly and rendering (Markdown / JSON)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import __version__
from .detectors import Detection
from .gitmeta import DISCLAIMER


def build_report(
    source: str,
    lines_analyzed: int,
    detections: list[Detection],
    commits: list[dict[str, str]] | None,
    ai_hypotheses: list[dict] | None,
) -> dict:
    return {
        "tool": "buildfail-triage",
        "version": __version__,
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lines_analyzed": lines_analyzed,
        "detections": [
            {
                "category": d.category,
                "title": d.title,
                "confidence": d.confidence,
                "confidence_label": d.confidence_label,
                "rule_based": d.rule_based,
                "match_lines": d.match_lines,
                "excerpt": d.excerpt,
                "suggestions": d.suggestions,
            }
            for d in detections
        ],
        "git_context": {
            "available": commits is not None,
            "recent_commits": commits or [],
            "disclaimer": DISCLAIMER,
        },
        "ai": {
            "enabled": ai_hypotheses is not None,
            "hypotheses": ai_hypotheses or [],
        },
    }


def render_json(report: dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False)


def render_markdown(report: dict) -> str:
    out: list[str] = []
    out.append("# BuildFail Triage Report")
    out.append("")
    out.append(f"- **Source:** `{report['source']}`")
    out.append(f"- **Generated:** {report['generated_at']}")
    out.append(f"- **Lines analyzed:** {report['lines_analyzed']}")
    out.append("")

    out.append("## Detections (rule-based)")
    out.append("")
    if not report["detections"]:
        out.append("No known failure patterns were detected in this log.")
        out.append("")
        out.append("Generic next checks:")
        out.append("- Read the last ~50 lines of the full log for the actual exit error.")
        out.append("- Compare against the last green build to isolate what changed.")
        out.append("")
    for i, det in enumerate(report["detections"], 1):
        out.append(
            f"### {i}. {det['title']} "
            f"(confidence: {det['confidence_label']}, {det['confidence']:.2f})"
        )
        out.append("")
        out.append(f"Category: `{det['category']}` — deterministic rule-based detection.")
        out.append("")
        out.append("**Relevant excerpt:**")
        out.append("")
        out.append("```text")
        out.append(det["excerpt"])
        out.append("```")
        out.append("")
        out.append("**Suggested next checks:**")
        for s in det["suggestions"]:
            out.append(f"- {s}")
        out.append("")

    git = report["git_context"]
    out.append("## Git context")
    out.append("")
    if git["available"]:
        out.append(f"> {git['disclaimer']}")
        out.append("")
        for c in git["recent_commits"]:
            out.append(f"- `{c['sha']}` {c['subject']} — {c['author']}, {c['date']}")
    else:
        out.append("No Git repository found near the log file; commit context unavailable.")
    out.append("")

    out.append("## AI-generated hypotheses")
    out.append("")
    if report["ai"]["enabled"]:
        out.append(
            "> The items below come from an external model via the AI adapter. "
            "They are **unverified hypotheses**, not rule-based detections."
        )
        out.append("")
        for h in report["ai"]["hypotheses"]:
            out.append(f"- **{h['detection_category']}** — {h['hypothesis']}")
        out.append("")
    else:
        out.append(
            "AI explanation adapter is disabled (default). Enable it with "
            "`--enable-ai` and the `BUILDFAIL_AI_ADAPTER` environment variable."
        )
        out.append("")

    return "\n".join(out)
