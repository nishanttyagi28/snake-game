import os
import shutil
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agent


@pytest.fixture
def workdir():
    root = tempfile.mkdtemp(prefix="agent_test_")
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def config_path(workdir):
    local_path = os.path.join(workdir, "repo")
    config = {
        "repo_url": "https://github.com/test-owner/snake-game",
        "local_path": local_path,
        "branch_prefix": "agent-maintenance",
        "max_fix_attempts": 3,
        "checks": ["fake-check"],
    }
    path = os.path.join(workdir, "config.yaml")
    with open(path, "w") as f:
        yaml.safe_dump(config, f)
    return path


def _result(cmd="fake-check", code=0, stdout="", stderr=""):
    return {"cmd": cmd, "code": code, "stdout": stdout, "stderr": stderr}


# Real (trimmed) Playwright "list" reporter output from two genuinely
# different failures -- both start with the same generic header line.
PLAYWRIGHT_OUTPUT_BUG_1 = """\
Running 6 tests using 6 workers

  x  5 tests\\snake.spec.js:59:1 › 4. score increases after eating food (4.1s)

    Error: expect(received).toBeGreaterThan(expected)

    Expected: > 0
    Received:   0
"""

PLAYWRIGHT_OUTPUT_BUG_2 = """\
Running 6 tests using 6 workers

  x  4 tests\\snake.spec.js:71:1 › 6. restart button resets the game (5.9s)

    Error: expect(locator).toContainText(expected) failed

    Locator: locator('#score')
    Expected substring: "0"
    Received string:    "1"
"""


def test_fingerprint_distinguishes_different_failures_of_the_same_command():
    fp1 = agent._fingerprint("npx playwright test", PLAYWRIGHT_OUTPUT_BUG_1, "")
    fp2 = agent._fingerprint("npx playwright test", PLAYWRIGHT_OUTPUT_BUG_2, "")
    assert fp1 != fp2


def test_fingerprint_is_stable_for_the_same_failure():
    fp1 = agent._fingerprint("npx playwright test", PLAYWRIGHT_OUTPUT_BUG_1, "")
    fp2 = agent._fingerprint("npx playwright test", PLAYWRIGHT_OUTPUT_BUG_1, "")
    assert fp1 == fp2


def test_fingerprint_falls_back_to_first_line_when_no_error_keyword():
    fp = agent._fingerprint("echo hi", "just plain output\nmore output", "")
    assert fp == agent._fingerprint("echo hi", "just plain output\nsomething else", "")


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-gh-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")


def test_all_checks_pass_exits_zero_and_touches_no_github(config_path):
    with patch("agent.clone_or_pull") as mock_clone, \
         patch("agent.run_checks", return_value=[_result(code=0)]), \
         patch("agent.GitHubClient") as MockGH:
        code = agent.run(config_path)

    assert code == 0
    mock_clone.assert_called_once()
    MockGH.assert_not_called()


