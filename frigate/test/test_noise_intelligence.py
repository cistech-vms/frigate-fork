import unittest

from frigate.headless.noise_intelligence import generate_noise_suggestions


class TestNoiseIntelligence(unittest.TestCase):
    def test_generate_suggestions_for_overloaded_camera(self):
        stats = {
            "cameras": {
                "front": {
                    "skipped_fps": 2.5,
                    "adaptive_overload": 1,
                    "routing_quota_drops": 3,
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
        items = generate_noise_suggestions(stats, effective, "tenant-a")
        types = {item["type"] for item in items}
        self.assertIn("threshold", types)
        self.assertIn("cooldown", types)
        self.assertIn("roi", types)
        self.assertIn("mask", types)

    def test_generate_no_suggestions_for_healthy_camera(self):
        stats = {
            "cameras": {
                "front": {
                    "skipped_fps": 0.1,
                    "adaptive_overload": 0,
                    "routing_quota_drops": 0,
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
        items = generate_noise_suggestions(stats, effective, "tenant-a")
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
