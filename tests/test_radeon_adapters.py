"""Selection and memory policy tests with simulated adapters."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'amd_experiment'))
from dxgi_adapters import (
    Adapter,
    compatible_adapters,
    default_worker_limit,
    select_adapter,
)
from video_export import export_desktop


def gpu(index: int, name: str, vendor: str, memory: int, available: int | None, dx12: bool) -> Adapter:
    gib = 1024 ** 3
    return {'index': index, 'name': name, 'vendor_id': vendor, 'device_id': '0000',
            'dedicated_bytes': memory * gib, 'available_bytes': available * gib if available is not None else None,
            'directx12': dx12}


class RadeonSelectionTests(unittest.TestCase):
    def test_multi_gpu_eligibility_and_explicit_selection(self) -> None:
        adapters = [gpu(0, 'Integrated', '1002', 0, None, True), gpu(1, 'NVIDIA', '10de', 24, 20, True),
                    gpu(2, 'RX 6800', '1002', 16, 10, True), gpu(3, 'RX 7900 XT', '1002', 20, 12, True),
                    gpu(4, 'RX 9070 XT', '1002', 16, 12, True), gpu(5, 'AMD incompatible', '1002', 32, 20, False)]
        self.assertEqual([a['index'] for a in compatible_adapters(adapters)], [0, 2, 3, 4])
        self.assertEqual(select_adapter(adapters)['index'], 3)
        self.assertEqual(select_adapter(adapters, 4)['name'], 'RX 9070 XT')
        with self.assertRaises(ValueError):
            select_adapter(adapters, 5)
        with self.assertRaises(ValueError):
            select_adapter(adapters, 99)

    def test_memory_caps_handle_unknown_capacity_and_budget(self) -> None:
        gib = 1024 ** 3
        for capacity, expected in [(0, 1), (4, 1), (8, 1), (12, 2), (16, 3), (24, 3)]:
            with self.subTest(capacity=capacity):
                self.assertEqual(default_worker_limit(capacity * gib), expected)
        self.assertEqual(default_worker_limit(16 * gib, 3 * gib), 1)
        self.assertEqual(default_worker_limit(16 * gib, 5 * gib), 2)
        self.assertEqual(default_worker_limit(16 * gib, 10 * gib), 3)

    def test_desktop_dispatches_selected_adapter_and_clamps_workers(self) -> None:
        adapters = [gpu(0, 'iGPU', '1002', 0, None, True), gpu(3, 'RX 7600', '1002', 8, 6, True)]
        with tempfile.TemporaryDirectory() as folder:
            with (patch.dict(os.environ, {'LOCALAPPDATA': folder}),
                  patch('dxgi_adapters.enumerate_adapters', return_value=adapters),
                  patch('paddlex_runtime.engine_settings') as provider,
                  patch('video_backend.verified_model_directory', return_value=Path(folder)),
                  patch('video_export.write_srt') as export):
                export_desktop('video.mp4', 'output.srt', directml_adapter=3, directml_workers=3, lang='en')
            provider.assert_called_once_with('directml', 3)
            self.assertEqual(export.call_args.args[3], 3)
            self.assertEqual(export.call_args.kwargs['worker_limit'], 1)
            self.assertEqual(export.call_args.kwargs['lang'], 'en')
