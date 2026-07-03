from github import Github


class GitHubClient:
    """Thin wrapper around PyGithub, scoped to one repo.

    Takes the repo as a constructor param (not hard-coded) so the same
    class can be pointed at any repo, and so tests can inject a mock
    Github client instead of hitting the network.
    """

    def __init__(self, token: str, repo_full_name: str):
        self._gh = Github(token)
        self._repo = self._gh.get_repo(repo_full_name)

    def find_existing_issue(self, fingerprint: str):
        for issue in self._repo.get_issues(state="open", labels=["agent-maintenance"]):
            if fingerprint in (issue.body or ""):
                return issue.number
        return None

    def create_issue(self, title: str, body: str, labels: list) -> int:
        issue = self._repo.create_issue(title=title, body=body, labels=labels)
        return issue.number

    def comment_issue(self, issue_number: int, body: str) -> None:
        issue = self._repo.get_issue(issue_number)
        issue.create_comment(body)

    def add_label(self, issue_number: int, label: str) -> None:
        issue = self._repo.get_issue(issue_number)
        issue.add_to_labels(label)

    def create_pull_request(self, branch_name: str, title: str, body: str, base: str = "main") -> str:
        pr = self._repo.create_pull(title=title, body=body, head=branch_name, base=base)
        return pr.html_url
