import contextlib
import io
import json
import os
import tempfile
import unittest

from buildfail_triage.cli import main

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def run_cli(argv):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


class TestCliHappyPath(unittest.TestCase):
    def test_markdown_report_to_stdout(self):
        path = os.path.join(FIXTURES, "test_failure.log")
        code, out, err = run_cli([path])
        self.assertEqual(code, 0, err)
        self.assertIn("# BuildFail Triage Report", out)
        self.assertIn("Test failure", out)
        self.assertIn("confidence", out)

    def test_json_report_is_valid(self):
        path = os.path.join(FIXTURES, "missing_env_var.log")
        code, out, err = run_cli([path, "--format", "json"])
        self.assertEqual(code, 0, err)
        parsed = json.loads(out)
        self.assertEqual(
            parsed["detections"][0]["category"], "missing_env_var"
        )

    def test_output_file_written(self):
        path = os.path.join(FIXTURES, "build_config.log")
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "report.md")
            code, out, err = run_cli([path, "--output", out_path])
            self.assertEqual(code, 0, err)
            with open(out_path, encoding="utf-8") as fh:
                content = fh.read()
            self.assertIn("Build / CI configuration error", content)

    def test_fixture_token_never_reaches_output(self):
        path = os.path.join(FIXTURES, "dependency_install.log")
        for fmt in ("markdown", "json"):
            code, out, err = run_cli([path, "--format", fmt])
            self.assertEqual(code, 0, err)
            self.assertNotIn("ghp_1234567890", out)
            self.assertNotIn("ghp_1234567890", err)
            self.assertIn("***REDACTED_GITHUB_TOKEN***", out)

    def test_unicode_log_content_does_not_crash(self):
        # Logs containing characters outside the console codepage (e.g. the
        # ✕/✗ markers the test-failure rule itself matches) must not crash
        # report printing on Windows GBK consoles.
        with tempfile.NamedTemporaryFile(
            "w", suffix=".log", delete=False, encoding="utf-8"
        ) as fh:
            fh.write("Test Suites: 1 failed\n ✕ adds numbers (5 ms)\n")
            path = fh.name
        try:
            for fmt in ("markdown", "json"):
                code, out, err = run_cli([path, "--format", fmt])
                self.assertEqual(code, 0, err)
                self.assertIn("Test failure", out)
        finally:
            os.unlink(path)


class TestCliFailurePaths(unittest.TestCase):
    def test_missing_file_exits_2(self):
        code, out, err = run_cli(["does/not/exist.log"])
        self.assertEqual(code, 2)
        self.assertIn("log file not found", err)

    def test_empty_file_exits_2(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".log", delete=False, encoding="utf-8"
        ) as fh:
            fh.write("   \n  \n")
            path = fh.name
        try:
            code, out, err = run_cli([path])
            self.assertEqual(code, 2)
            self.assertIn("empty", err)
        finally:
            os.unlink(path)

    def test_enable_ai_without_adapter_exits_2(self):
        os.environ.pop("BUILDFAIL_AI_ADAPTER", None)
        path = os.path.join(FIXTURES, "test_failure.log")
        code, out, err = run_cli([path, "--enable-ai"])
        self.assertEqual(code, 2)
        self.assertIn("BUILDFAIL_AI_ADAPTER", err)


class TestCliAiAdapter(unittest.TestCase):
    def test_ai_hypotheses_labeled_when_adapter_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            module_path = os.path.join(tmp, "fake_ai.py")
            with open(module_path, "w", encoding="utf-8") as fh:
                fh.write(
                    "def explain(category, excerpt):\n"
                    "    return 'hypothesis for ' + category\n"
                )
            import sys

            sys.path.insert(0, tmp)
            try:
                os.environ["BUILDFAIL_AI_ADAPTER"] = "fake_ai:explain"
                path = os.path.join(FIXTURES, "test_failure.log")
                code, out, err = run_cli([path])
                self.assertEqual(code, 0, err)
                self.assertNotIn("hypothesis for", out)  # not enabled yet
                code, out, err = run_cli([path, "--enable-ai", "--format", "json"])
                self.assertEqual(code, 0, err)
                parsed = json.loads(out)
                self.assertTrue(parsed["ai"]["enabled"])
                hyp = parsed["ai"]["hypotheses"][0]
                self.assertEqual(hyp["hypothesis"], "hypothesis for test_failure")
                self.assertFalse(hyp["verified"])
            finally:
                os.environ.pop("BUILDFAIL_AI_ADAPTER", None)
                sys.path.remove(tmp)


