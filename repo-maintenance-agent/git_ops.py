import os

import git


def clone_or_pull(repo_url: str, local_path: str) -> None:
    if os.path.isdir(os.path.join(local_path, ".git")):
        repo = git.Repo(local_path)
        origin = repo.remotes.origin
        origin.fetch()
        origin.pull()
    else:
        git.Repo.clone_from(repo_url, local_path)


def create_branch(repo_path: str, branch_name: str) -> None:
    repo = git.Repo(repo_path)
    # -B creates the branch or resets it to HEAD if it already exists (e.g. a
    # retry reusing a branch name from a previous run), instead of erroring.
    repo.git.checkout("-B", branch_name)


def commit_all(repo_path: str, message: str) -> None:
    repo = git.Repo(repo_path)
    if not repo.is_dirty(untracked_files=True):
        return
    repo.git.add(A=True)
    repo.index.commit(message)


def push_branch(repo_path: str, branch_name: str) -> None:
    repo = git.Repo(repo_path)
    repo.git.push("--set-upstream", "origin", branch_name)


def revert_uncommitted(repo_path: str) -> None:
    repo = git.Repo(repo_path)
    repo.git.reset("--hard")
    repo.git.clean("-fd")
