import json
import os
from dataclasses import dataclass
from typing import Any

from frigate.const import CONFIG_DIR


class ObjectStorageAdapter:
    def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        raise NotImplementedError

    def get_object_url(self, key: str) -> str:
        raise NotImplementedError

    def delete_object(self, key: str) -> None:
        raise NotImplementedError

    def head_object(self, key: str) -> bool:
        raise NotImplementedError


@dataclass
class LocalObjectStorageAdapter(ObjectStorageAdapter):
    base_dir: str = f"{CONFIG_DIR}/object_storage"
    base_url: str = "file://local-object-storage"

    def _path(self, key: str) -> str:
        safe_key = key.replace("..", "_").lstrip("/")
        return os.path.join(self.base_dir, safe_key)

    def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        del content_type
        path = self._path(key)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return self.get_object_url(key)

    def get_object_url(self, key: str) -> str:
        return f"{self.base_url}/{key.lstrip('/')}"

    def delete_object(self, key: str) -> None:
        path = self._path(key)
        if os.path.exists(path):
            os.unlink(path)

    def head_object(self, key: str) -> bool:
        return os.path.exists(self._path(key))


@dataclass
class S3CompatibleAdapter(ObjectStorageAdapter):
    provider: str
    bucket: str
    region: str | None
    endpoint: str | None
    access_key: str | None
    secret_key: str | None
    prefix: str
    local_fallback: LocalObjectStorageAdapter

    def _client(self):
        try:
            import boto3  # type: ignore
        except Exception as exc:
            raise RuntimeError("boto3_not_available") from exc
        kwargs: dict[str, Any] = {
            "service_name": "s3",
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
            "region_name": self.region,
        }
        if self.endpoint:
            kwargs["endpoint_url"] = self.endpoint
        return boto3.client(**kwargs)

    def _full_key(self, key: str) -> str:
        prefix = self.prefix.strip("/")
        if not prefix:
            return key.lstrip("/")
        return f"{prefix}/{key.lstrip('/')}"

    def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        full_key = self._full_key(key)
        try:
            client = self._client()
            client.put_object(Bucket=self.bucket, Key=full_key, Body=data, ContentType=content_type)
            return self.get_object_url(key)
        except Exception:
            return self.local_fallback.put_object(full_key, data, content_type=content_type)

    def get_object_url(self, key: str) -> str:
        full_key = self._full_key(key)
        if self.endpoint:
            return f"{self.endpoint.rstrip('/')}/{self.bucket}/{full_key}"
        return f"s3://{self.bucket}/{full_key}"

    def delete_object(self, key: str) -> None:
        full_key = self._full_key(key)
        try:
            client = self._client()
            client.delete_object(Bucket=self.bucket, Key=full_key)
        except Exception:
            self.local_fallback.delete_object(full_key)

    def head_object(self, key: str) -> bool:
        full_key = self._full_key(key)
        try:
            client = self._client()
            client.head_object(Bucket=self.bucket, Key=full_key)
            return True
        except Exception:
            return self.local_fallback.head_object(full_key)


def build_object_storage_adapter(config: dict[str, Any] | None = None) -> ObjectStorageAdapter:
    cfg = config or {}
    provider = str(cfg.get("provider") or os.getenv("FRIGATE_STORAGE_PROVIDER", "local")).strip().lower()
    local = LocalObjectStorageAdapter(
        base_dir=str(cfg.get("local_dir") or os.getenv("FRIGATE_STORAGE_LOCAL_DIR", f"{CONFIG_DIR}/object_storage")),
        base_url=str(cfg.get("base_url") or os.getenv("FRIGATE_STORAGE_BASE_URL", "file://local-object-storage")),
    )
    if provider not in {"s3", "r2"}:
        return local

    return S3CompatibleAdapter(
        provider=provider,
        bucket=str(cfg.get("bucket") or os.getenv("FRIGATE_STORAGE_BUCKET", "")),
        region=str(cfg.get("region") or os.getenv("FRIGATE_STORAGE_REGION", "")) or None,
        endpoint=str(cfg.get("endpoint") or os.getenv("FRIGATE_STORAGE_ENDPOINT", "")) or None,
        access_key=str(cfg.get("access_key") or os.getenv("FRIGATE_STORAGE_ACCESS_KEY", "")) or None,
        secret_key=str(cfg.get("secret_key") or os.getenv("FRIGATE_STORAGE_SECRET_KEY", "")) or None,
        prefix=str(cfg.get("prefix") or os.getenv("FRIGATE_STORAGE_PREFIX", "frigate")),
        local_fallback=local,
    )


def encode_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")
