"""Optional AI explanation adapter (disabled by default).

The tool works fully offline with rule-based detections only. If you want
model-generated hypotheses, point the ``BUILDFAIL_AI_ADAPTER`` environment
variable at a callable, e.g. ``BUILDFAIL_AI_ADAPTER=mymodule:explain``, where
``explain(category: str, excerpt: str) -> str`` returns a hypothesis string.

Anything produced this way is labeled as an *unverified model-generated
hypothesis* and is always kept separate from rule-based detections in the
report. The adapter is loaded but never invoked unless ``--enable-ai`` is
passed on the command line.
"""

from __future__ import annotations

import importlib
import os
from typing import Callable

ENV_VAR = "BUILDFAIL_AI_ADAPTER"


class AIAdapterError(Exception):
    """Raised when the configured AI adapter cannot be loaded."""


def load_adapter() -> Callable[[str, str], str] | None:
    """Load the adapter callable from the environment, or None if unset."""
    spec = os.environ.get(ENV_VAR, "").strip()
    if not spec:
        return None
    if ":" not in spec:
        raise AIAdapterError(
            f"{ENV_VAR} must be in the form 'module:function', got {spec!r}"
        )
    module_name, func_name = spec.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise AIAdapterError(
            f"Could not import AI adapter module {module_name!r}: {exc}"
        ) from exc
    func = getattr(module, func_name, None)
    if not callable(func):
        raise AIAdapterError(
            f"{module_name!r} has no callable {func_name!r}"
        )
    return func


def generate_hypotheses(
    adapter: Callable[[str, str], str], detections: list
) -> list[dict]:
    """Run the adapter over rule-based detections and label every output."""
    hypotheses = []
    for det in detections:
        try:
            text = adapter(det.category, det.excerpt)
        except Exception as exc:  # adapter failures must not kill the report
            text = f"(adapter raised {type(exc).__name__}: {exc})"
        hypotheses.append(
            {
                "detection_category": det.category,
                "hypothesis": text,
                "source": "ai-adapter",
                "verified": False,
                "note": "Model-generated hypothesis, not a rule-based detection. "
                "Treat as a starting point, not a diagnosis.",
            }
        )
    return hypotheses
