# Stage 3 audit

Baseline is master at e9f93ddebb689a792670d5ae41faf2212d8f1dfd. The profiler is opt-in and preserves the production pipeline and DirectML provider checks. It records stage boundaries, worker startup, JPEG reads, model runner and postprocessing timings, recognition batch counts, image dimensions, output box counts, process-tree RSS samples, cleanup, assembly and provider evidence. RSS sums individual processes and can count shared pages more than once. CPU samples exclude workers that already exited. GPU activity, VRAM and host-device transfer time require a separate GPU profiler.

Stage 1 decodes video, selects frames and writes stitched JPEGs. Stage 2 detects text on those grids and removes redundant frames with SSIM. Stage 3 reads individual JPEGs and repeats detection before recognizing crops. Reusing Stage 2 boxes would require exact geometry, confidence and subtitle parity tests.

The image input batch is four. PaddleX sorts detected crops by aspect ratio and uses a separate recognition batch setting of six. Effective batch sizes and dynamic-shape overhead on the current master remain unmeasured.

Earlier RX 9070 XT measurements showed recognition inference dominated worker time. A dense credits chunk contained 1,709 regions and took 15.24 seconds. JPEG reads and CTC decoding were secondary. Two-worker results varied enough that they did not establish an improvement. These are historical measurements from a different baseline, not new results.

The desktop adapter selection currently names the RX 9070 XT. RX 6000, RX 7000, other RX 9000 cards and 8 GB memory behavior remain unverified. DirectML uses sequential execution and disabled memory patterns. CPU and CUDA paths remain unchanged.

## Windows reproduction

For the guided test, download this branch as a ZIP from GitHub, extract it, and double-click Run-Performance-Test.cmd. Select the existing VideoOCR-AMD installation folder, select a subtitled video, and enter the same start and end times for every run. Keep the window open. It performs one warmup followed by three one-worker and three three-worker runs. It saves a ZIP and a results folder on the desktop. Review both before sharing because they contain subtitle text and file paths. The results file shows ranges and medians. Each run also includes its DirectML execution evidence and recognition batch histogram. GPU counters are machine-wide and may be unavailable. Check the logs to confirm the actual worker count if memory limits reduce it.

Run the following in PowerShell from this checkout. Replace the paths with a working AMD desktop bundle and the test video. Each output directory must be new.

    $python = 'C:\path\to\VideoOCR-AMD\runtime\python.exe'
    $models = 'C:\path\to\VideoOCR-AMD\app\models'
    $video = 'C:\path\to\episode.mp4'
    & $python amd_experiment/profile_video.py $video $models C:\Bench\cold
    & $python amd_experiment/profile_video.py $video $models C:\Bench\warm1
    & $python amd_experiment/profile_video.py $video $models C:\Bench\warm2
    & $python amd_experiment/profile_video.py $video $models C:\Bench\one --workers 1
    & $python amd_experiment/profile_video.py $video $models C:\Bench\two --workers 2
    & $python amd_experiment/profile_video.py $video $models C:\Bench\three --workers 3

Repeat with --start and --end for a short excerpt and the slow end section. Test --batch 2 and --opencv-threads 1 separately, alternate run order, and use Get-FileHash to compare output.srt files. Check Chinese with --lang ch and --lang chinese_cht. Use Task Manager or a GPU profiler for GPU activity and memory. Restart the PC for a cold-system measurement. Each invocation otherwise creates a fresh process and sessions.

The current sandbox reached the GPU but DirectML reported a suspended device. The provider check rejected CPU fallback. Current hardware throughput, GPU usage and VRAM are unverified.
