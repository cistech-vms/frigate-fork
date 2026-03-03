import os
import unittest
from types import SimpleNamespace

from frigate.headless.runtime_config import (
    CanaryPolicy,
    RuntimeConfigStore,
    assess_canary_health,
    load_env_overlay,
    requires_restart,
    snapshot_camera_metrics,
)


class TestHeadlessRuntimeConfig(unittest.TestCase):
    def setUp(self):
        self.original_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_load_env_overlay_from_cfg_prefix(self):
        os.environ["FRIGATE_CFG__cameras__front__enabled"] = "true"
        os.environ["FRIGATE_CFG__mqtt__enabled"] = "false"

        overlay = load_env_overlay()
        self.assertEqual(overlay["cameras"]["front"]["enabled"], True)
        self.assertEqual(overlay["mqtt"]["enabled"], False)

    def test_load_env_overlay_json_merge(self):
        os.environ["FRIGATE_CONFIG_JSON"] = '{"record": {"enabled": false}}'
        overlay = load_env_overlay()
        self.assertEqual(overlay["record"]["enabled"], False)

    def test_requires_restart(self):
        self.assertTrue(requires_restart(["cameras"]))
        self.assertFalse(requires_restart(["camera_groups"]))

    def test_snapshot_camera_metrics(self):
        stats = {
            "cameras": {
                "front": {
                    "process_fps": 8.0,
                    "skipped_fps": 1.0,
                    "adaptive_inference_latency_ms": 50.0,
                }
            }
        }
        snap = snapshot_camera_metrics(stats, ["front"])
        self.assertEqual(snap["front"]["process_fps"], 8.0)
        self.assertEqual(snap["front"]["skipped_fps"], 1.0)

    def test_assess_canary_health_degradation(self):
        baseline = {
            "front": {
                "process_fps": 10.0,
                "skipped_fps": 1.0,
                "adaptive_inference_latency_ms": 40.0,
            }
        }
        current = {
            "front": {
                "process_fps": 5.0,
                "skipped_fps": 5.0,
                "adaptive_inference_latency_ms": 70.0,
            }
        }
        policy = CanaryPolicy(
            cameras=["front"],
            duration_sec=120,
            max_skipped_fps_increase=2.0,
            min_process_fps_ratio=0.7,
            max_inference_latency_increase_pct=35.0,
        )
        reasons = assess_canary_health(baseline, current, policy)
        self.assertTrue(len(reasons) >= 2)

    def test_runtime_store_canary_rollback(self):
        base = {"mqtt": {"enabled": True}, "cameras": {"front": {"enabled": True}}}
        base_config = SimpleNamespace(model_dump=lambda **kwargs: base)
        store = RuntimeConfigStore(base_config=base_config, env_overlay={})
        # stub validation so test does not depend on full FrigateConfig parsing
        store.validate_candidate = lambda runtime_patch: runtime_patch  # type: ignore[assignment]

        stats_baseline = {
            "cameras": {
                "front": {
                    "process_fps": 10.0,
                    "skipped_fps": 1.0,
                    "adaptive_inference_latency_ms": 40.0,
                }
            }
        }

        policy = CanaryPolicy(cameras=["front"], duration_sec=120)
        _, _, canary = store.start_canary(
            {"cameras": {"front": {"enabled": False}}},
            policy,
            stats_baseline,
            now_ts=1000.0,
        )
        self.assertEqual(canary["status"], "running")

        stats_degraded = {
            "cameras": {
                "front": {
                    "process_fps": 4.0,
                    "skipped_fps": 5.0,
                    "adaptive_inference_latency_ms": 80.0,
                }
            }
        }
        evaluated = store.evaluate_canary(stats_degraded, now_ts=1020.0)
        self.assertEqual(evaluated["status"], "rolled_back")


if __name__ == "__main__":
    unittest.main()
