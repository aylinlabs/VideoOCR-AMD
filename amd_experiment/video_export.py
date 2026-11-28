"""Run the Windows picker selection through VideOCR's video-to-SRT API."""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


def export(args: argparse.Namespace) -> None:
    from dxgi_adapters import default_worker_limit, enumerate_adapters, select_adapter
    from video_backend import verified_models

    gpu = select_adapter(enumerate_adapters(), args.adapter)
    limit = default_worker_limit(gpu['dedicated_bytes'], gpu['available_bytes'])
    write_srt(args.video, args.output, verified_models(args.image_run.resolve()),
              args.adapter, args.diagnostics, worker_limit=limit, ocr_engine='paddleocr', lang=args.lang)


def export_desktop(video_path: str, file_path: str, **settings: Any) -> None:
    from dxgi_adapters import default_worker_limit, enumerate_adapters, select_adapter
    from paddlex_runtime import engine_settings
    from video_backend import verified_model_directory

    os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
    selected = settings.pop('directml_adapter', None)
    requested_workers = settings.pop('directml_workers', None)
    adapters = enumerate_adapters()
    adapter = select_adapter(adapters, selected)
    try:
        engine_settings('directml', adapter['index'])
    except (ImportError, RuntimeError) as error:
        raise ValueError(f'DirectML is unavailable for the selected AMD GPU: {error}') from error
    limit = default_worker_limit(adapter['dedicated_bytes'], adapter['available_bytes'])
    if requested_workers is not None:
        limit = min(requested_workers, limit)
        if limit != requested_workers:
            print(f'Limited workers to {limit} for the available GPU memory budget.', flush=True)
    print(f"Using {adapter['name']} (DirectML adapter {adapter['index']}, {adapter['dedicated_bytes'] / 1024 ** 3:.1f} GiB dedicated; up to {limit} worker(s))", flush=True)
    models = verified_model_directory(Path(__file__).resolve().parents[1] / 'models')
    logs = Path(os.environ['LOCALAPPDATA']) / 'VideOCR-AMD' / 'runs'
    logs.mkdir(parents=True, exist_ok=True)
    diagnostics = Path(tempfile.mkdtemp(prefix='video-', dir=logs))
    write_srt(Path(video_path), Path(file_path), models, adapter['index'], diagnostics, worker_limit=limit, **settings)


def write_srt(video: Path, output: Path, models: Path, adapter: int, diagnostics: Path, *, worker_limit: int = 3, **settings: Any) -> None:
    from video_backend import DirectMLVideoBackend

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'CLI'))
    from videocr import save_subtitles_to_file

    output = output.resolve()
    if output.suffix.lower() != '.srt' or output.exists():
        raise ValueError('Choose a new .srt filename. An existing file will be kept.')
    backend = DirectMLVideoBackend(models, adapter, diagnostics, worker_limit=worker_limit)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        draft = Path(temp) / 'subtitles.srt'
        try:
            save_subtitles_to_file(str(video.resolve(strict=True)), str(draft),
                                   directml_backend=backend, **settings)
        finally:
            (diagnostics / 'execution.json').write_text(json.dumps({
                'dxgi_adapter': adapter, 'sampled_node_events': backend.evidence,
            }, indent=2), encoding='utf-8')
        if not draft.stat().st_size:
            raise RuntimeError('No subtitles found in the selected area and time range.')
        if 'det' not in backend.evidence.get('text_detection', {}) or 'det' not in backend.evidence.get('ocr', {}) or 'rec' not in backend.evidence.get('ocr', {}):
            raise RuntimeError('Detector or recognizer lacked recorded DirectML execution.')
        print('DirectML detector and recognizer execution verified.', flush=True)
        # Windows rename fails if another export created the destination meanwhile.
        draft.rename(output)
    print(f'Saved subtitles: {output}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for option in ('video', 'output', 'image-run', 'diagnostics'):
        parser.add_argument('--' + option, type=Path, required=True)
    parser.add_argument('--lang', default='en', help='Subtitle language (en, ch or chinese_cht)')
    parser.add_argument('--adapter', type=int, required=True)
    os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
    export(parser.parse_args())
