import time
from typing import Any

CURRENT_API_CONTRACT_VERSION = "1.0"
CURRENT_EVENT_CONTRACT_VERSION = "1.0"


def with_contract_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    data.setdefault("contract", {})
    data["contract"]["api_version"] = CURRENT_API_CONTRACT_VERSION
    data["contract"]["event_version"] = CURRENT_EVENT_CONTRACT_VERSION
    data["contract"]["emitted_at"] = int(time.time())
    return data


def validate_contract_compatibility(
    requested_api_version: str | None, supported_versions: list[str] | None = None
) -> tuple[bool, str]:
    supported = supported_versions or [CURRENT_API_CONTRACT_VERSION]
    if not requested_api_version:
        return True, "default_version"
    if requested_api_version in supported:
        return True, "compatible"
    return False, "unsupported_contract_version"
