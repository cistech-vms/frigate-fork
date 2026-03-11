import unittest

from frigate.headless.production_readiness import build_production_readiness_report


class TestProductionReadiness(unittest.TestCase):
    def _base_context(self):
        return {
            "env": {
                "FRIGATE_DB_DRIVER": "sqlite",
                "FRIGATE_CI_QUALITY_GATES_ENABLED": "true",
                "FRIGATE_API_HMAC_KEYS_JSON": '{"key1":{"secret":"abc123","role":"admin"}}',
            },
            "settings": {"enabled": True, "auth_mode": "hmac"},
            "readiness": {"ready": True, "mode": "normal"},
            "release_gate": {"passed": True},
            "migrations": {"schema_version": 2, "history": [{"status": "applied"}]},
            "secrets": {"history": [{"name": "api_key"}]},
            "delivery": {
                "pending_total": 10,
                "channels": {"sse": {"success": 10, "failed": 0}},
                "dead_letters": [],
            },
            "storage_sync": {"throughput": 50, "failures": 0},
            "dr": {"exercises": [{"success": True}]},
            "backups": [{"backup_id": "runtime-1"}],
            "optimization_gate": {"passed": True},
            "optimization": {"playbook": {"weekly_reports": [{"status": "ok"}]}},
            "runbooks": {
                "storage_offline": {},
                "queue_accumulation": {},
                "degraded_node": {},
            },
            "governance": {
                "owner": "platform-team",
                "technical_committee": ["eng-1"],
                "audit_entries": [{"action": "promote"}],
            },
            "load_chaos_summary": {"gate_passed": True},
            "scaling_state": {"rollout": {"history": [{"status": "promoted"}]}},
            "rate_limiter": {"configured": True},
            "redis_enabled": True,
            "contract_compatibility_checked": True,
            "oncall_drill_completed": True,
            "supply_chain": {"release_blocked": False},
        }

    def test_report_is_production_ready_when_all_phases_pass(self):
        report = build_production_readiness_report(self._base_context())
        self.assertEqual(report["summary"]["total_phases"], 14)
        self.assertEqual(report["summary"]["passed"], 14)
        self.assertTrue(report["summary"]["production_ready"])
        self.assertEqual(report["pending_phase_ids"], [])

    def test_report_marks_blockers_for_quality_and_security(self):
        context = self._base_context()
        context["env"]["FRIGATE_CI_QUALITY_GATES_ENABLED"] = "false"
        context["env"].pop("FRIGATE_API_HMAC_KEYS_JSON", None)
        context["secrets"]["history"] = []

        report = build_production_readiness_report(context)

        self.assertFalse(report["summary"]["production_ready"])
        self.assertIn("02", report["pending_phase_ids"])
        self.assertIn("03", report["pending_phase_ids"])

        phase_02 = [x for x in report["phases"] if x["phase_id"] == "02"][0]
        phase_03 = [x for x in report["phases"] if x["phase_id"] == "03"][0]

        self.assertIn("ci_quality_gates_disabled", phase_02["blockers"])
        self.assertIn("missing_hmac_keys", phase_03["blockers"])
        self.assertIn("secrets_rotation_not_exercised", phase_03["blockers"])

    def test_report_marks_distributed_state_phase_when_redis_disabled(self):
        context = self._base_context()
        context["redis_enabled"] = False

        report = build_production_readiness_report(context)
        phase_05 = [x for x in report["phases"] if x["phase_id"] == "05"][0]

        self.assertEqual(phase_05["status"], "in_progress")
        self.assertIn("redis_distributed_state_disabled", phase_05["blockers"])

    def test_report_blocks_go_live_when_cms_license_invalid(self):
        context = self._base_context()
        context["cms_status"] = {
            "enabled": True,
            "connected": False,
            "license": {"status": "invalid"},
        }

        report = build_production_readiness_report(context)
        phase_12 = [x for x in report["phases"] if x["phase_id"] == "12"][0]

        self.assertFalse(report["summary"]["production_ready"])
        self.assertIn("cms_disconnected", phase_12["blockers"])
        self.assertIn("cms_license_not_valid", phase_12["blockers"])


if __name__ == "__main__":
    unittest.main()
