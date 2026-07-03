import subprocess


def run_cmd(cmd: str, cwd: str) -> dict:
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=True,
            text=True,
            capture_output=True,
        )
    except OSError as exc:
        # e.g. cwd doesn't exist -- still return the expected shape instead
        # of letting callers deal with an uncaught exception.
        return {"cmd": cmd, "code": -1, "stdout": "", "stderr": str(exc)}

    return {
        "cmd": cmd,
        "code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run_checks(repo_path: str, checks: list) -> list:
    return [run_cmd(check, repo_path) for check in checks]


def has_failures(results: list) -> bool:
    return any(r["code"] != 0 for r in results)
