import os
import tempfile
import unittest

from frigate.headless.db_adapter import SqliteAdapter
from frigate.headless.object_storage import LocalObjectStorageAdapter
from frigate.headless.observability import (
    build_observability_snapshot,
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


if __name__ == "__main__":
    unittest.main()
