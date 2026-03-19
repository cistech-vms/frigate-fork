import unittest

from frigate.headless.installer import (
    build_camera_connection_patch,
    build_hardware_profile,
    discover_camera_candidates,
    expand_scan_targets,
    parse_ws_discovery_match,
)


class TestHeadlessInstaller(unittest.TestCase):
    def test_build_hardware_profile_uses_snapshot(self):
        profile = build_hardware_profile(
            {
                "logical_cpus": 16,
                "physical_cpus": 8,
                "total_mem_bytes": 32 * 1024**3,
                "docker_limit_bytes": 24 * 1024**3,
                "disk_free_bytes": 500 * 1024**3,
                "gpu_inventory": {
                    "accelerator": "nvidia",
                    "devices": ["RTX"],
                },
            }
        )

        self.assertEqual(profile["decode_acceleration"], "nvidia")
        self.assertEqual(profile["node"]["effective_mem_bytes"], 24 * 1024**3)
        self.assertGreaterEqual(profile["recommendation"]["profiles"]["1080p_5fps"], 1)

    def test_expand_scan_targets_supports_cidr_and_range(self):
        hosts = expand_scan_targets(
            ["192.168.1.10-12", "192.168.2.0/30", "192.168.3.50"],
            max_hosts=16,
        )
        self.assertIn("192.168.1.10", hosts)
        self.assertIn("192.168.1.12", hosts)
        self.assertIn("192.168.2.1", hosts)
        self.assertIn("192.168.2.2", hosts)
        self.assertIn("192.168.3.50", hosts)

    def test_discover_camera_candidates_with_fake_probes(self):
        def fake_port_probe(address: str, timeout: float) -> bool:
            del timeout
            return address in {
                "192.168.1.20:554",
                "192.168.1.20:80",
            }

        def fake_stream_probe(url: str, ffprobe_path: str, timeout: float):
            del ffprobe_path, timeout
            if "192.168.1.20:554/Streaming/Channels/101" in url:
                return {"width": 1920, "height": 1080, "codec": "h264"}
            if "192.168.1.20:554/Streaming/Channels/201" in url:
                return {"width": 1280, "height": 720, "codec": "h264"}
            return None

        result = discover_camera_candidates(
            ffprobe_path="/usr/bin/ffprobe",
            targets=["192.168.1.20"],
            username="admin",
            password="secret",
            profiles=["hikvision"],
            max_channels=2,
            port_probe=fake_port_probe,
            stream_probe=fake_stream_probe,
        )

        self.assertEqual(result["summary"]["candidates_found"], 2)
        self.assertTrue(result["candidates"][0]["onvif_reachable"])
        self.assertEqual(result["candidates"][0]["source_type"], "nvr_channel")
        self.assertIn("recommended_config", result["candidates"][0])

    def test_parse_ws_discovery_match(self):
        payload = b"""
        <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
                    xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"
                    xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery">
          <s:Body>
            <d:ProbeMatches>
              <d:ProbeMatch>
                <a:EndpointReference>
                  <a:Address>urn:uuid:camera-1</a:Address>
                </a:EndpointReference>
                <d:Types>tds:Device</d:Types>
                <d:Scopes>onvif://www.onvif.org/name/Camera01</d:Scopes>
                <d:XAddrs>http://192.168.1.50:80/onvif/device_service</d:XAddrs>
              </d:ProbeMatch>
            </d:ProbeMatches>
          </s:Body>
        </s:Envelope>
        """
        parsed = parse_ws_discovery_match(payload, "192.168.1.50")
        self.assertEqual(parsed["host"], "192.168.1.50")
        self.assertEqual(parsed["port"], 80)
        self.assertEqual(parsed["urn"], "urn:uuid:camera-1")

    def test_discover_camera_candidates_with_fake_onvif(self):
        def fake_port_probe(address: str, timeout: float) -> bool:
            del timeout
            return address in {"192.168.1.40:80"}

        def fake_stream_probe(url: str, ffprobe_path: str, timeout: float):
            del ffprobe_path, timeout
            if "rtsp://192.168.1.40/live" in url:
                return {
                    "width": 2560,
                    "height": 1440,
                    "codec": "h265",
                    "fps": 15.0,
                    "has_audio": True,
                    "audio_codec": "aac",
                }
            return None

        def fake_onvif_discover(**kwargs):
            del kwargs
            return [
                {
                    "host": "192.168.1.40",
                    "port": 80,
                    "xaddr": "http://192.168.1.40:80/onvif/device_service",
                    "xaddrs": ["http://192.168.1.40:80/onvif/device_service"],
                    "urn": "urn:uuid:onvif-1",
                    "scopes": ["onvif://www.onvif.org/name/NVRFront"],
                    "types": "tds:Device",
                    "discovery": "ws-discovery",
                }
            ]

        def fake_onvif_device(service_url: str, username: str | None, password: str | None, timeout: float):
            del service_url, username, password, timeout
            return {
                "service_url": "http://192.168.1.40:80/onvif/device_service",
                "manufacturer": "Acme",
                "model": "NVR-Pro",
                "capabilities": {
                    "media_xaddr": "http://192.168.1.40:80/onvif/media_service",
                },
            }

        def fake_onvif_profiles(
            service_url: str,
            username: str | None,
            password: str | None,
            timeout: float,
            metadata: dict | None = None,
        ):
            del service_url, username, password, timeout, metadata
            return [
                {
                    "token": "profile1",
                    "name": "MainStream",
                    "width": 2560,
                    "height": 1440,
                    "rtsp_url": "rtsp://192.168.1.40/live",
                    "source": "media",
                }
            ]

        result = discover_camera_candidates(
            ffprobe_path="/usr/bin/ffprobe",
            targets=["192.168.1.40"],
            onvif_ports=[80],
            rtsp_ports=[],
            port_probe=fake_port_probe,
            stream_probe=fake_stream_probe,
            onvif_discover_fn=fake_onvif_discover,
            onvif_device_fn=fake_onvif_device,
            onvif_profiles_fn=fake_onvif_profiles,
        )

        self.assertEqual(result["summary"]["onvif_devices_found"], 1)
        self.assertEqual(result["summary"]["candidates_found"], 1)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["discovery_method"], "onvif")
        self.assertEqual(candidate["onvif"]["metadata"]["model"], "NVR-Pro")
        self.assertTrue(candidate["recommended_config"]["audio_enabled"])

    def test_build_camera_connection_patch_generates_go2rtc_and_cameras(self):
        patch = build_camera_connection_patch(
            selected_candidates=[
                {
                    "suggested_camera_name": "nvr_192_168_1_20_ch01",
                    "rtsp_url": "rtsp://admin:secret@192.168.1.20:554/Streaming/Channels/101",
                    "recommended_config": {
                        "detect_fps": 6,
                        "audio_enabled": True,
                        "hwaccel_args": "preset-vaapi",
                        "input_preset": "preset-rtsp-generic",
                    },
                    "onvif": {
                        "service_url": "http://192.168.1.20:80/onvif/device_service",
                    },
                },
                {
                    "suggested_camera_name": "nvr_192_168_1_20_ch02",
                    "rtsp_url": "rtsp://admin:secret@192.168.1.20:554/Streaming/Channels/201",
                },
            ],
            existing_config={"cameras": {}, "go2rtc": {"streams": {}}},
            camera_name_prefix="cam",
            detect_enabled=True,
            record_enabled=True,
        )

        self.assertEqual(len(patch["cameras"]), 2)
        self.assertEqual(len(patch["go2rtc"]["streams"]), 2)
        first_camera = next(iter(patch["cameras"].values()))
        self.assertEqual(
            first_camera["ffmpeg"]["inputs"][0]["roles"],
            ["record", "detect", "audio"],
        )
        self.assertEqual(first_camera["detect"]["fps"], 6)
        self.assertEqual(first_camera["audio"]["enabled"], True)
        self.assertEqual(first_camera["ffmpeg"]["hwaccel_args"], "preset-vaapi")
        self.assertEqual(first_camera["onvif"]["host"], "192.168.1.20")


if __name__ == "__main__":
    unittest.main()
