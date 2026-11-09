#!/usr/bin/env bash
set -euo pipefail

endpoint="https://mason-recipe-submissions.david-beihl.workers.dev"
build_attempts=40
smoke_attempts=20
delay_seconds=15

echo "Waiting for the Workers Builds check on $GITHUB_SHA."
for ((attempt = 1; attempt <= build_attempts; attempt++)); do
  build_status="$(gh api "repos/$GITHUB_REPOSITORY/commits/$GITHUB_SHA/check-runs" \
    --jq '[.check_runs[] | select(.name == "Workers Builds: mason-recipe-submissions")] | last | if . == null then "missing" else "\(.status):\(.conclusion // "")" end' || true)"

  if [[ "$build_status" == "completed:success" ]]; then
    echo "Workers Builds completed successfully for $GITHUB_SHA."
    break
  fi
  if [[ "$build_status" == completed:* ]]; then
    echo "Workers Builds finished with $build_status for $GITHUB_SHA." >&2
    exit 1
  fi

  echo "Attempt $attempt/$build_attempts: Workers Builds status is $build_status."
  if ((attempt < build_attempts)); then
    sleep "$delay_seconds"
  fi
done

if [[ "$build_status" != "completed:success" ]]; then
  echo "Workers Builds did not complete successfully within the wait window." >&2
  exit 1
fi

status_code() {
  local url="$1"
  local origin_header="${2-}"
  local args=(--silent --show-error --max-time 10 --output /dev/null --write-out '%{http_code}' \
    --request POST "$url" --header 'Content-Type: application/json' --data '{}')
  if [[ -n "$origin_header" ]]; then
    args+=(--header "$origin_header")
  fi
  curl "${args[@]}" || true
}

for ((attempt = 1; attempt <= smoke_attempts; attempt++)); do
  origin_status="$(status_code "$endpoint/submit" 'Origin: https://not-masonrecipes.example')"
  draft_status="$(status_code "$endpoint/draft")"

  if [[ "$origin_status" == 403 && "$draft_status" == 401 ]]; then
    echo "Worker smoke checks passed: wrong origin returned 403 and unauthenticated /draft returned 401."
    exit 0
  fi

  echo "Attempt $attempt/$smoke_attempts: /submit returned $origin_status (expected 403); /draft returned $draft_status (expected 401)."
  if ((attempt < smoke_attempts)); then
    sleep "$delay_seconds"
  fi
done

echo "Worker smoke checks failed after the successful build: expected /submit 403 and /draft 401." >&2
exit 1
