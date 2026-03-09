import hashlib
import os
import time
from typing import Any


class SupplyChainHardening:
    def __init__(self) -> None:
        self.state: dict[str, Any] = {
            "sbom": {},
            "vulnerabilities": [],
            "image_signature": "",
            "last_scan_ts": 0,
        }

    def generate_sbom(self, root_path: str) -> dict[str, Any]:
        files: list[str] = []
        for current_root, _, names in os.walk(root_path):
            for n in names:
                if n.endswith((".py", ".txt", ".md", ".yml", ".yaml", ".toml")):
                    files.append(os.path.relpath(os.path.join(current_root, n), root_path))
            if len(files) > 5000:
                break
        digest = hashlib.sha256("\n".join(sorted(files)).encode("utf-8")).hexdigest()
        sbom = {
            "generated_at": int(time.time()),
            "file_count": len(files),
            "manifest_digest": digest,
        }
        self.state["sbom"] = sbom
        return sbom

    def record_scan(self, vulnerabilities: list[dict[str, Any]]) -> dict[str, Any]:
        self.state["vulnerabilities"] = vulnerabilities[-500:]
        self.state["last_scan_ts"] = int(time.time())
        critical = [v for v in vulnerabilities if str(v.get("severity", "")).lower() == "critical"]
        self.state["release_blocked"] = len(critical) > 0
        return {
            "critical_count": len(critical),
            "release_blocked": self.state["release_blocked"],
            "last_scan_ts": self.state["last_scan_ts"],
        }

    def sign_image(self, image_ref: str) -> dict[str, Any]:
        signature = hashlib.sha256(f"{image_ref}:{int(time.time())}".encode("utf-8")).hexdigest()
        self.state["image_signature"] = signature
        return {"image_ref": image_ref, "signature": signature}

    def snapshot(self) -> dict[str, Any]:
        return self.state
