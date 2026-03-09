import unittest

from frigate.headless.optimization_engine import OptimizationEngine


class TestOptimizationPrecisionSpeed(unittest.TestCase):
    def test_baseline_and_targets(self):
        e = OptimizationEngine()
        baseline = e.collect_baseline("edge_basic", {"fps": 5, "resolution": "640x360"})
        self.assertEqual(baseline["tier"], "edge_basic")
        targets = e.set_targets({"inference_latency_p95_ms": 180.0})
        self.assertEqual(targets["inference_latency_p95_ms"], 180.0)

    def test_tenant_configs(self):
        e = OptimizationEngine()
        ingest = e.configure_ingest_decode("tenant-a", {"detect_fps": 4})
        inference = e.configure_inference("tenant-a", {"min_confidence": 0.55})
        tracking = e.configure_tracking_regions("tenant-a", {"mask_enabled": True})
        rules = e.configure_event_rules("tenant-a", {"cooldown_sec": 20})
        self.assertEqual(ingest["detect_fps"], 4)
        self.assertEqual(inference["min_confidence"], 0.55)
        self.assertTrue(tracking["mask_enabled"])
        self.assertEqual(rules["cooldown_sec"], 20)

    def test_queue_backpressure_and_processing(self):
        e = OptimizationEngine()
        last = None
        for _ in range(4100):
            last = e.enqueue("best_effort", 1)
        self.assertIsNotNone(last)
        self.assertFalse(last["accepted"])
        processed = e.process_queue(300)
        self.assertGreater(processed["processed"], 0)

    def test_benchmark_gate_and_weekly_report(self):
        e = OptimizationEngine()
        e.set_targets(
            {
                "inference_latency_p95_ms": 250.0,
                "event_delivery_latency_p95_ms": 900.0,
                "drop_rate_max_pct": 2.0,
                "queue_depth_max": 2000.0,
            }
        )
        e.record_benchmark(
            cameras=25,
            inference_p95_ms=120.0,
            event_delivery_p95_ms=300.0,
            drop_rate_pct=0.2,
            queue_depth=120,
        )
        gate = e.benchmark_gate()
        self.assertTrue(gate["passed"])
        report = e.weekly_report()
        self.assertIn("avg_inference_p95_ms", report)


if __name__ == "__main__":
    unittest.main()
