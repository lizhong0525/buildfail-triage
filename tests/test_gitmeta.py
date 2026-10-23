import subprocess
import unittest
from unittest import mock

from buildfail_triage.gitmeta import recent_commits


class TestRecentCommits(unittest.TestCase):
    def test_none_stdout_does_not_crash(self):
        # If the subprocess reader thread dies (e.g. a decode failure),
        # CompletedProcess.stdout is None; recent_commits must degrade to
        # "no git context" instead of raising AttributeError.
        fake = subprocess.CompletedProcess(args=["git"], returncode=0, stdout=None)
        with mock.patch("subprocess.run", return_value=fake):
            self.assertIsNone(recent_commits("/anywhere"))

    def test_git_failure_returns_none(self):
        fake = subprocess.CompletedProcess(args=["git"], returncode=128, stdout="")
        with mock.patch("subprocess.run", return_value=fake):
            self.assertIsNone(recent_commits("/anywhere"))

    def test_timeout_returns_none(self):
        with mock.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=10),
        ):
            self.assertIsNone(recent_commits("/anywhere"))


if __name__ == "__main__":
    unittest.main()
