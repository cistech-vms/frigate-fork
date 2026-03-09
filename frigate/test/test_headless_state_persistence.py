import os
import tempfile
import unittest

from frigate.headless.state_persistence import HeadlessStateStore


class TestHeadlessStatePersistence(unittest.TestCase):
    def test_load_default_when_file_does_not_exist(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            store = HeadlessStateStore(path=path)
            state = store.load()
            self.assertEqual(state["runtime_overlays"], {})
            self.assertEqual(state["triggers"], {})
            self.assertEqual(state["regions"], {})

    def test_put_runtime_overlay_and_choose_by_tenant(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            store = HeadlessStateStore(path=path)
            store.put_runtime_overlay("tenant-a", {"mqtt": {"enabled": False}})
            store.put_runtime_overlay("default", {"record": {"enabled": False}})

            tenant, overlay = store.choose_runtime_overlay("tenant-a")
            self.assertEqual(tenant, "tenant-a")
            self.assertEqual(overlay["mqtt"]["enabled"], False)

            tenant, overlay = store.choose_runtime_overlay(None)
            self.assertEqual(tenant, "default")
            self.assertEqual(overlay["record"]["enabled"], False)

    def test_put_triggers_and_regions(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            store = HeadlessStateStore(path=path)

            triggers = {"t1": {"id": "t1", "tenant_id": "tenant-a"}}
            regions = {"tenant-a:cam:region-1": {"id": "region-1", "camera_id": "cam"}}
            store.put_triggers(triggers)
            store.put_regions(regions)

            state = store.load()
            self.assertEqual(state["triggers"], triggers)
            self.assertEqual(state["regions"], regions)

    def test_load_invalid_json_returns_default_state(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{invalid")
            store = HeadlessStateStore(path=path)
            state = store.load()
            self.assertEqual(state["runtime_overlays"], {})
            self.assertEqual(state["triggers"], {})
            self.assertEqual(state["regions"], {})


if __name__ == "__main__":
    unittest.main()
