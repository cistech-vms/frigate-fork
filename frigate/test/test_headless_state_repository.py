import os
import tempfile
import unittest

from frigate.headless.control_plane_state import (
    DesiredTenantState,
    OperationalTenantState,
    apply_runtime_patch_to_desired_state,
)
from frigate.headless.state_persistence import HeadlessStateStore
from frigate.headless.state_repository import HeadlessStateRepositoryAdapter


class TestHeadlessStateRepository(unittest.TestCase):
    def test_repository_round_trip_per_tenant(self):
        with tempfile.TemporaryDirectory() as td:
            store = HeadlessStateStore(path=os.path.join(td, 'state.json'))
            repository = HeadlessStateRepositoryAdapter(store)

            desired = DesiredTenantState.from_dict(
                'tenant-a',
                {
                    'tenant_id': 'tenant-a',
                    'go2rtc_streams': {'front': 'rtsp://front'},
                    'cameras': {
                        'front': {
                            'camera_id': 'front',
                            'stream_name': 'front',
                            'stream_url': 'rtsp://front',
                            'ffmpeg_path': 'rtsp://front',
                            'roles': ['record', 'detect'],
                            'origin': 'installer_connect',
                        }
                    },
                },
            )
            repository.save_desired_state(desired)

            restored = repository.load_desired_state('tenant-a')
            self.assertEqual(restored.tenant_id, 'tenant-a')
            self.assertEqual(restored.go2rtc_streams['front'], 'rtsp://front')
            self.assertEqual(restored.cameras['front'].stream_url, 'rtsp://front')

    def test_repository_round_trip_operational_state(self):
        with tempfile.TemporaryDirectory() as td:
            store = HeadlessStateStore(path=os.path.join(td, 'state.json'))
            repository = HeadlessStateRepositoryAdapter(store)

            operational = OperationalTenantState.from_dict(
                'tenant-a',
                {
                    'tenant_id': 'tenant-a',
                    'cameras': {
                        'front': {
                            'camera_id': 'front',
                            'status': 'healthy',
                            'process_fps': 7.5,
                            'last_error': '',
                        }
                    },
                },
            )
            repository.save_operational_state(operational)

            restored = repository.load_operational_state('tenant-a')
            self.assertEqual(restored.tenant_id, 'tenant-a')
            self.assertEqual(restored.cameras['front'].status, 'healthy')
            self.assertEqual(restored.cameras['front'].process_fps, 7.5)

    def test_apply_runtime_patch_to_desired_state_projects_camera_transport(self):
        state = DesiredTenantState(tenant_id='tenant-a')
        patch = {
            'go2rtc': {
                'streams': {
                    'front': 'rtsp://10.0.0.10:554/substream',
                }
            },
            'cameras': {
                'front': {
                    'enabled': True,
                    'audio': {'enabled': False},
                    'detect': {'enabled': True},
                    'record': {'enabled': True},
                    'ffmpeg': {
                        'hwaccel_args': 'preset-nvidia',
                        'inputs': [
                            {
                                'path': 'rtsp://10.0.0.10:554/substream',
                                'roles': ['record', 'detect'],
                                'input_args': 'preset-rtsp-generic',
                            }
                        ],
                    },
                    'live': {
                        'streams': {
                            'front': 'front',
                        }
                    },
                }
            },
        }

        updated = apply_runtime_patch_to_desired_state(
            state, patch, origin='installer_connect'
        )

        self.assertEqual(updated.go2rtc_streams['front'], 'rtsp://10.0.0.10:554/substream')
        self.assertEqual(updated.cameras['front'].stream_name, 'front')
        self.assertEqual(updated.cameras['front'].stream_url, 'rtsp://10.0.0.10:554/substream')
        self.assertEqual(updated.cameras['front'].hwaccel_args, 'preset-nvidia')
        self.assertEqual(updated.cameras['front'].origin, 'installer_connect')


if __name__ == '__main__':
    unittest.main()
