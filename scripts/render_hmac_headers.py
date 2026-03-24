#!/usr/bin/env python3
import argparse
import hashlib
import json
import shlex
import sys
import time
from pathlib import Path


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def load_body(args: argparse.Namespace) -> bytes:
    if args.body is not None:
        return args.body.encode("utf-8")
    if args.body_file is None:
        return b""
    if args.body_file == "-":
        return sys.stdin.buffer.read()
    return Path(args.body_file).read_bytes()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render HMAC headers for headless Frigate API requests."
    )
    parser.add_argument("--env-file", default=".env", help="Path to the env file.")
    parser.add_argument("--key-id", required=True, help="Key id from FRIGATE_API_HMAC_KEYS_JSON.")
    body_group = parser.add_mutually_exclusive_group()
    body_group.add_argument("--body", help="Inline request body string.")
    body_group.add_argument(
        "--body-file",
        help="Path to request body file. Use '-' to read from stdin.",
    )
    parser.add_argument(
        "--timestamp",
        type=int,
        default=int(time.time()),
        help="Unix timestamp to embed in the signature.",
    )
    parser.add_argument(
        "--curl",
        action="store_true",
        help="Print shell-safe curl header arguments.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    env_file = Path(args.env_file)

    if not env_file.is_file():
        print(f"Env file not found: {env_file}", file=sys.stderr)
        return 2

    env_values = load_env(env_file)
    registry_raw = env_values.get("FRIGATE_API_HMAC_KEYS_JSON", "")
    if not registry_raw:
        print("FRIGATE_API_HMAC_KEYS_JSON is not configured.", file=sys.stderr)
        return 2

    try:
        registry = json.loads(registry_raw)
    except json.JSONDecodeError as exc:
        print(f"Invalid FRIGATE_API_HMAC_KEYS_JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(registry, dict):
        print("FRIGATE_API_HMAC_KEYS_JSON must be a JSON object.", file=sys.stderr)
        return 2

    key_config = registry.get(args.key_id)
    if not isinstance(key_config, dict):
        print(f"Key id not found: {args.key_id}", file=sys.stderr)
        return 2

    secret = key_config.get("secret")
    if not isinstance(secret, str) or not secret:
        print(f"Key id '{args.key_id}' does not have a valid secret.", file=sys.stderr)
        return 2

    body = load_body(args)
    timestamp = str(args.timestamp)
    signature = hashlib.sha256(body + timestamp.encode("utf-8") + secret.encode("utf-8")).hexdigest()

    headers = {
        "X-Key-Id": args.key_id,
        "X-Timestamp": timestamp,
        "X-Signature": signature,
    }

    if args.curl:
        parts = [f"-H {shlex.quote(f'{name}: {value}')}" for name, value in headers.items()]
        print(" ".join(parts))
        return 0

    for name, value in headers.items():
        print(f"{name}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
