import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from checks_runner import run_cmd, run_checks, has_failures

PY = f'"{sys.executable}"'


def test_run_cmd_success():
    result = run_cmd(f"{PY} -c \"print(1)\"", cwd=".")
    assert result["code"] == 0
    assert "1" in result["stdout"]
    assert result["cmd"] == f"{PY} -c \"print(1)\""


def test_run_cmd_failure_captures_stderr():
    result = run_cmd(f"{PY} -c \"import sys; sys.stderr.write('boom'); sys.exit(1)\"", cwd=".")
    assert result["code"] == 1
    assert "boom" in result["stderr"]


def test_run_cmd_missing_cwd_does_not_raise():
    result = run_cmd(f"{PY} -c \"print(1)\"", cwd="./this-path-does-not-exist")
    assert result["code"] != 0
    assert result["stderr"]


def test_run_checks_runs_every_check_even_after_a_failure():
    checks = [
        f"{PY} -c \"import sys; sys.exit(1)\"",
        f"{PY} -c \"print('still ran')\"",
    ]
    results = run_checks(".", checks)
    assert len(results) == 2
    assert results[0]["code"] == 1
    assert results[1]["code"] == 0
    assert "still ran" in results[1]["stdout"]


def test_has_failures_true_when_any_check_fails():
    results = [{"code": 0}, {"code": 1}, {"code": 0}]
    assert has_failures(results) is True


def test_has_failures_false_when_all_pass():
    results = [{"code": 0}, {"code": 0}]
    assert has_failures(results) is False


def test_has_failures_empty_list():
    assert has_failures([]) is False
