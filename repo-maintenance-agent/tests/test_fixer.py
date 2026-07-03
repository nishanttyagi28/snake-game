import os
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fixer import build_fix_prompt, request_fix, validate_fix


def test_build_fix_prompt_fills_in_all_placeholders():
    prompt = build_fix_prompt(
        cmd="npx playwright test",
        stdout="6 passed",
        stderr="1 failed: score did not increase",
        relevant_files={"src/game.js": "const x = 1;"},
    )

    assert "npx playwright test" in prompt
    assert "6 passed" in prompt
    assert "score did not increase" in prompt
    assert "src/game.js" in prompt
    assert "const x = 1;" in prompt
    assert "Modify exactly one file." in prompt


def _mock_anthropic_response(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


WELL_FORMED_RESPONSE = """\
FILE: src/game.js
EXPLANATION: The score assignment was a no-op; increment it instead.
CODE:
```js
this.score += 1;
```
"""


def test_request_fix_parses_a_well_formed_response():
    with patch("fixer.anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = _mock_anthropic_response(
            WELL_FORMED_RESPONSE
        )
        result = request_fix("some prompt")

    assert result["file_path"] == "src/game.js"
    assert "no-op" in result["explanation"]
    assert result["code"].strip() == "this.score += 1;"


def test_request_fix_raises_on_missing_file_marker():
    text = "EXPLANATION: no file given\nCODE:\n```js\nx = 1;\n```\n"
    with patch("fixer.anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = _mock_anthropic_response(text)
        with pytest.raises(ValueError, match="FILE:"):
            request_fix("some prompt")


def test_request_fix_raises_on_multiple_files():
    text = (
        "FILE: src/game.js\n"
        "FILE: index.html\n"
        "EXPLANATION: touches two files\n"
        "CODE:\n```js\nx = 1;\n```\n"
    )
    with patch("fixer.anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = _mock_anthropic_response(text)
        with pytest.raises(ValueError, match="more than one file"):
            request_fix("some prompt")


def test_request_fix_raises_on_missing_code_block():
    text = "FILE: src/game.js\nEXPLANATION: no code block follows\n"
    with patch("fixer.anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = _mock_anthropic_response(text)
        with pytest.raises(ValueError, match="CODE:"):
            request_fix("some prompt")


def test_request_fix_raises_on_path_outside_repo():
    text = (
        "FILE: ../../etc/passwd\n"
        "EXPLANATION: sneaky\n"
        "CODE:\n```js\nx = 1;\n```\n"
    )
    with patch("fixer.anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = _mock_anthropic_response(text)
        with pytest.raises(ValueError, match="unsafe"):
            request_fix("some prompt")


@pytest.fixture
def scratch_repo():
    root = tempfile.mkdtemp(prefix="fixer_test_")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    with open(os.path.join(root, "src_game.js"), "w") as f:
        f.write("original\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)

    yield root

    shutil.rmtree(root, ignore_errors=True)


def test_validate_fix_true_when_only_declared_file_changed(scratch_repo):
    with open(os.path.join(scratch_repo, "src_game.js"), "w") as f:
        f.write("changed\n")

    assert validate_fix(scratch_repo, "src_game.js") is True


def test_validate_fix_true_for_newly_created_file(scratch_repo):
    with open(os.path.join(scratch_repo, "new_file.js"), "w") as f:
        f.write("new\n")

    assert validate_fix(scratch_repo, "new_file.js") is True


def test_validate_fix_false_when_other_files_also_changed(scratch_repo):
    with open(os.path.join(scratch_repo, "src_game.js"), "w") as f:
        f.write("changed\n")
    with open(os.path.join(scratch_repo, "extra.js"), "w") as f:
        f.write("oops\n")

    assert validate_fix(scratch_repo, "src_game.js") is False


def test_validate_fix_false_when_nothing_changed(scratch_repo):
    assert validate_fix(scratch_repo, "src_game.js") is False
