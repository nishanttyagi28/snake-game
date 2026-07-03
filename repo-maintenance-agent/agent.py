import argparse
import hashlib
import logging
import os
import sys
from datetime import datetime, timezone

import yaml
from dotenv import load_dotenv

from checks_runner import run_checks, has_failures
from git_ops import clone_or_pull, create_branch, commit_all, push_branch, revert_uncommitted
from github_client import GitHubClient
from redact import redact_secrets
from fixer import build_fix_prompt, request_fix, validate_fix

_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_KNOWN_FILES = ["src/game.js", "index.html", "style.css", "tests/snake.spec.js"]


def _setup_logging():
    logs_dir = os.path.join(_AGENT_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.log")

    logger = logging.getLogger("agent")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    return logger


def _load_config(config_path):
    # utf-8-sig transparently strips a UTF-8 BOM if present (e.g. config.yaml
    # saved with Notepad, which defaults to BOM on Windows) and behaves
    # exactly like plain utf-8 otherwise.
    with open(config_path, "r", encoding="utf-8-sig") as f:
        return yaml.safe_load(f)


def _repo_full_name(repo_url):
    """"https://github.com/owner/repo(.git)" or "git@github.com:owner/repo(.git)" -> "owner/repo"."""
    trimmed = repo_url.rstrip("/")
    if trimmed.endswith(".git"):
        trimmed = trimmed[: -len(".git")]
    if trimmed.startswith("git@"):
        return trimmed.split(":", 1)[-1]
    return trimmed.split("github.com/", 1)[-1]


def _fingerprint(cmd, stdout, stderr):
    first_line = next((line for line in (stderr or stdout or "").splitlines() if line.strip()), "")
    digest = hashlib.sha256(f"{cmd}::{first_line}".encode("utf-8")).hexdigest()[:12]
    return digest


def _gather_relevant_files(repo_path, results):
    combined_output = "\n".join((r["stdout"] or "") + (r["stderr"] or "") for r in results)
    mentioned = [f for f in _KNOWN_FILES if f in combined_output]
    if not mentioned:
        mentioned = ["src/game.js", "tests/snake.spec.js"]

    files = {}
    for rel_path in mentioned:
        abs_path = os.path.join(repo_path, rel_path)
        if os.path.isfile(abs_path):
            with open(abs_path, "r", encoding="utf-8") as f:
                files[rel_path] = f.read()
    return files


def _format_results_for_issue(results):
    lines = []
    for r in results:
        status = "PASS" if r["code"] == 0 else "FAIL"
        lines.append(f"### `{r['cmd']}` — {status} (exit {r['code']})")
        if r["code"] != 0:
            lines.append("```")
            lines.append(redact_secrets((r["stdout"] or "").strip()))
            lines.append(redact_secrets((r["stderr"] or "").strip()))
            lines.append("```")
    return "\n".join(lines)


def _attempt_fix(local_path, branch_name, failing, results, logger, attempt):
    create_branch(local_path, branch_name)

    try:
        relevant_files = _gather_relevant_files(local_path, results)
        prompt = build_fix_prompt(
            cmd=failing["cmd"],
            stdout=redact_secrets(failing["stdout"]),
            stderr=redact_secrets(failing["stderr"]),
            relevant_files=relevant_files,
        )
        fix = request_fix(prompt)
    except ValueError as exc:
        logger.warning("Attempt %s: malformed fix response: %s", attempt, exc)
        revert_uncommitted(local_path)
        return None, f"Attempt {attempt}: malformed fix response ({exc})"

    target_path = os.path.join(local_path, fix["file_path"])
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(fix["code"])

    if not validate_fix(local_path, fix["file_path"]):
        logger.warning("Attempt %s: fix touched more than the declared file; reverting", attempt)
        revert_uncommitted(local_path)
        return None, f"Attempt {attempt}: fix touched more than {fix['file_path']}; discarded"

    return fix, None


def run(config_path):
    logger = _setup_logging()

    try:
        config = _load_config(config_path)

        repo_url = config["repo_url"]
        local_path = os.path.normpath(os.path.join(_AGENT_DIR, config["local_path"]))
        branch_prefix = config["branch_prefix"]
        max_fix_attempts = config["max_fix_attempts"]
        checks = config["checks"]

        github_token = os.environ.get("GITHUB_TOKEN")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

        logger.info("Cloning/pulling %s into %s", repo_url, local_path)
        clone_or_pull(repo_url, local_path)

        logger.info("Running checks: %s", checks)
        results = run_checks(local_path, checks)

        if not has_failures(results):
            logger.info("All checks passed. Nothing to do.")
            return 0

        original_failing = next(r for r in results if r["code"] != 0)
        fingerprint = _fingerprint(original_failing["cmd"], original_failing["stdout"], original_failing["stderr"])
        logger.info("Checks failed. Failing command: %s (fingerprint %s)", original_failing["cmd"], fingerprint)

        if not github_token:
            logger.error("GITHUB_TOKEN not set; cannot open/update a GitHub issue. Stopping.")
            return 1

        gh = GitHubClient(github_token, _repo_full_name(repo_url))
        fingerprint_marker = f"<!-- fingerprint:{fingerprint} -->"

        issue_number = gh.find_existing_issue(fingerprint)
        if issue_number is None:
            issue_number = gh.create_issue(
                title=f"Automated maintenance: `{original_failing['cmd']}` failed",
                body=f"{fingerprint_marker}\n\nThe maintenance agent found a failing check.\n\n"
                f"{_format_results_for_issue(results)}",
                labels=["agent-maintenance"],
            )
            logger.info("Opened issue #%s", issue_number)
        else:
            logger.info("Reusing existing issue #%s", issue_number)

        if not anthropic_key:
            logger.error("ANTHROPIC_API_KEY not set; cannot attempt a fix. Stopping.")
            gh.comment_issue(
                issue_number, "Agent could not attempt a fix: ANTHROPIC_API_KEY is not configured."
            )
            return 1

        attempts_log = []
        for attempt in range(1, max_fix_attempts + 1):
            # Re-derive "failing" from the most recent check run each attempt,
            # since an unsuccessful prior attempt may have changed which check
            # (or which part of it) is failing.
            failing = next(r for r in results if r["code"] != 0)
            logger.info("Fix attempt %s/%s (targeting: %s)", attempt, max_fix_attempts, failing["cmd"])
            branch_name = f"{branch_prefix}/fix-{fingerprint}-{attempt}"

            fix, failure_note = _attempt_fix(local_path, branch_name, failing, results, logger, attempt)
            if fix is None:
                attempts_log.append(failure_note)
                continue

            results = run_checks(local_path, checks)
            if not has_failures(results):
                commit_all(local_path, f"Fix: {fix['explanation'][:72]}")
                push_branch(local_path, branch_name)
                pr_url = gh.create_pull_request(
                    branch_name=branch_name,
                    title=f"Fix: {original_failing['cmd']} failure",
                    body=f"Closes #{issue_number}\n\n{fix['explanation']}",
                )
                gh.comment_issue(issue_number, f"Opened a fix: {pr_url}")
                logger.info("Fix verified. Opened PR: %s", pr_url)
                return 0

            logger.info("Attempt %s: fix did not resolve all checks; reverting", attempt)
            attempts_log.append(f"Attempt {attempt}: applied fix to {fix['file_path']} but checks still failed")
            revert_uncommitted(local_path)

        summary = "\n".join(f"- {line}" for line in attempts_log) or "- No fix attempts produced a usable change."
        gh.add_label(issue_number, "needs-human")
        gh.comment_issue(
            issue_number,
            f"Agent exhausted {max_fix_attempts} fix attempts without resolving this issue.\n\n{summary}",
        )
        logger.warning("Exhausted fix attempts. Issue #%s labeled needs-human.", issue_number)
        return 1

    except Exception:
        logger.exception("Agent run failed with an unexpected error")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Snake Game maintenance agent")
    parser.add_argument("--config", default=os.path.join(_AGENT_DIR, "config.yaml"))
    args = parser.parse_args()

    load_dotenv(os.path.join(_AGENT_DIR, ".env"))
    sys.exit(run(args.config))


if __name__ == "__main__":
    main()
