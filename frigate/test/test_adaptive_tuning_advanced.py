import unittest

from frigate.headless.adaptive_tuning import AdaptiveTuningManager


class TestAdaptiveTuningAdvanced(unittest.TestCase):
    def test_segmentation_baseline_and_health(self):
        m = AdaptiveTuningManager()
        m.classify_camera("front", "outdoor")
        m.classify_camera("garage", "baixa_luz")
        m.set_segment_limits("outdoor", {"max_drop_rate": 0.02})
        baseline = m.capture_baseline(
            {
                "cameras": {
                    "front": {"process_fps": 9.0, "skipped_fps": 0.5, "queue_depth": 10, "drop_rate": 0.01},
                    "garage": {"process_fps": 7.0, "skipped_fps": 1.2, "queue_depth": 22, "drop_rate": 0.02},
                }
            }
        )
        self.assertIn("outdoor", baseline)
        self.assertIn("front", m.snapshot()["health_scores"])

    def test_day_night_profile_switch(self):
        m = AdaptiveTuningManager()
        m.upsert_day_night_profile(
            "front",
            day_profile={"min_confidence": 0.55},
            night_profile={"min_confidence": 0.7},
            day_start="06:00",
            night_start="18:00",
        )
        day = m.evaluate_day_night("front", now_hhmm="12:00")
        self.assertEqual(day["active_profile"], "day")
        night = m.evaluate_day_night("front", now_hhmm="22:30")
        self.assertEqual(night["active_profile"], "night")

    def test_adaptive_rule_adjustment(self):
        m = AdaptiveTuningManager()
        m.upsert_adaptive_rule(
            camera_id="front",
            label="person",
            min_threshold=0.4,
            max_threshold=0.9,
            min_cooldown=0,
            max_cooldown=120,
            current_threshold=0.6,
            current_cooldown=10,
        )
        high_noise = m.evaluate_rule("front", "person", repeat_rate=1.8, is_critical=False)
        self.assertGreaterEqual(high_noise["current_threshold"], 0.65)
        calmer = m.evaluate_rule("front", "person", repeat_rate=0.1, is_critical=False)
        self.assertLessEqual(calmer["current_threshold"], high_noise["current_threshold"])


if __name__ == "__main__":
    unittest.main()
