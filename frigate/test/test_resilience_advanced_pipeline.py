import os
import tempfile
import unittest
from types import SimpleNamespace

from frigate.headless.db_adapter import SqliteAdapter
from frigate.headless.object_storage import LocalObjectStorageAdapter
from frigate.headless.observability import (
    build_observability_snapshot,
    build_performance_diagnostics,
    evaluate_release_gate,
)
from frigate.headless.self_healing import (
    init_self_healing_state,
    register_chaos_event,
    register_recovery,
    should_recover,
)
from frigate.headless.state_persistence import HeadlessStateStore
from frigate.headless.storage_sync import StorageSyncManager


class TestResilienceAdvancedPipeline(unittest.TestCase):
    def test_db_adapter_audit_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            db = SqliteAdapter(path=os.path.join(td, "audit.db"))
            db.append_audit("security", {"event": "rate_limit_rejected", "ts": 1})
            items = db.list_audit("security", limit=10)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["event"], "rate_limit_rejected")

    def test_storage_sync_retries_and_success(self):
        with tempfile.TemporaryDirectory() as td:
            store = HeadlessStateStore(path=os.path.join(td, "state.json"))
            adapter = LocalObjectStorageAdapter(base_dir=os.path.join(td, "obj"))
            manager = StorageSyncManager(state_store=store, object_storage=adapter)
            manager.enqueue_replication("tenant-a", "events/a.json", {"ok": True})
            manager.process_due()
            status = manager.status()
            self.assertGreaterEqual(status["throughput"], 1)
            self.assertEqual(status["backlog"], 0)

    def test_self_healing_state(self):
        state = init_self_healing_state()
        register_chaos_event(state, "simulate_backpressure")
        self.assertTrue(should_recover(state, now_ts=9999.0))
        register_recovery(state, "reconcile_workers", "manual_test")
        self.assertIn("recoveries", state)

    def test_observability_and_release_gate(self):
        snapshot = build_observability_snapshot(
            readiness={"ready": True, "mode": "normal"},
            delivery_status={"pending_total": 10, "channels": {"webhook": {"failed": 0}}},
            rate_limit_audit=[],
            storage_sync={"throughput": 5, "failures": 0},
        )
        gate = evaluate_release_gate(snapshot)
        self.assertTrue(gate["passed"])

    def test_performance_diagnostics_identifies_camera_and_host_pressure(self):
        frigate_config = SimpleNamespace(
            cameras={
                "front": SimpleNamespace(
                    detect=SimpleNamespace(width=1920, height=1080, fps=10),
                    audio=SimpleNamespace(enabled=True),
                    record=SimpleNamespace(enabled=True),
                    review=SimpleNamespace(enabled=True),
                    snapshots=SimpleNamespace(enabled=True),
                    semantic_search=SimpleNamespace(enabled=False),
                    face_recognition=SimpleNamespace(enabled=False),
                    lpr=SimpleNamespace(enabled=False),
                    ffmpeg=SimpleNamespace(
                        inputs=[SimpleNamespace(roles=["detect", "record"])]
                    ),
                )
            }
        )
        stats = {
            "camera_fps": 12.0,
            "process_fps": 4.0,
            "skipped_fps": 3.0,
            "detection_fps": 4.0,
            "cameras": {
                "front": {
                    "camera_fps": 12.0,
                    "process_fps": 4.0,
                    "skipped_fps": 3.0,
                    "detection_fps": 4.0,
                    "adaptive_inference_latency_ms": 180.0,
                    "pid": 200,
                    "ffmpeg_pid": 100,
                }
            },
            "cpu_usages": {
                "100": {"cpu": 92.0, "mem": 12.0, "cmdline": "ffmpeg front"},
                "200": {"cpu": 88.0, "mem": 10.0, "cmdline": "detect front"},
            },
            "detectors": {"cpu": {"inference_speed": 185.0, "pid": 200}},
            "service": {
                "storage": {
                    "/media/frigate/recordings": {"total": 100.0, "free": 8.0},
                    "/tmp/cache": {"total": 10.0, "free": 0.8},
                }
            },
        }
        stats_history = [stats]
        hardware_profile = {
            "decode_acceleration": "software",
            "recommendation": {
                "tier": "edge_basic",
                "profiles": {"720p_5fps": 1, "1080p_5fps": 1, "1080p_10fps": 1},
                "notes": [],
            },
        }

        report = build_performance_diagnostics(
            stats=stats,
            stats_history=stats_history,
            hardware_profile=hardware_profile,
            frigate_config=frigate_config,
        )

        bottlenecks = {item["kind"] for item in report["cameras"]["front"]["bottlenecks"]}
        host_issues = {item["kind"] for item in report["issues"]}

        self.assertIn("decode_pressure", bottlenecks)
        self.assertIn("inference_pressure", bottlenecks)
        self.assertIn("stream_configuration", bottlenecks)
        self.assertIn("feature_pressure", bottlenecks)
        self.assertIn("camera_capacity_exceeded", host_issues)
        self.assertIn("storage_pressure", host_issues)
        self.assertIn("decode_without_hwaccel", host_issues)
        self.assertGreater(report["host"]["capacity_utilization"], 1.0)
        self.assertTrue(report["recommendations"])


if __name__ == "__main__":
    unittest.main()
