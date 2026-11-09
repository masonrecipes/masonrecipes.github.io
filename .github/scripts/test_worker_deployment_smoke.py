import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github/scripts/smoke_worker_deployment.sh"
REPOSITORY = "masonrecipes/masonrecipes.github.io"
SHA = "fixture-sha"
WORKERS_BUILD = "Workers Builds: mason-recipe-submissions"

GH_STUB = f"""
if [[ "$1" != api || "$2" != "repos/{REPOSITORY}/commits/{SHA}/check-runs" || "$3" != --jq ]]; then
  echo "unexpected gh call: $*" >&2
  exit 1
fi
calls=$(( $(cat "$STUB_DIR/gh-calls" 2>/dev/null || echo 0) + 1 ))
echo "$calls" > "$STUB_DIR/gh-calls"
fixture="$STUB_DIR/check-runs-$calls.json"
[[ -f "$fixture" ]] || fixture="$STUB_DIR/check-runs-last.json"
jq -r "$4" "$fixture"
"""

CURL_STUB = """
url="" authorization="" origin=""
while (($#)); do
  case "$1" in
    --header)
      case "$2" in
        Origin:*) origin="${2#Origin: }" ;;
        Authorization:*) authorization="$2" ;;
      esac
      shift 2 ;;
    https://*) url="$1"; shift ;;
    *) shift ;;
  esac
done
if [[ "$WORKER_STATE" == open ]]; then printf 200; exit 0; fi
case "$url" in
  */submit) [[ -n "$origin" && "$origin" != https://masonrecipes.github.io ]] && printf 403 || printf 400 ;;
  */draft) [[ -z "$authorization" ]] && printf 401 || printf 400 ;;
  *) printf 404 ;;
esac
"""


def check_run(name, status, conclusion=None):
    return {"name": name, "status": status, "conclusion": conclusion}


class WorkerDeploymentSmokeTests(unittest.TestCase):
    def run_smoke(self, check_run_responses, worker_state="deployed"):
        with tempfile.TemporaryDirectory() as directory:
            stub_dir = Path(directory)
            bin_dir = stub_dir / "bin"
            bin_dir.mkdir()
            for number, check_runs in enumerate(check_run_responses, start=1):
                body = json.dumps({"total_count": len(check_runs), "check_runs": check_runs})
                (stub_dir / f"check-runs-{number}.json").write_text(body)
                (stub_dir / "check-runs-last.json").write_text(body)
            self.write_command(bin_dir / "gh", GH_STUB)
            self.write_command(bin_dir / "curl", CURL_STUB)
            self.write_command(bin_dir / "sleep", "exit 0\n")
            env = dict(
                os.environ,
                PATH=f"{bin_dir}:{os.environ['PATH']}",
                STUB_DIR=str(stub_dir),
                GITHUB_SHA=SHA,
                GITHUB_REPOSITORY=REPOSITORY,
                GH_TOKEN="fake-token",
                WORKER_STATE=worker_state,
            )
            return subprocess.run(
                ["bash", str(SCRIPT)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

    @staticmethod
    def write_command(path, body):
        path.write_text("#!/usr/bin/env bash\n" + body)
        path.chmod(0o755)

    def test_smokes_only_after_the_matching_build_succeeds(self):
        result = self.run_smoke([
            [check_run("Tests", "completed", "success"), check_run(WORKERS_BUILD, "in_progress")],
            [check_run("Tests", "completed", "success"), check_run(WORKERS_BUILD, "completed", "success")],
        ])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Attempt 1/40: Workers Builds status is in_progress:.", result.stdout)
        self.assertIn("completed successfully for fixture-sha", result.stdout)
        self.assertIn("wrong origin returned 403", result.stdout)
        self.assertIn("unauthenticated /draft returned 401", result.stdout)

    def test_waits_while_only_other_checks_have_finished(self):
        result = self.run_smoke([[check_run("Tests", "completed", "success")]])

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Workers Builds status is missing.", result.stdout)
        self.assertIn("did not complete successfully within the wait window", result.stderr)

    def test_fails_when_workers_builds_fails(self):
        result = self.run_smoke([
            [check_run("Tests", "completed", "success"), check_run(WORKERS_BUILD, "completed", "failure")],
        ])

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Workers Builds finished with completed:failure", result.stderr)

    def test_fails_when_public_endpoint_responses_are_wrong(self):
        result = self.run_smoke(
            [[check_run(WORKERS_BUILD, "completed", "success")]],
            worker_state="open",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected /submit 403 and /draft 401", result.stderr)


if __name__ == "__main__":
    unittest.main()
