# BuildFail Triage

For developers staring at a failed CI run: paste a GitHub Actions log (or point at a saved log file) and get a prioritized diagnostic report — what category of failure it looks like, the exact log lines behind the call, a confidence score, and the next checks to run. No GitHub credentials, no network access, pure Python standard library.

## Quickstart

Requires Python 3.10+ (CI-tested on 3.10–3.13). No install, no third-party
dependencies:

```bash
python -m buildfail_triage fixtures/test_failure.log
```

That's it — no API keys, no network access.

## Demo walkthrough

The `fixtures/` directory contains one synthetic log per supported category:

```bash
# Markdown report to stdout
python -m buildfail_triage fixtures/test_failure.log

# JSON export
python -m buildfail_triage fixtures/missing_env_var.log --format json

# Save to a file
python -m buildfail_triage fixtures/dependency_install.log --output report.md

# Pipe a log instead of a file
cat fixtures/network_timeout.log | python -m buildfail_triage -
```

Try each fixture: `dependency_install.log`, `lint_type.log`, `test_failure.log`,
`missing_env_var.log`, `network_timeout.log`, `build_config.log`.
Every one produces its category, a confidence label, the triggering excerpt
(with secrets redacted — `dependency_install.log` contains a fake token that
never reaches the report), and concrete next checks.

If the log file sits inside a Git repository, the report also lists the 5 most
recent commits **as context only**, with an explicit disclaimer that temporal
proximity is not evidence of causation. Use `--git-dir DIR` to point at a
specific repository.

## Features

- Rule-based detection of six failure categories:
  dependency installation, lint/type errors, test failures,
  missing environment variables/secrets, network timeouts, and
  build/CI configuration errors.
- Every detection is deterministic and links back to numbered log lines.
- Automatic redaction of GitHub tokens, PATs, OpenAI-style keys, AWS keys,
  Slack/npm tokens, `Authorization` headers, password/token assignments, and
  private key blocks before anything is displayed or exported.
- Optional Git context (recent commits) with a non-causation disclaimer.
- Markdown and JSON export.
- Optional AI explanation adapter, **disabled by default**. Enable with
  `--enable-ai` and `BUILDFAIL_AI_ADAPTER=module:function` where
  `function(category, excerpt) -> str` returns a hypothesis. All AI output is
  labeled as an unverified, model-generated hypothesis and is kept clearly
  separate from rule-based detections in both output formats.

## Exit codes

- `0` — report produced.
- `2` — bad input (missing/empty/unreadable log) or misconfigured AI adapter.

## Tests

```bash
python -m unittest discover -s tests -v
```

Fully offline and deterministic; covers all six fixture categories, secret
redaction, report structure, and CLI failure paths.

## Known limitations

- Detection is keyword/regex-based, so it classifies *known shapes* of
  failures; an exotic failure with no matching pattern yields an empty
  detection list plus generic next checks.
- Multi-category logs report all matched categories, but confidence is a
  simple match-count heuristic, not a statistical model.
- Git context only lists commits; it does not diff them against the failure.
- Redaction covers common token shapes; unusual secret formats can slip
  through — treat reports as shareable within your team, not as public-safe.

## Roadmap

1. Fetch logs directly from the GitHub API (opt-in, token via env var).
2. Pluggable rule packs so teams can add project-specific detectors.
3. Diff-aware analysis correlating the failing log with the last green build.
