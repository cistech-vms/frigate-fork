import unittest

from frigate.headless.closed_loop import init_closed_loop_state, run_closed_loop_iteration


class FakeStore:
    def __init__(self):
        self._status = {"status": "idle"}
        self.started = False

    def evaluate_canary(self, stats, now_ts):
        return self._status

    def start_canary(self, patch, policy, stats, now_ts):
        self.started = True
        return {}, patch, {"status": "running"}


class TestClosedLoop(unittest.TestCase):
    def test_disabled_loop(self):
        state = init_closed_loop_state()
        state["enabled"] = False
        store = FakeStore()
        decision = run_closed_loop_iteration(
            state,
            store,
            stats={"cameras": {}},
            effective_config={"cameras": {}},
            tenant_id="tenant-a",
            now_ts=1000.0,
        )
        self.assertEqual(decision["status"], "disabled")

    def test_starts_canary_for_low_risk_candidate(self):
        state = init_closed_loop_state()
        state["observation_interval_sec"] = 0
        store = FakeStore()
        stats = {
            "cameras": {
                "front": {
                    "skipped_fps": 2.5,
                    "adaptive_overload": 1,
                    "routing_quota_drops": 2,
                }
            }
        }
        effective = {
            "cameras": {
                "front": {
                    "objects": {"filters": {"person": {"threshold": 0.7}}},
                    "notifications": {"cooldown": 0},
                    "detect": {"roi_scheduling": {"enabled": False}},
                }
            }
        }
        decision = run_closed_loop_iteration(
            state, store, stats, effective, "tenant-a", now_ts=1000.0
        )
        self.assertEqual(decision["status"], "started")
        self.assertTrue(store.started)

    def test_freeze_on_major_incident(self):
        state = init_closed_loop_state()
        state["observation_interval_sec"] = 0
        store = FakeStore()
        stats = {
            "cameras": {
                "cam1": {"adaptive_overload": 1, "routing_quota_drops": 0, "skipped_fps": 1.0},
                "cam2": {"adaptive_overload": 1, "routing_quota_drops": 0, "skipped_fps": 1.0},
                "cam3": {"adaptive_overload": 0, "routing_quota_drops": 0, "skipped_fps": 0.1},
            }
        }
        decision = run_closed_loop_iteration(
            state,
            store,
            stats,
            {"cameras": {}},
            "tenant-a",
            now_ts=1000.0,
        )
        self.assertEqual(decision["status"], "incident_freeze")
        self.assertGreater(state["freeze_until_ts"], 1000.0)


if __name__ == "__main__":
    unittest.main()
