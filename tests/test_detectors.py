import os
import unittest

from buildfail_triage.detectors import detect
from buildfail_triage.redaction import redact

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures")

EXPECTED = {
    "dependency_install.log": "dependency_installation",
    "lint_type.log": "lint_or_type_error",
    "test_failure.log": "test_failure",
    "missing_env_var.log": "missing_env_var",
    "network_timeout.log": "network_timeout",
    "build_config.log": "build_config",
}


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


class TestFixturesDetected(unittest.TestCase):
    def test_every_fixture_category_detected(self):
        for filename, expected_category in EXPECTED.items():
            with self.subTest(fixture=filename):
                detections = detect(redact(load_fixture(filename)))
                categories = [d.category for d in detections]
                self.assertIn(
                    expected_category,
                    categories,
                    f"{filename}: expected {expected_category} in {categories}",
                )
                det = next(d for d in detections if d.category == expected_category)
                self.assertTrue(det.excerpt.strip(), "excerpt must not be empty")
                self.assertTrue(det.suggestions, "suggestions must not be empty")
                self.assertGreater(det.confidence, 0.0)
                self.assertLessEqual(det.confidence, 0.95)
                self.assertTrue(det.rule_based)

    def test_top_detection_is_highest_confidence(self):
        detections = detect(redact(load_fixture("test_failure.log")))
        confidences = [d.confidence for d in detections]
        self.assertEqual(confidences, sorted(confidences, reverse=True))

    def test_match_lines_exist_in_excerpt(self):
        detections = detect(redact(load_fixture("test_failure.log")))
        top = detections[0]
        self.assertEqual(top.category, "test_failure")
        for line_no in top.match_lines:
            self.assertIn(f"{line_no:>5} |", top.excerpt)


class TestEdgeCases(unittest.TestCase):
    def test_empty_log_yields_no_detections(self):
        self.assertEqual(detect(""), [])

    def test_noise_log_yields_no_detections(self):
        text = "everything is fine\nbuild succeeded\nall green\n"
        self.assertEqual(detect(text), [])

    def test_long_log_excerpt_is_truncated(self):
        lines = ["noise"] * 500
        for i in range(0, 500, 10):
            lines[i] = "FAILED tests/test_%d.py::test_x" % i
        detections = detect("\n".join(lines))
        self.assertTrue(detections)
        excerpt_line_count = len(detections[0].excerpt.splitlines())
        self.assertLessEqual(excerpt_line_count, 45)


if __name__ == "__main__":
    unittest.main()