def test_missing_github_token_stops_before_any_github_call(config_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch("agent.clone_or_pull"), \
         patch("agent.run_checks", return_value=[_result(code=1, stderr="boom")]), \
         patch("agent.GitHubClient") as MockGH:
        code = agent.run(config_path)

    assert code == 1
    MockGH.assert_not_called()


def test_missing_anthropic_key_creates_issue_but_does_not_attempt_fix(config_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    mock_gh_instance = MagicMock()
    mock_gh_instance.find_existing_issue.return_value = None
    mock_gh_instance.create_issue.return_value = 5

    with patch("agent.clone_or_pull"), \
         patch("agent.run_checks", return_value=[_result(code=1, stderr="boom")]), \
         patch("agent.GitHubClient", return_value=mock_gh_instance), \
         patch("agent.request_fix") as mock_request_fix:
        code = agent.run(config_path)

    assert code == 1
    mock_gh_instance.create_issue.assert_called_once()
    mock_request_fix.assert_not_called()
    mock_gh_instance.comment_issue.assert_called_once()


def test_fix_succeeds_on_first_attempt_opens_pr(config_path):
    mock_gh_instance = MagicMock()
    mock_gh_instance.find_existing_issue.return_value = None
    mock_gh_instance.create_issue.return_value = 5
    mock_gh_instance.create_pull_request.return_value = "https://github.com/test-owner/snake-game/pull/1"

    check_results = [
        [_result(code=1, stderr="score did not increase")],  # initial run
        [_result(code=0)],  # after the fix
    ]

    with patch("agent.clone_or_pull"), \
         patch("agent.run_checks", side_effect=check_results), \
         patch("agent.GitHubClient", return_value=mock_gh_instance), \
         patch("agent.create_branch"), \
         patch("agent.commit_all") as mock_commit, \
         patch("agent.push_branch") as mock_push, \
         patch("agent.revert_uncommitted") as mock_revert, \
         patch("agent.request_fix", return_value={
             "file_path": "src/game.js",
             "explanation": "increment score properly",
             "code": "this.score += 1;",
         }), \
         patch("agent.validate_fix", return_value=True):
        code = agent.run(config_path)

    assert code == 0
    mock_gh_instance.create_issue.assert_called_once()
    mock_commit.assert_called_once()
    mock_push.assert_called_once()
    mock_gh_instance.create_pull_request.assert_called_once()
    mock_gh_instance.comment_issue.assert_called_once()
    mock_revert.assert_not_called()


def test_existing_issue_is_reused_not_duplicated(config_path):
    mock_gh_instance = MagicMock()
    mock_gh_instance.find_existing_issue.return_value = 7

    with patch("agent.clone_or_pull"), \
         patch("agent.run_checks", return_value=[_result(code=1, stderr="boom")]), \
         patch("agent.GitHubClient", return_value=mock_gh_instance), \
         patch("agent.create_branch"), \
         patch("agent.revert_uncommitted"), \
         patch("agent.request_fix", side_effect=ValueError("malformed")):
        agent.run(config_path)

    mock_gh_instance.create_issue.assert_not_called()


def test_exhausting_fix_attempts_labels_needs_human(config_path):
    mock_gh_instance = MagicMock()
    mock_gh_instance.find_existing_issue.return_value = None
    mock_gh_instance.create_issue.return_value = 5

    with patch("agent.clone_or_pull"), \
         patch("agent.run_checks", return_value=[_result(code=1, stderr="boom")]), \
         patch("agent.GitHubClient", return_value=mock_gh_instance), \
         patch("agent.create_branch"), \
         patch("agent.revert_uncommitted") as mock_revert, \
         patch("agent.request_fix", side_effect=ValueError("malformed response")):
        code = agent.run(config_path)

    assert code == 1
    assert mock_revert.call_count == 3  # max_fix_attempts
    mock_gh_instance.add_label.assert_called_once_with(5, "needs-human")
    mock_gh_instance.comment_issue.assert_called_once()


def test_recovers_from_a_malformed_response_then_succeeds(config_path):
    mock_gh_instance = MagicMock()
    mock_gh_instance.find_existing_issue.return_value = None
    mock_gh_instance.create_issue.return_value = 5
    mock_gh_instance.create_pull_request.return_value = "https://github.com/test-owner/snake-game/pull/1"

    check_results = [
        [_result(code=1, stderr="boom")],  # initial run
        [_result(code=0)],  # after the second (successful) attempt
    ]

    with patch("agent.clone_or_pull"), \
         patch("agent.run_checks", side_effect=check_results), \
         patch("agent.GitHubClient", return_value=mock_gh_instance), \
         patch("agent.create_branch"), \
         patch("agent.commit_all"), \
         patch("agent.push_branch"), \
         patch("agent.revert_uncommitted") as mock_revert, \
         patch("agent.request_fix", side_effect=[
             ValueError("malformed"),
             {"file_path": "src/game.js", "explanation": "fixed it", "code": "ok"},
         ]), \
         patch("agent.validate_fix", return_value=True):
        code = agent.run(config_path)

    assert code == 0
    assert mock_revert.call_count == 1  # only the first, malformed attempt reverted
