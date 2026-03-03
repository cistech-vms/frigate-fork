import unittest

from frigate.headless.governance import (
    append_audit_entry,
    build_monthly_scorecard,
    current_period,
    init_governance_state,
)


class TestGovernance(unittest.TestCase):
    def test_append_audit_entry_keeps_max_size(self):
        state = init_governance_state()
        state["max_audit_entries"] = 2
        append_audit_entry(state, {"id": 1})
        append_audit_entry(state, {"id": 2})
        append_audit_entry(state, {"id": 3})
        self.assertEqual(len(state["audit_entries"]), 2)
        self.assertEqual(state["audit_entries"][0]["id"], 2)

    def test_build_monthly_scorecard(self):
        stats = {
            "cameras": {
                "front": {"process_fps": 8.0, "skipped_fps": 1.0, "adaptive_overload": 1},
                "garage": {"process_fps": 6.0, "skipped_fps": 0.5, "adaptive_overload": 0},
            }
        }
        entries = [
            {"period": "2026-03", "origin": "automatic", "action": "apply"},
            {"period": "2026-03", "origin": "manual", "action": "apply"},
            {"period": "2026-03", "origin": "automatic", "action": "promote"},
            {"period": "2026-03", "origin": "automatic", "action": "rollback"},
            {"period": "2026-02", "origin": "automatic", "action": "apply"},
        ]
        card = build_monthly_scorecard(stats, entries, "2026-03")
        self.assertEqual(card["cameras_count"], 2)
        self.assertEqual(card["automatic_changes"], 3)
        self.assertEqual(card["manual_changes"], 1)
        self.assertEqual(card["promotions"], 1)
        self.assertEqual(card["rollbacks"], 1)

    def test_current_period_format(self):
        p = current_period(1709251200.0)
        self.assertRegex(p, r"^\d{4}-\d{2}$")


if __name__ == "__main__":
    unittest.main()
