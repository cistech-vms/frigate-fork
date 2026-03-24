#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "${script_dir}/.." && pwd)"

ENV_FILE="${repo_dir}/.env"
ENV_TEMPLATE="${repo_dir}/.env.production.example"
CONFIG_FILE="${repo_dir}/config/config.yml"
CONFIG_TEMPLATE="${repo_dir}/config/config.headless.example.yml"
TENANT_ID="tenant-local"
FORCE_ROTATE=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/bootstrap_headless_deploy.sh [options]

Options:
  --env-file PATH                  Override destination .env path.
  --env-template PATH              Override source env template.
  --config-file PATH               Override destination config path.
  --config-template PATH           Override source config template.
  --tenant-id VALUE                Tenant id to embed in generated API keys.
  --force-rotate-api-secrets       Rotate HMAC and JWT secrets even if present.
  -h, --help                       Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --env-template)
      ENV_TEMPLATE="$2"
      shift 2
      ;;
    --config-file)
      CONFIG_FILE="$2"
      shift 2
      ;;
    --config-template)
      CONFIG_TEMPLATE="$2"
      shift 2
      ;;
    --tenant-id)
      TENANT_ID="$2"
      shift 2
      ;;
    --force-rotate-api-secrets)
      FORCE_ROTATE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_bin() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 2
  fi
}

ensure_parent_dir() {
  mkdir -p "$(dirname -- "$1")"
}

copy_if_missing() {
  local source="$1"
  local target="$2"

  if [[ -f "$target" ]]; then
    return 0
  fi

  if [[ ! -f "$source" ]]; then
    echo "Template not found: $source" >&2
    exit 2
  fi

  ensure_parent_dir "$target"
  cp "$source" "$target"
}

current_env_value() {
  local key="$1"
  awk -F= -v key="$key" '
    $1 == key {
      sub(/^[^=]*=/, "", $0)
      value = $0
    }
    END {
      print value
    }
  ' "$ENV_FILE"
}

upsert_env() {
  local key="$1"
  local value="$2"
  local tmp
  tmp="$(mktemp)"

  awk -v key="$key" -v value="$value" '
    BEGIN { replaced = 0 }
    index($0, key "=") == 1 {
      if (!replaced) {
        print key "=" value
        replaced = 1
      }
      next
    }
    { print }
    END {
      if (!replaced) {
        print key "=" value
      }
    }
  ' "$ENV_FILE" > "$tmp"

  mv "$tmp" "$ENV_FILE"
}

needs_secret_refresh() {
  local value="$1"
  [[ -z "$value" || "$value" == "__GENERATE__" || "$value" == *"change-me"* ]]
}

require_bin openssl
require_bin awk
require_bin mktemp

mkdir -p "${repo_dir}/config" "${repo_dir}/storage"
copy_if_missing "$ENV_TEMPLATE" "$ENV_FILE"
copy_if_missing "$CONFIG_TEMPLATE" "$CONFIG_FILE"

upsert_env "FRIGATE_HEADLESS" "true"
upsert_env "FRIGATE_INSTALLER_ENABLED" "true"
upsert_env "FRIGATE_API_AUTH_MODE" "hmac"
upsert_env "FRIGATE_TENANT_ID" "$TENANT_ID"
upsert_env "FRIGATE_METRICS_ENABLED" "true"
upsert_env "FRIGATE_LOG_FORMAT" "json"
upsert_env "FRIGATE_CFG__mqtt__enabled" "true"
upsert_env "FRIGATE_CFG__record__enabled" "true"

current_hmac="$(current_env_value "FRIGATE_API_HMAC_KEYS_JSON")"
current_jwt="$(current_env_value "FRIGATE_API_JWT_SECRET")"

if [[ "$FORCE_ROTATE" -eq 1 ]] || needs_secret_refresh "$current_hmac"; then
  admin_secret="$(openssl rand -hex 32)"
  reader_secret="$(openssl rand -hex 32)"
  hmac_json="$(printf '{"edge-admin":{"secret":"%s","role":"admin","tenant_id":"%s"},"edge-reader":{"secret":"%s","role":"reader","tenant_id":"%s"}}' "$admin_secret" "$TENANT_ID" "$reader_secret" "$TENANT_ID")"
  upsert_env "FRIGATE_API_HMAC_KEYS_JSON" "$hmac_json"
fi

if [[ "$FORCE_ROTATE" -eq 1 ]] || needs_secret_refresh "$current_jwt"; then
  jwt_secret="$(openssl rand -hex 32)"
  upsert_env "FRIGATE_API_JWT_SECRET" "$jwt_secret"
fi

chmod 600 "$ENV_FILE"

echo "Bootstrap concluido."
echo "- Env: $ENV_FILE"
echo "- Config: $CONFIG_FILE"
echo "- Tenant: $TENANT_ID"
echo "- Proximo passo: docker compose -f docker-compose.prod.yml up -d --build"
