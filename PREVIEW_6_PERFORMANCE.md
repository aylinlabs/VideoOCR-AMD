# DirectML desktop performance on the RX 9070 XT

## Reproducing the benchmark

Use the desktop Python 3.12 runtime, its verified det/rec model directory, and a checkout of the source. The profiler runs the normal video-to-SRT export on DirectML adapter 0. Supply a new output directory for each run.

```powershell
& $python amd_experiment/profile_video.py $video $models results-base
& $python amd_experiment/profile_video.py $video $models results-tail --start 20:16 --end 22:16 --workers 2 --batch 4
```

For a baseline, copy the same profiler into the released Preview 5 checkout. Keep the crop, language, video, model files and settings identical, and run one export at a time. Compare the SRT files including timestamps. Use `--lang ch` or `--lang chinese_cht` for the Chinese exports. Worker and batch overrides apply only to the benchmark. The batch option controls file prefetch and the OCR pipeline input batch; the recognizer retains its own configured line batch. OpenCV thread overrides apply to the benchmark process and its children.

Each run writes an SRT, the normal provider evidence, per-process JSON lines and a timing summary. Stage 1 extends from export entry to detection backend entry. Stage 2 includes detection, redundancy analysis and preparing the recognition inputs. Stage 3 includes worker startup, OCR, ordered delivery and shutdown. Finalization includes frame mapping, temporary-file removal, assembly and output. Costs recorded at the model runner boundary include synchronization and transfers. Worker seconds overlap across workers, as do JPEG reads with inference. Receipts record when the parent consumes the first result of each 32-image chunk.

## Worker and batch experiment

Final two minutes of the 22:16 bilingual episode, English, 637 OCR images. Forced worker counts apply to both passes, including the short detection pass. Times below are single runs in seconds. All eight output files matched byte for byte.

| Workers | Input batch | OpenCV threads | Stage 3 | Total |
|---:|---:|---|---:|---:|
| 1 | 4 | default | 15.63 | 19.73 |
| 2 | 4 | default | 10.75 | 16.72 |
| 3 | 4 | default | 14.90 | 21.70 |
| 1 | 4 | 1 | 18.25 | 22.36 |
| 2 | 4 | 1 | 11.80 | 17.73 |
| 3 | 4 | 1 | 12.38 | 18.37 |
| 3 | 2 | 1 | 10.68 | 16.64 |
| 3 | 8 | 1 | 11.18 | 17.14 |

## Where the time goes

The full Preview 5 run produced 7,321 Stage 3 JPEGs, all 720 × 100. The first quarter averaged 2.55 recognized regions per image and the last quarter 15.85. The slowest chunks began at images 6304, 6336 and 6368, with 1,709, 1,668 and 1,676 recognized regions. They took 15.24, 14.65 and 14.24 seconds. The median chunk took 1.43 seconds. Timing only the final two minutes misses part of this dense sequence.

The three workers completed 80, 76 and 73 chunks. Summed across them, the recognition runner used 407 seconds, JPEG reading 63, recognition postprocessing 46, preprocessing 15, detection inference 14 and detection postprocessing 6. Mean sampled worker RSS increased from 524 to 738 MiB across those quarters. The density increase and recognition timings explain expensive chunks. These measurements do not establish a memory leak or isolate GPU transfer time.

Ordered delivery delayed a completed chunk by up to 2.41 seconds. The executor already schedules queued chunks while the parent waits. This explains pauses in visible progress without establishing that out-of-order collection would shorten the export. Provider samples confirmed DirectML detection and recognition, with sampled CPU Slice and Concat operations in recognition. Measuring individual transfers would require a separate device trace.

Stage 2 already removed 5,117 redundant frames. Its boxes come from stitched detection grids. Stage 3 detects again on individually repacked JPEGs. Equivalent boxes, scores and SRTs from reusing grid detections have not been demonstrated. The baseline spent 1.26 seconds removing the working directory and 0.11 seconds assembling the SRT.

## Worker cap experiment

A blanket two-worker cap looked promising in the first full run (171.98 s Stage 3 versus 175.65 s; 200.41 s total versus 206.24 s). Repeating in reverse order gave 214.14 s versus 121.05 s (244.30 s total versus 149.34 s). Shorter repeated tests with automatic detection worker selection likewise gave 14.97/12.63 s for two recognition workers and 13.85/10.55 s for three. Two workers had shorter worst-case chunks on the first run but higher per-worker RSS. The shipped candidate retains the original worker count policy, input batches and ordering.

## Recognition postprocessing

The pinned PaddleX CTC decoder copies the complete recognition output, scans its vocabulary axis for the winning character, then scans that axis again for its probability. For normal video subtitles the candidate reads the existing logits, computes the same winning indices and gathers their probabilities directly. The existing PaddleX decoder still removes blanks/repeats, looks up characters and computes confidence. Word-box requests take the original path.

A paired CPU benchmark used float32 tensors, six lines per batch, the verified model's 18,710 classes, and 40 alternating-order comparisons per shape on this machine. Median decoding fell from 2.03 to 0.31 ms at 32 time steps and from 5.56 to 0.81 ms at 80. The two paths returned identical text and scores on the same seeded inputs and on tied inputs. The pinned ORT runner passes contiguous NumPy inputs to session.run and returns CPU outputs. The change removes extra host memory traffic after that boundary; the GPU graph and provider configuration are identical.

## End-to-end comparison

AX_spiritual_realm_ep_13_eng.mp4, 22:16, English, default crop/settings, adapter 0, one export at a time. The baseline source tree matched release tag v1.6.0-amd-preview.5.

| Input and version | Detection / OCR workers | Stage 1 s | Stage 2 s | Stage 3 s | Final s | Total s | OCR images/s |
|---|---|---:|---:|---:|---:|---:|---:|
| Full, Preview 5 first run | 3 / 3 | 15.56 | 13.23 | 175.65 | 1.80 | 206.24 | 41.68 |
| Full, Preview 5 repeat | 3 / 3 | 15.39 | 11.24 | 121.05 | 1.67 | 149.34 | 60.48 |
| 04:02–04:11, Preview 5 | 1 / 1 | 0.79 | 1.86 | 2.84 | 0.02 | 5.51 | 16.56 |
| Full, optimized decoder | 3 / 3 | 15.65 | 12.26 | 156.11 | 1.75 | 185.77 | 46.90 |
| 04:02–04:11, optimized decoder | 1 / 1 | 0.76 | 1.69 | 2.62 | 0.02 | 5.09 | 17.96 |

Full recognition postprocessing fell from 45.52 and 30.67 worker-seconds in the baseline runs to 8.90. The candidate's median and maximum full-episode chunks took 1.30 and 13.33 seconds. Pool shutdown took 0.30 seconds for detection and 0.55 for OCR. Temporary cleanup took 1.22 seconds and SRT assembly 0.11. The full-episode elapsed time falls inside the observed baseline range; a universal end-to-end speedup is unverified. Recognition inference is still the largest cost.

The paired full English SRTs matched byte for byte (SHA-256 67bc6bfb1105e8cb49b4c176bf393158b6cf5b6a8689ef64be047697d9bcd8c3). The nine-second English, Simplified Chinese and Traditional Chinese exports matched their saved reference SRTs including timestamps. A historical full English reference differed in several credits cues even from the fresh Preview 5 baseline. The fresh release-baseline and candidate runs on this machine produced 7,321 recognition images, compared with 7,562 originally reported. Other hardware and episodes remain unmeasured.
