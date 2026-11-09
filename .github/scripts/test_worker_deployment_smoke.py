import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github/scripts/smoke_worker_deployment.sh"


class WorkerDeploymentSmokeTests(unittest.TestCase):
    def run_smoke(self, build_status, submit_status="403", draft_status="401"):
        with tempfile.TemporaryDirectory() as directory:
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            self.write_command(
                bin_dir / "gh",
                'printf "%s\\n" "$GH_STUB_STATUS"\n',
            )
            self.write_command(
                bin_dir / "curl",
                'for arg in "$@"; do\n'
                '  case "$arg" in\n'
                '    */submit) printf "%s" "$SUBMIT_STATUS" ;;\n'
                '    */draft) printf "%s" "$DRAFT_STATUS" ;;\n'
                '  esac\n'
                'done\n',
            )
            self.write_command(bin_dir / "sleep", "exit 0\n")
            env = dict(
                os.environ,
                PATH=f"{bin_dir}:{os.environ['PATH']}",
                GITHUB_SHA="fixture-sha",
                GITHUB_REPOSITORY="masonrecipes/masonrecipes.github.io",
                GH_TOKEN="fake-token",
                GH_STUB_STATUS=build_status,
                SUBMIT_STATUS=submit_status,
                DRAFT_STATUS=draft_status,
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
        result = self.run_smoke("completed:success")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("completed successfully for fixture-sha", result.stdout)
        self.assertIn("wrong origin returned 403", result.stdout)
        self.assertIn("unauthenticated /draft returned 401", result.stdout)

    def test_fails_when_workers_builds_fails(self):
        result = self.run_smoke("completed:failure")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Workers Builds finished with completed:failure", result.stderr)

    def test_fails_when_public_endpoint_responses_are_wrong(self):
        result = self.run_smoke("completed:success", submit_status="200", draft_status="200")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected /submit 403 and /draft 401", result.stderr)


if __name__ == "__main__":
    unittest.main()
