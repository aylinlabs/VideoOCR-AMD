"""Compare original per-image OCR calls with an isolated cross-image batch experiment."""
import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from paddlex_runtime import engine_settings, ocr_pipeline, trace_sessions
from real_image_compare import summarize_profile
from video_backend import predict_video_images, verified_model_directory


def signature(results: list[Any]) -> list[tuple[str, float]]:
    return [(str(r['rec_text']), float(r['rec_score'])) for r in results]


def compare(expected: list[tuple[str, float]], actual: list[tuple[str, float]]) -> dict[str, Any]:
    if len(expected) != len(actual):
        return {'equal': False, 'expected_count': len(expected), 'actual_count': len(actual)}
    text_differences = sum(a[0] != b[0] for a, b in zip(expected, actual, strict=True))
    confidence_differences = sum(a[1] != b[1] for a, b in zip(expected, actual, strict=True))
    max_difference = max((abs(a[1] - b[1]) for a, b in zip(expected, actual, strict=True)), default=0.0)
    return {'equal': not text_differences and not confidence_differences,
            'text_differences': text_differences, 'confidence_differences': confidence_differences,
            'max_confidence_difference': max_difference}


def main() -> None:
    import psutil

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('images', type=Path, help='Stage 3 recognition-inputs captured by the profiler')
    parser.add_argument('models', type=Path)
    parser.add_argument('output', type=Path, help='New directory for the report')
    parser.add_argument('--adapter', type=int, default=0)
    parser.add_argument('--repeat', type=int, default=3)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error('--repeat must be positive')
    images = sorted(args.images.glob('*.jpg'))
    if not images:
        parser.error('No captured JPEG files found')
    args.output.mkdir()
    os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
    models = verified_model_directory(args.models)
    provider, settings = engine_settings('directml', args.adapter)
    settings['intra_op_num_threads'] = 1
    with trace_sessions(provider, args.output) as sessions:
        pipeline = ocr_pipeline(models / 'det', models / 'rec', settings, batch_size=4)
    recognizer = pipeline.text_rec_model
    original = pipeline._pipeline.text_rec_model
    groups: list[list[Any]] = []
    reference: list[tuple[str, float]] = []

    class Capture:
        def __call__(self, crops: list[Any], **options: Any) -> Any:
            results = list(original(crops, **options))
            groups.append(list(crops))
            reference.extend(signature(results))
            return iter(results)

    pipeline._pipeline.text_rec_model = Capture()
    for _path, _result in predict_video_images(images, pipeline.predict, 4):
        pass
    pipeline._pipeline.text_rec_model = original
    if not reference:
        raise RuntimeError('No text crops found; choose a subtitle-rich excerpt')
    evidence = {}
    for kind, session in sessions:
        evidence[kind] = summarize_profile(Path(session.end_profiling()))
        if not evidence[kind]['counts'].get(provider):
            raise RuntimeError(f'{kind}: no DirectML execution recorded')
    flattened = [crop for group in groups for crop in group]
    report: dict[str, Any] = {'image_count': len(images), 'crop_count': len(flattened),
                              'per_image_call_sizes': [len(g) for g in groups], 'provider_evidence': evidence,
                              'settings': {'image_batch': 4, 'adapter': args.adapter}, 'runs': []}
    # A warmup is deliberately omitted from reported measurements.
    list(recognizer(flattened[:min(6, len(flattened))]))
    for mode, batch_size in [('per-image', 6), *[('cross-image', n) for n in (1, 2, 4, 6, 8)]]:
        recognizer.batch_sampler.batch_size = batch_size
        for iteration in range(args.repeat):
            timestamp = datetime.now(UTC).isoformat()
            start = perf_counter()
            inputs = groups if mode == 'per-image' else [flattened]
            observed = [row for group in inputs for row in recognizer(group)]
            elapsed = perf_counter() - start
            report['runs'].append({'mode': mode, 'batch_size': batch_size, 'iteration': iteration + 1,
                                   'started_utc': timestamp,
                                   'seconds': elapsed, 'crops_per_second': len(flattened) / elapsed,
                                   'rss_bytes_after': psutil.Process().memory_info().rss,
                                   'parity': compare(reference, signature(observed))})
    report['inputs_sha256'] = hashlib.sha256(b''.join(hashlib.sha256(p.read_bytes()).digest() for p in images)).hexdigest()
    (args.output / 'recognition-benchmark.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    if not all(row['parity']['equal'] for row in report['runs']):
        raise SystemExit('Recognition output or confidence differs; inspect the report')


if __name__ == '__main__':
    main()
