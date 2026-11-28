"""Check that the recognition comparison rejects text and confidence changes."""
import json
import sys
import tempfile
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'amd_experiment'))
import benchmark_recognition_batches as probe
from benchmark_recognition_batches import compare


class RecognitionParityTests(unittest.TestCase):
    def test_detects_order_text_confidence_and_length_changes(self) -> None:
        expected = [('door', .9), ('門', .8)]
        self.assertTrue(compare(expected, expected)['equal'])
        self.assertFalse(compare(expected, expected[::-1])['equal'])
        self.assertFalse(compare(expected, [('door', .9), ('門', .81)])['equal'])
        self.assertFalse(compare(expected, [('door', .9)])['equal'])

    def test_replays_crops_without_reordering(self) -> None:
        class Recognizer:
            batch_sampler = SimpleNamespace(batch_size=6)

            def __call__(self, crops: list[str], **_options: object) -> object:
                return iter([{'rec_text': crop, 'rec_score': .9} for crop in crops])

        rec = Recognizer()
        inner = SimpleNamespace(text_rec_model=rec)
        pipeline = SimpleNamespace(text_rec_model=rec, _pipeline=inner, predict=object())

        def predict(_images: object, _predict: object, _batch: int) -> object:
            list(inner.text_rec_model(['a', 'b']))
            list(inner.text_rec_model(['c']))
            return iter([])

        @contextmanager
        def sessions(*_args: object) -> Iterator[list[tuple[str, SimpleNamespace]]]:
            yield [('det', SimpleNamespace(end_profiling=lambda: 'det')), ('rec', SimpleNamespace(end_profiling=lambda: 'rec'))]

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'input').mkdir()
            (root / 'input' / 'a.jpg').write_bytes(b'test')
            arguments = ['probe', str(root / 'input'), str(root), str(root / 'output'), '--repeat', '1']
            with (patch.object(sys, 'argv', arguments), patch.object(probe, 'engine_settings', return_value=('DmlExecutionProvider', {})),
                  patch.object(probe, 'verified_model_directory', return_value=root), patch.object(probe, 'trace_sessions', sessions),
                  patch.object(probe, 'ocr_pipeline', return_value=pipeline), patch.object(probe, 'predict_video_images', predict),
                  patch.object(probe, 'summarize_profile', return_value={'counts': {'DmlExecutionProvider': 1}})):
                probe.main()
            report = json.loads((root / 'output' / 'recognition-benchmark.json').read_text(encoding='utf8'))
            self.assertEqual(report['per_image_call_sizes'], [2, 1])
            self.assertEqual([run['batch_size'] for run in report['runs']], [6, 1, 2, 4, 6, 8])
            self.assertTrue(all(run['parity']['equal'] for run in report['runs']))
