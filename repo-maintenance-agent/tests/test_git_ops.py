import os
import sys
import tempfile
import shutil

import git
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from git_ops import clone_or_pull, create_branch, commit_all, push_branch, revert_uncommitted


@pytest.fixture
def scratch_dirs():
    root = tempfile.mkdtemp(prefix="git_ops_test_")
    origin_path = os.path.join(root, "origin")
    local_path = os.path.join(root, "local")

    origin = git.Repo.init(origin_path, initial_branch="main")
    readme = os.path.join(origin_path, "README.md")
    with open(readme, "w") as f:
        f.write("hello\n")
    origin.index.add(["README.md"])
    origin.index.commit("initial commit")

    yield origin_path, local_path

    shutil.rmtree(root, ignore_errors=True)


def test_clone_or_pull_clones_when_local_path_missing(scratch_dirs):
    origin_path, local_path = scratch_dirs
    assert not os.path.isdir(local_path)

    clone_or_pull(origin_path, local_path)

    assert os.path.isdir(os.path.join(local_path, ".git"))
    assert os.path.isfile(os.path.join(local_path, "README.md"))


def test_clone_or_pull_pulls_when_local_path_exists(scratch_dirs):
    origin_path, local_path = scratch_dirs
    clone_or_pull(origin_path, local_path)

    # push a new commit to origin directly, then pull it via clone_or_pull again
    other_file = os.path.join(origin_path, "second.txt")
    with open(other_file, "w") as f:
        f.write("more\n")
    origin_repo = git.Repo(origin_path)
    origin_repo.index.add(["second.txt"])
    origin_repo.index.commit("second commit")

    clone_or_pull(origin_path, local_path)

    assert os.path.isfile(os.path.join(local_path, "second.txt"))


def test_create_branch_switches_to_new_branch(scratch_dirs):
    origin_path, local_path = scratch_dirs
    clone_or_pull(origin_path, local_path)

    create_branch(local_path, "agent-maintenance/fix-test-1")

    repo = git.Repo(local_path)
    assert repo.active_branch.name == "agent-maintenance/fix-test-1"


def test_create_branch_is_idempotent_on_reuse(scratch_dirs):
    origin_path, local_path = scratch_dirs
    clone_or_pull(origin_path, local_path)

    create_branch(local_path, "agent-maintenance/fix-test-1")
    # calling again with the same name must not raise
    create_branch(local_path, "agent-maintenance/fix-test-1")

    repo = git.Repo(local_path)
    assert repo.active_branch.name == "agent-maintenance/fix-test-1"


def test_commit_all_commits_working_tree_changes(scratch_dirs):
    origin_path, local_path = scratch_dirs
    clone_or_pull(origin_path, local_path)
    create_branch(local_path, "agent-maintenance/fix-test-1")

    with open(os.path.join(local_path, "README.md"), "a") as f:
        f.write("more text\n")

    repo = git.Repo(local_path)
    before_sha = repo.head.commit.hexsha

    commit_all(local_path, "fix: update readme")

    after_sha = repo.head.commit.hexsha
    assert after_sha != before_sha
    assert not repo.is_dirty(untracked_files=True)


def test_commit_all_is_a_noop_with_nothing_to_commit(scratch_dirs):
    origin_path, local_path = scratch_dirs
    clone_or_pull(origin_path, local_path)

    repo = git.Repo(local_path)
    before_sha = repo.head.commit.hexsha

    commit_all(local_path, "should not create a commit")

    assert repo.head.commit.hexsha == before_sha


def test_push_branch_pushes_to_origin(scratch_dirs):
    origin_path, local_path = scratch_dirs
    clone_or_pull(origin_path, local_path)
    create_branch(local_path, "agent-maintenance/fix-test-1")

    with open(os.path.join(local_path, "README.md"), "a") as f:
        f.write("more text\n")
    commit_all(local_path, "fix: update readme")

    push_branch(local_path, "agent-maintenance/fix-test-1")

    origin_repo = git.Repo(origin_path)
    assert "agent-maintenance/fix-test-1" in [h.name for h in origin_repo.heads]


def test_revert_uncommitted_discards_changes_and_untracked_files(scratch_dirs):
    origin_path, local_path = scratch_dirs
    clone_or_pull(origin_path, local_path)

    with open(os.path.join(local_path, "README.md"), "a") as f:
        f.write("dirty change\n")
    with open(os.path.join(local_path, "untracked.txt"), "w") as f:
        f.write("untracked\n")

    repo = git.Repo(local_path)
    assert repo.is_dirty(untracked_files=True)

    revert_uncommitted(local_path)

    assert not repo.is_dirty(untracked_files=True)
    assert not os.path.isfile(os.path.join(local_path, "untracked.txt"))
    with open(os.path.join(local_path, "README.md")) as f:
        assert f.read() == "hello\n"
