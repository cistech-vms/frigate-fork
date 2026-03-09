import unittest

from frigate.headless.horizontal_scaling import HorizontalScalingManager


class TestHorizontalScaling(unittest.TestCase):
    def test_apply_plan_and_reconcile(self):
        m = HorizontalScalingManager(node_id="node-a")
        item = m.apply_plan(
            tenant_id="tenant-a",
            config_version=3,
            assigned_cameras=["cam1", "cam2"],
            request_id="r1",
        )
        self.assertEqual(item["desired_version"], 3)
        rec = m.reconcile("tenant-a")
        self.assertEqual(rec["drift"], 0)
        self.assertEqual(len(rec["assigned_cameras"]), 2)

    def test_rebalance_and_shards(self):
        m = HorizontalScalingManager(node_id="node-a")
        m.apply_plan(
            tenant_id="tenant-a",
            config_version=1,
            assigned_cameras=["c1", "c2", "c3"],
        )
        result = m.rebalance("tenant-a", max_cameras_per_node=2)
        self.assertEqual(result["status"], "rebalanced")
        self.assertEqual(len(result["moved_out"]), 1)

    def test_event_pipeline_backpressure(self):
        m = HorizontalScalingManager()
        accepted = None
        for _ in range(5002):
            accepted = m.publish_event(
                tenant_id="tenant-a", priority="high", payload={"x": 1}
            )
        self.assertIsNotNone(accepted)
        self.assertFalse(accepted["accepted"])
        self.assertGreaterEqual(len(m.state["event_pipeline"]["dlq"]), 1)

    def test_slo_and_rollout(self):
        m = HorizontalScalingManager()
        m.heartbeat(
            tenant_id="tenant-a",
            fps=20.0,
            queue_depth=10,
            inference_latency_ms=90.0,
        )
        slo = m.slo_snapshot()
        self.assertIn("slo", slo)
        canary = m.start_canary("tenant-a", target_version=2, cameras=["cam1"])
        self.assertEqual(canary["status"], "running")
        finalized = m.finalize_canary("tenant-a", promote=True)
        self.assertEqual(finalized["status"], "promoted")


if __name__ == "__main__":
    unittest.main()
