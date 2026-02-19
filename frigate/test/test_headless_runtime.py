import os
import unittest

from frigate.headless.runtime_config import load_env_overlay, requires_restart


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


if __name__ == "__main__":
    unittest.main()
