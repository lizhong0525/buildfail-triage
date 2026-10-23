import unittest

from buildfail_triage.redaction import redact


class TestRedaction(unittest.TestCase):
    def test_github_tokens(self):
        text = (
            "using ghp_1234567890abcdefghijklmnopqrstuvwx and "
            "gho_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 to auth"
        )
        out = redact(text)
        self.assertNotIn("ghp_1234567890", out)
        self.assertNotIn("gho_ABCDEFGHIJ", out)
        self.assertIn("***REDACTED_GITHUB_TOKEN***", out)

    def test_github_fine_grained_pat(self):
        text = "token: github_pat_11ABCDEFG0_abcdefghijklmnopqrstuvwxyz0123456789"
        out = redact(text)
        self.assertNotIn("github_pat_11ABCDEFG0", out)
        self.assertIn("***REDACTED_GITHUB_PAT***", out)

    def test_openai_style_key_and_aws_key(self):
        text = "sk-abcdefghijklmnopqrstuvwxyz012345 AKIAIOSFODNN7EXAMPLE"
        out = redact(text)
        self.assertNotIn("sk-abcdefghij", out)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", out)

    def test_slack_and_npm_tokens(self):
        text = (
            "xoxb-123456789012-abcdefghijkl "
            "npm_abcdefghijklmnopqrstuvwxyz0123456789"
        )
        out = redact(text)
        self.assertNotIn("xoxb-123456789012", out)
        self.assertNotIn("npm_abcdefghij", out)

    def test_authorization_header(self):
        text = "Authorization: Bearer abcdef1234567890.supersecret"
        out = redact(text)
        self.assertNotIn("abcdef1234567890.supersecret", out)
        self.assertIn("Authorization: Bearer ***REDACTED***", out)

    def test_password_and_token_assignments(self):
        text = "password=hunter2\nDB_TOKEN: s3cr3t-value\napi_key=abcdef123"
        out = redact(text)
        self.assertNotIn("hunter2", out)
        self.assertNotIn("s3cr3t-value", out)
        self.assertNotIn("abcdef123", out)

    def test_private_key_block(self):
        text = (
            "before\n-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA7\n-----END RSA PRIVATE KEY-----\nafter"
        )
        out = redact(text)
        self.assertNotIn("MIIEowIBAAKCAQEA7", out)
        self.assertIn("***REDACTED_PRIVATE_KEY***", out)
        self.assertIn("before", out)
        self.assertIn("after", out)

    def test_non_secret_text_untouched(self):
        text = "FAILED tests/test_math.py::test_add - assert 2 == 3"
        self.assertEqual(redact(text), text)


if __name__ == "__main__":
    unittest.main()
