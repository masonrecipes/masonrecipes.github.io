#!/usr/bin/env python3
"""Run every test suite; exit nonzero on any failure and print {"pass_rate": ...} last."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".pydeps"


def run(cmd, cwd=ROOT, env=None):
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode, proc.stdout + proc.stderr


def count(pattern, text):
    match = re.search(pattern, text, re.M)
    return int(match.group(1)) if match else 0


def main():
    code, _ = run([sys.executable, "-m", "pip", "install", "--quiet", "--target", str(DEPS), "-r", "requirements-test.txt"])
    if code:
        print(json.dumps({"pass_rate": 0.0}))
        return 1

    total = passed = 0
    code, _ = run(["npm", "ci"], cwd=ROOT / "submit-worker")
    if code:
        print(json.dumps({"pass_rate": 0.0}))
        return 1
    code, out = run(["node", "--test", "--test-reporter=tap"], cwd=ROOT / "submit-worker")
    node_total, node_pass = count(r"^# tests (\d+)", out), count(r"^# pass (\d+)", out)
    total += node_total
    passed += node_pass
    failed = code != 0 or node_total == 0

    env = dict(os.environ, PYTHONPATH=str(DEPS))
    code, out = run([sys.executable, "-m", "unittest", "discover", "-s", ".github/scripts", "-p", "test_*.py"], env=env)
    py_total = count(r"^Ran (\d+) tests?", out)
    bad = sum(count(rf"{kind}=(\d+)", out) for kind in ("failures", "errors", "skipped", "expected failures"))
    total += py_total
    passed += max(py_total - bad, 0)
    failed = failed or code != 0 or py_total == 0

    failed = failed or passed < total
    rate = passed / total if total else 0.0
    if failed and rate == 1.0:
        rate = 0.0
    print(json.dumps({"pass_rate": rate}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
