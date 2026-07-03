import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from github_client import GitHubClient


def make_client(mock_repo):
    with patch("github_client.Github") as MockGithub:
        MockGithub.return_value.get_repo.return_value = mock_repo
        client = GitHubClient("fake-token", "owner/snake-game")
    return client


def test_constructor_does_not_hardcode_repo_name():
    mock_repo = MagicMock()
    with patch("github_client.Github") as MockGithub:
        MockGithub.return_value.get_repo.return_value = mock_repo
        GitHubClient("fake-token", "someone-else/other-repo")
        MockGithub.return_value.get_repo.assert_called_once_with("someone-else/other-repo")


def test_find_existing_issue_matches_fingerprint():
    mock_repo = MagicMock()
    issue1 = MagicMock(number=1, body="unrelated failure")
    issue2 = MagicMock(number=2, body="failure fingerprint:abc123 details here")
    mock_repo.get_issues.return_value = [issue1, issue2]

    client = make_client(mock_repo)
    found = client.find_existing_issue("fingerprint:abc123")

    assert found == 2
    mock_repo.get_issues.assert_called_once_with(state="open", labels=["agent-maintenance"])


def test_find_existing_issue_returns_none_when_no_match():
    mock_repo = MagicMock()
    mock_repo.get_issues.return_value = [MagicMock(number=1, body="something else")]

    client = make_client(mock_repo)
    assert client.find_existing_issue("fingerprint:abc123") is None


def test_find_existing_issue_handles_none_body():
    mock_repo = MagicMock()
    mock_repo.get_issues.return_value = [MagicMock(number=1, body=None)]

    client = make_client(mock_repo)
    assert client.find_existing_issue("fingerprint:abc123") is None


def test_create_issue_returns_number():
    mock_repo = MagicMock()
    mock_repo.create_issue.return_value = MagicMock(number=42)

    client = make_client(mock_repo)
    number = client.create_issue("title", "body", ["agent-maintenance"])

    assert number == 42
    mock_repo.create_issue.assert_called_once_with(
        title="title", body="body", labels=["agent-maintenance"]
    )


def test_comment_issue_posts_comment_on_correct_issue():
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_repo.get_issue.return_value = mock_issue

    client = make_client(mock_repo)
    client.comment_issue(7, "hello")

    mock_repo.get_issue.assert_called_once_with(7)
    mock_issue.create_comment.assert_called_once_with("hello")


def test_add_label_applies_label_to_correct_issue():
    mock_repo = MagicMock()
    mock_issue = MagicMock()
    mock_repo.get_issue.return_value = mock_issue

    client = make_client(mock_repo)
    client.add_label(7, "needs-human")

    mock_repo.get_issue.assert_called_once_with(7)
    mock_issue.add_to_labels.assert_called_once_with("needs-human")


def test_create_pull_request_returns_url_and_uses_default_base():
    mock_repo = MagicMock()
    mock_repo.create_pull.return_value = MagicMock(html_url="https://github.com/owner/repo/pull/9")

    client = make_client(mock_repo)
    url = client.create_pull_request("agent-maintenance/fix-1", "title", "body")

    assert url == "https://github.com/owner/repo/pull/9"
    mock_repo.create_pull.assert_called_once_with(
        title="title", body="body", head="agent-maintenance/fix-1", base="main"
    )