class TestCliGitContext(unittest.TestCase):
    def test_git_dir_with_no_repo_reports_unavailable(self):
        path = os.path.join(FIXTURES, "test_failure.log")
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run_cli([path, "--git-dir", tmp, "--format", "json"])
            self.assertEqual(code, 0, err)
            parsed = json.loads(out)
            self.assertFalse(parsed["git_context"]["available"])

    def test_git_dir_in_real_repo_shows_commits(self):
        with tempfile.TemporaryDirectory() as tmp:
            import subprocess

            env = dict(os.environ)
            env.update(
                {
                    "GIT_AUTHOR_NAME": "Test",
                    "GIT_AUTHOR_EMAIL": "test@example.com",
                    "GIT_COMMITTER_NAME": "Test",
                    "GIT_COMMITTER_EMAIL": "test@example.com",
                }
            )
            subprocess.run(["git", "-C", tmp, "init", "-q"], check=True)
            with open(os.path.join(tmp, "a.txt"), "w") as fh:
                fh.write("x")
            subprocess.run(["git", "-C", tmp, "add", "a.txt"], check=True, env=env)
            subprocess.run(
                ["git", "-C", tmp, "commit", "-qm", "initial commit"],
                check=True,
                env=env,
            )
            path = os.path.join(FIXTURES, "test_failure.log")
            code, out, err = run_cli([path, "--git-dir", tmp, "--format", "json"])
            self.assertEqual(code, 0, err)
            parsed = json.loads(out)
            self.assertTrue(parsed["git_context"]["available"])
            self.assertEqual(
                parsed["git_context"]["recent_commits"][0]["subject"],
                "initial commit",
            )
            self.assertIn(
                "not evidence of causation",
                parsed["git_context"]["disclaimer"],
            )

    def test_git_dir_with_non_ascii_commit_survives(self):
        # git log output is UTF-8; decoding it with the locale encoding
        # (GBK on a Chinese Windows box) used to crash the whole CLI.
        with tempfile.TemporaryDirectory() as tmp:
            import subprocess

            env = dict(os.environ)
            env.update(
                {
                    "GIT_AUTHOR_NAME": "中 李",
                    "GIT_AUTHOR_EMAIL": "test@example.com",
                    "GIT_COMMITTER_NAME": "中 李",
                    "GIT_COMMITTER_EMAIL": "test@example.com",
                    "LANG": "C.UTF-8",
                }
            )
            subprocess.run(["git", "-C", tmp, "init", "-q"], check=True)
            with open(os.path.join(tmp, "a.txt"), "w") as fh:
                fh.write("x")
            subprocess.run(["git", "-C", tmp, "add", "a.txt"], check=True, env=env)
            subprocess.run(
                ["git", "-C", tmp, "commit", "-qm", "修复 cart 总计"],
                check=True,
                env=env,
            )
            path = os.path.join(FIXTURES, "test_failure.log")
            code, out, err = run_cli([path, "--git-dir", tmp, "--format", "json"])
            self.assertEqual(code, 0, err)
            parsed = json.loads(out)
            commit = parsed["git_context"]["recent_commits"][0]
            self.assertEqual(commit["subject"], "修复 cart 总计")
            self.assertEqual(commit["author"], "中 李")


if __name__ == "__main__":
    unittest.main()
