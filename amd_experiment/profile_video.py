"""Benchmark a real desktop export. All instrumentation is confined to this process tree."""
import argparse
import json
import os
import threading
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
from functools import partial
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any
from unittest.mock import patch

import video_backend as backend
from paddlex_runtime import ocr_pipeline

_original_init = backend._VideoPass.__init__
_original_process = backend._VideoPass.process
_original_predict = backend.predict_video_images
_cost: defaultdict[str, float] = defaultdict(float)
_shapes: Counter[str] = Counter()
_rec_batches: Counter[int] = Counter()


def timed(label: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    start = perf_counter()
    try:
        return fn(*args, **kwargs)
    finally:
        _cost[label] += perf_counter() - start


def record(directory: Path, **row: Any) -> None:
    with (directory / f'{os.getpid()}.jsonl').open('a', encoding='utf8') as stream:
        print(json.dumps(row), file=stream)


def instrument(directory: Path, batch: int, threads: int) -> None:
    import cv2
    import psutil
    from paddlex.inference.common.reader.image_reader import ReadImage
    from paddlex.inference.models.text_detection.predictor import TextDetRunnerPredictor
    from paddlex.inference.models.text_recognition.predictor import (
        TextRecRunnerPredictor,
    )

    process = psutil.Process()
    if threads:
        cv2.setNumThreads(threads)

    def wrap_model(label: str, model: Any) -> None:
        for key, operation in model.pre_tfs.items():
            model.pre_tfs[key] = partial(timed, 'preprocess', operation)
        model.runner = partial(timed, label + '_runner', model.runner)
        model.post_op = partial(timed, label + '_postprocess', model.post_op)

    for cls, label in ((TextDetRunnerPredictor, 'det'), (TextRecRunnerPredictor, 'rec')):
        original = cls.process

        def process_batch(model: Any, *a: Any, _fn: Any = original, _label: str = label, **kw: Any) -> Any:
            if not getattr(model, "_videocr_timed", False):
                wrap_model(_label, model)
                model._videocr_timed = True
            if _label == "rec" and a:
                _rec_batches[len(a[0].instances)] += 1
            return _fn(model, *a, **kw)
        patch.object(cls, 'process', process_batch).start()

    read = ReadImage.__call__

    def read_images(reader: Any, *a: Any, **kw: Any) -> Any:
        if a and a[0] and isinstance(a[0][0], str):
            frames = timed('jpeg', read, reader, *a, **kw)
            _shapes.update(str(f.shape[:2]) for f in frames)
            return frames
        return read(reader, *a, **kw)
    patch.object(ReadImage, '__call__', read_images).start()

    def start(worker: Any, *a: Any) -> None:
        before = perf_counter()
        _original_init(worker, *a)
        record(directory, event='startup', start=before, end=perf_counter(), detection=worker.detection)

    def chunk(worker: Any, images: Sequence[Path]) -> backend.BatchResult:
        _cost.clear()
        _shapes.clear()
        _rec_batches.clear()
        before = perf_counter()
        result = _original_process(worker, images)
        record(directory, event='chunk', first=images[0].name, n=len(images), start=before,
               end=perf_counter(), rss=process.memory_info().rss, boxes=sum(len(rows) for _, rows in result[0]),
               shape=dict(_shapes), recognition_batches=dict(_rec_batches), costs=dict(_cost), detection=worker.detection)
        return result

    patch.object(backend._VideoPass, '__init__', start).start()
    patch.object(backend._VideoPass, 'process', chunk).start()
    patch.object(backend, 'predict_video_images', lambda images, predict, _: _original_predict(images, predict, batch)).start()
    pipeline = ocr_pipeline
    patch.object(backend, 'ocr_pipeline', lambda *a, **kw: pipeline(*a, **(kw | {'batch_size': batch}))).start()


def initialize(directory: Path, batch: int, threads: int, *config: Any) -> None:
    instrument(directory, batch, threads)
    backend._start_worker(*config)


def summarize(directory: Path) -> None:
    rows = [json.loads(line) | {'pid': path.stem} for path in directory.glob('*.jsonl')
            for line in path.read_text(encoding='utf8').splitlines()]
    total = next(row for row in rows if row['event'] == 'total')
    report: dict[str, Any] = {'total_s': total['end'] - total['start']}
    samples = [r for r in rows if r['event'] == 'resources']
    report['peak_sampled_process_tree_rss_bytes'] = max((r['rss'] for r in samples), default=None)
    report['gpu_memory_and_activity'] = 'not collected; use Windows GPU counters or a device profiler'
    batches: Counter[str] = Counter()
    for chunk in (r for r in rows if r['event'] == 'chunk' and not r['detection']):
        batches.update(chunk.get('recognition_batches', {}))
    report['recognition_batch_histogram'] = dict(batches)
    crops = sum(int(size) * count for size, count in batches.items())
    report['recognition_crops'] = crops
    boundaries = {}
    for stage in ('text_detection', 'ocr'):
        markers = {r['event']: r['t'] for r in rows
                   if r.get('stage') == stage and r['event'] in ('begin', 'end')}
        if not markers:
            continue
        boundaries[stage] = markers
        chunks = sorted((r for r in rows if r['event'] == 'chunk' and r['detection'] == (stage == 'text_detection')),
                        key=lambda r: r['first'])
        if not chunks:
            continue
        durations = [r['end'] - r['start'] for r in chunks]
        finish = {r['first']: r['end'] for r in chunks}
        receipts = [r['t'] - finish[r['first']] for r in rows if r['event'] == 'received' and r['stage'] == stage]
        elapsed = markers['end'] - markers['begin']
        n = sum(r['n'] for r in chunks)
        report[stage] = {
            'images': n, 'backend_s': elapsed, 'images_per_s': n / elapsed,
            'chunk_median_s': median(durations), 'slowest_chunk': chunks[durations.index(max(durations))]['first'],
            'chunk_max_s': max(durations), 'max_completion_to_receipt_s': max(receipts, default=0),
            'startup_to_first_chunk_s': min(r['start'] for r in chunks) - markers['begin'],
            'last_chunk_to_return_s': markers['end'] - max(finish.values()),
        }
    if 'ocr' in boundaries and 'text_detection' in boundaries:
        detect, ocr = boundaries['text_detection'], boundaries['ocr']
        report['recognition_crops_per_s'] = crops / (ocr['end'] - ocr['begin'])
        report.update(stage1_s=detect['begin'] - total['start'], stage2_s=ocr['begin'] - detect['begin'],
                      stage3_s=ocr['end'] - ocr['begin'], finalize_s=total['end'] - ocr['end'])
    for event in ('assemble', 'cleanup', 'pool_shutdown'):
        report[event + '_s'] = sum(r['end'] - r['start'] for r in rows if r['event'] == event)
    (directory / 'summary.json').write_text(json.dumps(report, indent=2), encoding='utf8')


def main() -> None:
    import shutil
    import sys

    from video_export import write_srt

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'CLI'))
    from videocr.video import Video

    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('video', 'models', 'output'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--adapter', type=int, default=0)
    parser.add_argument('--workers', type=int, choices=(1, 2, 3))
    parser.add_argument('--batch', type=int, default=4, choices=(1, 2, 4, 8))
    parser.add_argument('--opencv-threads', type=int, default=0)
    parser.add_argument('--start', default='0:00')
    parser.add_argument('--end', default='')
    parser.add_argument('--lang', default='en')
    parser.add_argument('--capture-recognition-inputs', action='store_true', help='Copy Stage 3 JPEGs for the separate recognition benchmark')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir()
    os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
    models = backend.verified_model_directory(args.models)
    original_run = backend.DirectMLVideoBackend.run

    class MeasuredPool(ProcessPoolExecutor):
        def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
            measure("pool_shutdown", super().shutdown, wait, cancel_futures=cancel_futures)

    def pool(*a: Any, **kw: Any) -> Any:
        kw.update(initializer=initialize, initargs=(out, args.batch, args.opencv_threads, *kw['initargs']))
        return MeasuredPool(*a, **kw)

    def run(self: Any, command: list[str], *a: Any) -> Iterator[str]:
        stage = command[1]
        if stage == 'ocr' and args.capture_recognition_inputs:
            source = Path(command[command.index('--input') + 1])
            shutil.copytree(source, out / 'recognition-inputs')
        record(out, event='begin', stage=stage, t=perf_counter())
        with ExitStack() as stack:
            if args.workers:
                # Override only the backend module's concurrency calculation.
                stack.enter_context(patch.object(backend, 'min', lambda *v: min(args.workers, v[2]) if len(v) == 3 else min(*v), create=True))
            for line in original_run(self, command, *a):
                if line.startswith('ppocr INFO: **********'):
                    record_name = line.removeprefix('ppocr INFO: ').strip('*')
                    # One receipt timestamp per ordered chunk.
                    if run_count[stage] % 32 == 0:
                        record(out, event='received', first=record_name, stage=stage, t=perf_counter())
                    run_count[stage] += 1
                yield line
        record(out, event='end', stage=stage, t=perf_counter())

    run_count: Counter[str] = Counter()
    instrument(out, args.batch, args.opencv_threads)

    def measure(label: str, fn: Any, *a: Any, **kw: Any) -> Any:
        before = perf_counter()
        try:
            return fn(*a, **kw)
        finally:
            record(out, event=label, start=before, end=perf_counter())
    assemble = Video.get_subtitles

    def subtitles(self: Any, *a: Any, **kw: Any) -> Any:
        return measure('assemble', assemble, self, *a, **kw)
    import psutil
    stopped = threading.Event()
    parent = psutil.Process()

    def sample() -> None:
        while not stopped.wait(1):
            try:
                processes = [parent, *parent.children(recursive=True)]
                record(out, event='resources', t=perf_counter(),
                       rss=sum(p.memory_info().rss for p in processes if p.is_running()),
                       cpu_seconds=sum(sum(p.cpu_times()[:2]) for p in processes if p.is_running()))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    monitor = threading.Thread(target=sample, daemon=True)
    monitor.start()
    with (patch.object(backend, 'ProcessPoolExecutor', pool), patch.object(backend.DirectMLVideoBackend, 'run', run),
          patch.object(Video, 'get_subtitles', subtitles), patch.object(shutil, 'rmtree', partial(measure, 'cleanup', shutil.rmtree))):
        measure('total', write_srt, args.video, out / 'output.srt', models, args.adapter, out,
                ocr_engine='paddleocr', lang=args.lang, time_start=args.start, time_end=args.end)
    stopped.set()
    monitor.join()
    summarize(out)


if __name__ == '__main__':
    main()
