import json
import os
import unittest

from buildfail_triage.detectors import detect
from buildfail_triage.gitmeta import DISCLAIMER
from buildfail_triage.redaction import redact
from buildfail_triage.report import build_report, render_json, render_markdown

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


def sample_report(ai_hypotheses=None, commits=None):
    text = redact(load_fixture("test_failure.log"))
    detections = detect(text)
    return build_report(
        source="fixtures/test_failure.log",
        lines_analyzed=len(text.splitlines()),
        detections=detections,
        commits=commits,
        ai_hypotheses=ai_hypotheses,
    )


class TestJsonReport(unittest.TestCase):
    def test_json_structure(self):
        report = sample_report()
        parsed = json.loads(render_json(report))
        self.assertEqual(parsed["tool"], "buildfail-triage")
        self.assertEqual(parsed["source"], "fixtures/test_failure.log")
        self.assertGreater(parsed["lines_analyzed"], 0)
        self.assertTrue(parsed["detections"])
        first = parsed["detections"][0]
        for key in (
            "category",
            "title",
            "confidence",
            "confidence_label",
            "rule_based",
            "match_lines",
            "excerpt",
            "suggestions",
        ):
            self.assertIn(key, first)
        self.assertTrue(first["rule_based"])
        self.assertFalse(parsed["git_context"]["available"])
        self.assertFalse(parsed["ai"]["enabled"])

    def test_json_ai_hypotheses_labeled_unverified(self):
        hyps = [
            {
                "detection_category": "test_failure",
                "hypothesis": "maybe float rounding",
                "source": "ai-adapter",
                "verified": False,
                "note": "Model-generated hypothesis",
            }
        ]
        parsed = json.loads(render_json(sample_report(ai_hypotheses=hyps)))
        self.assertTrue(parsed["ai"]["enabled"])
        self.assertFalse(parsed["ai"]["hypotheses"][0]["verified"])

    def test_json_git_context_and_disclaimer(self):
        commits = [
            {"sha": "abc1234", "subject": "fix stuff", "author": "Ann", "date": "2026-10-22"}
        ]
        parsed = json.loads(render_json(sample_report(commits=commits)))
        self.assertTrue(parsed["git_context"]["available"])
        self.assertEqual(parsed["git_context"]["recent_commits"][0]["sha"], "abc1234")
        self.assertIn("not evidence of causation", parsed["git_context"]["disclaimer"])


class TestMarkdownReport(unittest.TestCase):
    def test_markdown_sections(self):
        md = render_markdown(sample_report())
        self.assertIn("# BuildFail Triage Report", md)
        self.assertIn("## Detections (rule-based)", md)
        self.assertIn("**Relevant excerpt:**", md)
        self.assertIn("**Suggested next checks:**", md)
        self.assertIn("## Git context", md)
        self.assertIn("## AI-generated hypotheses", md)
        self.assertIn("disabled (default)", md)

    def test_markdown_never_contains_fixture_token(self):
        text = redact(load_fixture("dependency_install.log"))
        report = build_report(
            source="fixtures/dependency_install.log",
            lines_analyzed=len(text.splitlines()),
            detections=detect(text),
            commits=None,
            ai_hypotheses=None,
        )
        md = render_markdown(report)
        self.assertNotIn("ghp_1234567890", md)
        self.assertIn("***REDACTED_GITHUB_TOKEN***", md)

    def test_markdown_no_detections_message(self):
        report = build_report("empty.log", 3, [], None, None)
        md = render_markdown(report)
        self.assertIn("No known failure patterns", md)

    def test_git_disclaimer_present_when_commits(self):
        commits = [
            {"sha": "abc1234", "subject": "fix", "author": "Ann", "date": "2026-10-22"}
        ]
        md = render_markdown(sample_report(commits=commits))
        self.assertIn(DISCLAIMER, md)
        self.assertIn("`abc1234`", md)


if __name__ == "__main__":
    unittest.main()
