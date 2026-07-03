import os
import re
import subprocess

import anthropic

_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "fix_prompt.txt")
_MODEL = "claude-sonnet-5"

_FILE_RE = re.compile(r"^FILE:\s*(.+)$", re.MULTILINE)
_EXPLANATION_RE = re.compile(r"EXPLANATION:\s*(.*?)\s*CODE:", re.DOTALL)
_CODE_RE = re.compile(r"```[A-Za-z0-9_+-]*\r?\n(.*?)```", re.DOTALL)


def build_fix_prompt(cmd: str, stdout: str, stderr: str, relevant_files: dict) -> str:
    with open(_TEMPLATE_PATH, "r") as f:
        template = f.read()

    files_block = "\n\n".join(
        f"{path}:\n```\n{content}\n```" for path, content in relevant_files.items()
    )

    return template.format(cmd=cmd, stdout=stdout, stderr=stderr, relevant_files=files_block)


def _parse_fix_response(text: str) -> dict:
    file_matches = _FILE_RE.findall(text)
    if len(file_matches) == 0:
        raise ValueError("fix response is missing a FILE: marker")
    if len(file_matches) > 1:
        raise ValueError(f"fix response declares more than one file: {file_matches}")

    file_path = file_matches[0].strip()
    if not file_path or file_path.startswith(("/", "..")) or ":" in file_path:
        raise ValueError(f"fix response has an unsafe or empty file path: {file_path!r}")

    explanation_match = _EXPLANATION_RE.search(text)
    if not explanation_match:
        raise ValueError("fix response is missing an EXPLANATION: section before CODE:")
    explanation = explanation_match.group(1).strip()

    code_match = _CODE_RE.search(text)
    if not code_match:
        raise ValueError("fix response is missing a fenced CODE: block")
    code = code_match.group(1)

    return {"file_path": file_path, "explanation": explanation, "code": code}


def request_fix(prompt: str) -> dict:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return _parse_fix_response(text)


def validate_fix(repo_path: str, file_path: str) -> bool:
    # `git status --porcelain` (not `git diff --name-only`) so a fix that
    # creates a brand-new file is also detected -- a plain `git diff` only
    # shows changes to files git already tracks.
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        text=True,
        capture_output=True,
    )
    changed = [line[3:].strip() for line in result.stdout.splitlines() if line.strip()]
    return changed == [file_path]
