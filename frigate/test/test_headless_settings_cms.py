import os
import unittest

from frigate.headless.settings import get_headless_settings


class TestHeadlessSettingsCms(unittest.TestCase):
    def setUp(self):
        self.original_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_cms_required_without_url_raises(self):
        os.environ["FRIGATE_CMS_REQUIRED"] = "true"
        os.environ["FRIGATE_TENANT_CODE"] = "tenant-a"
        os.environ["FRIGATE_CMS_AUTH_MODE"] = "token"
        os.environ["FRIGATE_CMS_TOKEN"] = "token"
        with self.assertRaises(ValueError):
            get_headless_settings()

    def test_cms_token_mode_valid(self):
        os.environ["FRIGATE_CMS_URL"] = "https://cms.example.com"
        os.environ["FRIGATE_TENANT_CODE"] = "tenant-a"
        os.environ["FRIGATE_CMS_AUTH_MODE"] = "token"
        os.environ["FRIGATE_CMS_TOKEN"] = "token"
        settings = get_headless_settings()
        self.assertTrue(settings.cms_enabled)
        self.assertEqual(settings.cms_auth_mode, "token")

    def test_cms_password_mode_requires_credentials(self):
        os.environ["FRIGATE_CMS_URL"] = "https://cms.example.com"
        os.environ["FRIGATE_TENANT_CODE"] = "tenant-a"
        os.environ["FRIGATE_CMS_REQUIRED"] = "true"
        os.environ["FRIGATE_CMS_AUTH_MODE"] = "password"
        with self.assertRaises(ValueError):
            get_headless_settings()


if __name__ == "__main__":
    unittest.main()
