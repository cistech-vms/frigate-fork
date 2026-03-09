import unittest

from frigate.headless.reliable_delivery import ReliableEventDelivery


class _FakeSseClient:
    def __init__(self) -> None:
        self.items = []

    def publish(self, topic, payload, retain=False):
        self.items.append((topic, payload, retain))


class _FakeStateStore:
    def __init__(self) -> None:
        self.state = {"event_delivery_status": {"channels": {}, "dead_letters": []}}

    def load(self):
        return self.state

    def put_event_delivery_status(self, status):
        self.state["event_delivery_status"] = status
        return self.state


class _FailingWebhookDelivery(ReliableEventDelivery):
    def _deliver_webhook(self, item):  # type: ignore[override]
        raise RuntimeError("webhook_down")


class TestReliableEventDelivery(unittest.TestCase):
    def test_emit_and_deliver_sse(self):
        sse = _FakeSseClient()
        store = _FakeStateStore()
        delivery = ReliableEventDelivery(sse_client=sse, state_store=store, webhook_url=None)
        event_id = delivery.emit("topic/a", {"ok": True})
        self.assertTrue(event_id)
        delivery.process_due()
        self.assertEqual(len(sse.items), 1)
        snapshot = delivery.snapshot()
        self.assertEqual(snapshot["pending_total"], 0)
        self.assertEqual(snapshot["channels"]["sse"]["success"], 1)

    def test_idempotency_by_event_id_topic_channel(self):
        sse = _FakeSseClient()
        store = _FakeStateStore()
        delivery = ReliableEventDelivery(sse_client=sse, state_store=store, webhook_url=None)
        event_id = "evt-1"
        delivery.emit("topic/a", {"x": 1}, event_id=event_id)
        delivery.emit("topic/a", {"x": 2}, event_id=event_id)
        snapshot = delivery.snapshot()
        self.assertEqual(snapshot["pending_total"], 1)

    def test_retry_and_dead_letter_for_webhook(self):
        sse = _FakeSseClient()
        store = _FakeStateStore()
        delivery = _FailingWebhookDelivery(
            sse_client=sse,
            state_store=store,
            webhook_url="http://localhost:9/never",
            max_attempts=2,
            backoff_base_sec=0.0,
            backoff_max_sec=0.0,
            jitter_ratio=0.0,
        )
        delivery.emit("topic/a", {"x": 1}, event_id="evt-webhook")
        delivery.process_due()
        with delivery._lock:
            for item in delivery._pending:
                item["next_attempt_ts"] = 0.0
        delivery.process_due()
        delivery.process_due()
        snapshot = delivery.snapshot()
        self.assertGreaterEqual(snapshot["channels"]["webhook"]["dead_letter"], 1)
        self.assertGreaterEqual(len(snapshot["dead_letters"]), 1)


if __name__ == "__main__":
    unittest.main()
