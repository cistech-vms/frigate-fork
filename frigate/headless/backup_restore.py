import json
import os
import shutil
import time
from dataclasses import dataclass
from typing import Any

from frigate.const import CONFIG_DIR


@dataclass
class BackupRestoreManager:
    base_dir: str = f"{CONFIG_DIR}/backups"

    def __post_init__(self) -> None:
        os.makedirs(self.base_dir, exist_ok=True)

    def create_backup(
        self, *, name: str, sources: dict[str, str], mode: str = "incremental"
    ) -> dict[str, Any]:
        ts = int(time.time())
        backup_id = f"{name}-{ts}"
        target_dir = os.path.join(self.base_dir, backup_id)
        os.makedirs(target_dir, exist_ok=True)
        copied: list[str] = []
        for logical_name, source in sources.items():
            if not source or not os.path.exists(source):
                continue
            dest = os.path.join(target_dir, f"{logical_name}.bak")
            if os.path.isdir(source):
                shutil.copytree(source, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(source, dest)
            copied.append(logical_name)
        manifest = {
            "backup_id": backup_id,
            "mode": mode,
            "created_at": ts,
            "sources": copied,
            "rpo_sec": 300 if mode == "incremental" else 3600,
            "rto_sec": 900,
        }
        with open(os.path.join(target_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, separators=(",", ":"), sort_keys=True)
        return manifest

    def list_backups(self, limit: int = 30) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for entry in sorted(os.listdir(self.base_dir), reverse=True):
            manifest_path = os.path.join(self.base_dir, entry, "manifest.json")
            if not os.path.exists(manifest_path):
                continue
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    items.append(json.load(f))
            except Exception:
                continue
        return items[: max(1, min(200, int(limit)))]

    def restore_backup(self, backup_id: str, targets: dict[str, str]) -> dict[str, Any]:
        source_dir = os.path.join(self.base_dir, backup_id)
        if not os.path.isdir(source_dir):
            raise ValueError("backup_not_found")
        restored: list[str] = []
        for logical_name, target_path in targets.items():
            backup_path = os.path.join(source_dir, f"{logical_name}.bak")
            if not os.path.exists(backup_path):
                continue
            os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
            if os.path.isdir(backup_path):
                shutil.copytree(backup_path, target_path, dirs_exist_ok=True)
            else:
                shutil.copy2(backup_path, target_path)
            restored.append(logical_name)
        return {"backup_id": backup_id, "restored": restored, "restored_at": int(time.time())}
