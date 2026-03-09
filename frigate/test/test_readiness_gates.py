import unittest

from frigate.headless.readiness import evaluate_readiness


class TestReadinessGates(unittest.TestCase):
    def _evaluate(self, **kwargs):
        defaults = {
            "stats": {
                "cameras": {
                    "front": {
                        "process_fps": 8.0,
                        "skipped_fps": 1.0,
                        "detection_enabled": True,
                        "pid": 1001,
                        "ffmpeg_pid": 1002,
                    }
                }
            },
            "db_connected": True,
            "sse_health": {"subscribers": 1, "max_fill_ratio": 0.1},
            "canary_status": {"status": "idle"},
            "started_at": 0.0,
            "warmup_sec": 0,
            "min_process_fps": 0.1,
            "max_skipped_process_ratio": 2.0,
            "max_sse_fill_ratio": 0.95,
        }
        defaults.update(kwargs)
        return evaluate_readiness(**defaults)

    def test_ready_when_all_checks_pass(self):
        result = self._evaluate()
        self.assertTrue(result["ready"])
        self.assertEqual(result["mode"], "normal")
        self.assertTrue(result["write_critical_allowed"])

    def test_not_ready_when_db_disconnected(self):
        result = self._evaluate(db_connected=False)
        self.assertFalse(result["ready"])
        self.assertEqual(result["mode"], "not_ready")
        self.assertIn("database_disconnected", result["reasons"])

    def test_not_ready_when_camera_processes_missing(self):
        result = self._evaluate(
            stats={
                "cameras": {
                    "front": {
                        "process_fps": 5.0,
                        "skipped_fps": 0.5,
                        "detection_enabled": True,
                        "pid": None,
                        "ffmpeg_pid": None,
                    }
                }
            }
        )
        self.assertFalse(result["ready"])
        self.assertIn("missing_camera_processes", result["reasons"])

    def test_degraded_read_only_when_high_skipped_ratio(self):
        result = self._evaluate(
            stats={
                "cameras": {
                    "front": {
                        "process_fps": 1.0,
                        "skipped_fps": 4.0,
                        "detection_enabled": True,
                        "pid": 1,
                        "ffmpeg_pid": 2,
                    }
                }
            }
        )
        self.assertTrue(result["ready"])
        self.assertEqual(result["mode"], "degraded_read_only")
        self.assertFalse(result["write_critical_allowed"])
        self.assertIn("high_skipped_process_ratio", result["warnings"])

    def test_not_ready_when_sse_backpressure_is_critical(self):
        result = self._evaluate(sse_health={"subscribers": 2, "max_fill_ratio": 0.98})
        self.assertFalse(result["ready"])
        self.assertIn("sse_backpressure_critical", result["reasons"])


if __name__ == "__main__":
    unittest.main()
