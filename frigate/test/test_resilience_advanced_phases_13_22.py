import os
import tempfile
import unittest

from frigate.headless.backup_restore import BackupRestoreManager
from frigate.headless.contracts import validate_contract_compatibility, with_contract_metadata
from frigate.headless.disaster_recovery import DisasterRecoveryPlan
from frigate.headless.idempotency import IdempotencyStore
from frigate.headless.load_chaos_validation import LoadChaosValidator
from frigate.headless.migrations import MigrationManager
from frigate.headless.secrets_rotation import SecretRotationManager
from frigate.headless.supply_chain import SupplyChainHardening
from frigate.headless.tenant_isolation import TenantQuotaManager


class TestResilienceAdvanced1322(unittest.TestCase):
    def test_backup_restore_cycle(self):
        with tempfile.TemporaryDirectory() as td:
            source = os.path.join(td, "source.txt")
            with open(source, "w", encoding="utf-8") as f:
                f.write("hello")
            manager = BackupRestoreManager(base_dir=os.path.join(td, "backups"))
            manifest = manager.create_backup(
                name="runtime", sources={"runtime_state": source}, mode="full"
            )
            self.assertTrue(manifest["backup_id"])
            target = os.path.join(td, "restored.txt")
            restored = manager.restore_backup(
                manifest["backup_id"], {"runtime_state": target}
            )
            self.assertIn("runtime_state", restored["restored"])

    def test_secret_rotation_and_revoke(self):
        m = SecretRotationManager()
        first = m.rotate("jwt", "abc123xyz")
        self.assertIn("fingerprint", first)
        m.rotate("jwt", "new-secret-001")
        snap = m.snapshot()
        self.assertIn("jwt", snap["active"])
        m.revoke_previous("jwt")
        snap2 = m.snapshot()
        self.assertNotIn("jwt", snap2["previous"])

    def test_contract_validation(self):
        ok, _ = validate_contract_compatibility("1.0")
        self.assertTrue(ok)
        bad, _ = validate_contract_compatibility("99.0")
        self.assertFalse(bad)
        payload = with_contract_metadata({"x": 1})
        self.assertIn("contract", payload)

    def test_migrations_and_idempotency(self):
        migrations = MigrationManager()
        applied = migrations.apply(2, backup_id="bkp-1")
        self.assertEqual(applied["to"], 2)
        rolled = migrations.rollback(1)
        self.assertEqual(rolled["to"], 1)

        idem = IdempotencyStore(ttl_sec=120)
        dup, _ = idem.record_or_get("tenant-a", "key-1", {"a": 1})
        self.assertFalse(dup)
        dup2, _ = idem.record_or_get("tenant-a", "key-1", {"a": 1})
        self.assertTrue(dup2)

    def test_dr_quotas_supply_chain_and_load_gate(self):
        dr = DisasterRecoveryPlan()
        ex = dr.record_exercise("single_node_failure", 60, 120, True)
        self.assertTrue(ex["success"])

        quotas = TenantQuotaManager()
        quotas.set_quota("tenant-a", {"events_per_min": 2})
        ok, _ = quotas.consume("tenant-a", "events_per_min", 1)
        self.assertTrue(ok)
        ok2, _ = quotas.consume("tenant-a", "events_per_min", 2)
        self.assertFalse(ok2)

        sc = SupplyChainHardening()
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "a.py"), "w", encoding="utf-8") as f:
                f.write("print(1)")
            sbom = sc.generate_sbom(td)
            self.assertGreaterEqual(sbom["file_count"], 1)
        scan = sc.record_scan([{"id": "CVE-1", "severity": "critical"}])
        self.assertTrue(scan["release_blocked"])

        validator = LoadChaosValidator()
        validator.record(
            profile="small", latency_ms=100.0, event_loss_pct=0.1, backlog=10, recovery_sec=5
        )
        summary = validator.summary()
        self.assertTrue(summary["gate_passed"])


if __name__ == "__main__":
    unittest.main()
