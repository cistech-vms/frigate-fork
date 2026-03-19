import unittest

from frigate.headless.installer import (
    build_camera_connection_patch,
    build_hardware_profile,
    discover_camera_candidates,
    expand_scan_targets,
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

    def test_build_camera_connection_patch_generates_go2rtc_and_cameras(self):
        patch = build_camera_connection_patch(
            selected_candidates=[
                {
                    "suggested_camera_name": "nvr_192_168_1_20_ch01",
                    "rtsp_url": "rtsp://admin:secret@192.168.1.20:554/Streaming/Channels/101",
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
            ["record", "detect"],
        )


if __name__ == "__main__":
    unittest.main()
