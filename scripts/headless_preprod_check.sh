#!/usr/bin/env bash
set -euo pipefail

BASE_URL="http://127.0.0.1:5000"
HEADERS=()

usage() {
  cat <<'EOF'
Usage:
  scripts/headless_preprod_check.sh [--base-url URL] [-H "Header: value"]...

Examples:
  scripts/headless_preprod_check.sh
  scripts/headless_preprod_check.sh --base-url http://localhost:5000
  scripts/headless_preprod_check.sh -H "Authorization: Bearer <token>"
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    -H|--header)
      HEADERS+=("-H" "${2:-}")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Invalid argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required." >&2
  exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 2
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

request_json() {
  local path="$1"
  local output="$2"
  curl --silent --show-error --location \
    --output "$output" \
    --write-out "%{http_code}" \
    "${HEADERS[@]}" \
    "${BASE_URL}${path}" || true
}

health_body="${tmp_dir}/healthz.json"
ready_body="${tmp_dir}/readyz.json"
release_body="${tmp_dir}/release_gate.json"
prod_body="${tmp_dir}/production_readiness.json"

health_code="$(request_json "/healthz" "$health_body")"
ready_code="$(request_json "/readyz" "$ready_body")"
release_code="$(request_json "/v1/resilience/release-gate" "$release_body")"
prod_code="$(request_json "/v1/production/readiness" "$prod_body")"

python3 - "$health_code" "$health_body" "$ready_code" "$ready_body" "$release_code" "$release_body" "$prod_code" "$prod_body" <<'PY'
import json
import sys
from typing import Any


def load_json(path: str) -> dict[str, Any] | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


health_code = int(sys.argv[1])
health_data = load_json(sys.argv[2])
ready_code = int(sys.argv[3])
ready_data = load_json(sys.argv[4])
release_code = int(sys.argv[5])
release_data = load_json(sys.argv[6])
prod_code = int(sys.argv[7])
prod_data = load_json(sys.argv[8])

ok = True
lines: list[str] = []

if health_code == 200 and isinstance(health_data, dict) and health_data.get("status") == "ok":
    lines.append("[OK] /healthz")
else:
    ok = False
    lines.append(f"[FAIL] /healthz (http={health_code})")

if ready_code == 200 and isinstance(ready_data, dict) and bool(ready_data.get("ready", False)):
    lines.append("[OK] /readyz")
else:
    ok = False
    reasons = as_list(ready_data.get("reasons") if isinstance(ready_data, dict) else [])
    warnings = as_list(ready_data.get("warnings") if isinstance(ready_data, dict) else [])
    detail = f"reasons={reasons} warnings={warnings}" if (reasons or warnings) else "no details"
    lines.append(f"[FAIL] /readyz (http={ready_code}) {detail}")

if release_code in {401, 403}:
    ok = False
    lines.append(
        "[FAIL] /v1/resilience/release-gate unauthorized. Provide reader auth header with -H."
    )
elif release_code == 200 and isinstance(release_data, dict) and bool(release_data.get("passed", False)):
    lines.append("[OK] /v1/resilience/release-gate")
else:
    ok = False
    reasons = as_list(release_data.get("reasons") if isinstance(release_data, dict) else [])
    detail = f"reasons={reasons}" if reasons else "no details"
    lines.append(f"[FAIL] /v1/resilience/release-gate (http={release_code}) {detail}")

if prod_code in {401, 403}:
    ok = False
    lines.append(
        "[FAIL] /v1/production/readiness unauthorized. Provide reader auth header with -H."
    )
else:
    summary = prod_data.get("summary", {}) if isinstance(prod_data, dict) else {}
    production_ready = bool(summary.get("production_ready", False)) if isinstance(summary, dict) else False
    pending = as_list(prod_data.get("pending_phase_ids") if isinstance(prod_data, dict) else [])
    if prod_code == 200 and production_ready:
        lines.append("[OK] /v1/production/readiness")
    else:
        ok = False
        lines.append(
            "[FAIL] /v1/production/readiness "
            f"(http={prod_code}) production_ready={production_ready} pending={pending}"
        )

print("Headless Pre-Production Check")
for item in lines:
    print(item)

if ok:
    print("GO/NO-GO: GO")
    raise SystemExit(0)

print("GO/NO-GO: NO-GO")
raise SystemExit(1)
PY
