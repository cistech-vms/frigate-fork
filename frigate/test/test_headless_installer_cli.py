import argparse
import json
import unittest

from frigate.headless.installer_cli import (
    InstallerApiClient,
    _normalize_base_url,
    _private_networks_from_interfaces,
    _scan_payload_from_args,
    parse_candidate_selection,
)


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


class _FakeOpener:
    def __init__(self, payload):
        self.payload = payload
        self.last_request = None
        self.last_timeout = None

    def open(self, request, timeout=0):
        self.last_request = request
        self.last_timeout = timeout
        return _FakeResponse(self.payload)


class TestHeadlessInstallerCli(unittest.TestCase):
    def test_normalize_base_url_adds_scheme(self):
        self.assertEqual(
            _normalize_base_url("127.0.0.1:5001"),
            "http://127.0.0.1:5001",
        )

    def test_private_networks_from_interfaces_filters_noise(self):
        networks = _private_networks_from_interfaces(
            {
                "eth0": [
                    {"address": "192.168.10.15", "netmask": "255.255.255.0"},
                    {"address": "10.1.2.3", "netmask": "255.255.0.0"},
                ],
                "docker0": [
                    {"address": "172.17.0.1", "netmask": "255.255.0.0"},
                ],
                "lo": [
                    {"address": "127.0.0.1", "netmask": "255.0.0.0"},
                ],
            }
        )

        self.assertEqual(networks, ["192.168.10.0/24", "10.1.0.0/16"])

    def test_parse_candidate_selection_supports_ranges(self):
        candidates = [{"id": "cam-1"}, {"id": "cam-2"}, {"id": "cam-3"}, {"id": "cam-4"}]
        selected = parse_candidate_selection("1,3-4", candidates)
        self.assertEqual(selected, ["cam-1", "cam-3", "cam-4"])

    def test_scan_payload_prefers_runtime_overrides(self):
        args = argparse.Namespace(
            targets=["192.168.1.0/24"],
            username="admin",
            password="secret",
            rtsp_ports=[554],
            onvif_ports=[80],
            profiles=["hikvision"],
            max_hosts=128,
            max_channels=8,
            max_candidates=32,
            scan_timeout_sec=3.5,
        )

        payload = _scan_payload_from_args(args, username="operator", password="override")

        self.assertEqual(payload["username"], "operator")
        self.assertEqual(payload["password"], "override")
        self.assertEqual(payload["timeout_sec"], 3.5)

    def test_api_client_posts_json_to_install_endpoint(self):
        opener = _FakeOpener({"enabled": True, "cameras_configured": 0})
        client = InstallerApiClient(
            base_url="127.0.0.1:5001",
            timeout_sec=12,
            headers={"X-Test": "ok"},
            opener=opener,
        )

        payload = client.get_status()

        self.assertTrue(payload["enabled"])
        self.assertEqual(opener.last_timeout, 12)
        self.assertEqual(opener.last_request.full_url, "http://127.0.0.1:5001/install/status")
        self.assertEqual(opener.last_request.get_method(), "GET")
        self.assertEqual(opener.last_request.headers["X-test"], "ok")


if __name__ == "__main__":
    unittest.main()
