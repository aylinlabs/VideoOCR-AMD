# VideoOCR-AMD

Extract burned-in subtitles from video into a timed SubRip (`.srt`) file. VideoOCR-AMD is a Windows-first fork of [Timminator's VideOCR](https://github.com/timminator/VideOCR), with an experimental AMD Radeon path using PaddleOCR and ONNX Runtime DirectML.

[Download for Windows](https://github.com/SimpleCraftApp/VideoOCR-AMD/releases) · [GPU compatibility](AMD_GPU_COMPATIBILITY.md) · [Changelog](CHANGELOG.md) · [Upstream project](https://github.com/timminator/VideOCR)

## Features

- Extract subtitles from videos into timestamped SRT files.
- Select a subtitle region, process a queue, and pause or cancel work.
- Use AMD Radeon acceleration through DirectML, with automatic or manual adapter selection in the current source.
- Extract English, Simplified Chinese, or Traditional Chinese subtitles with the AMD OCR path.
- Adjust worker settings within memory-aware limits and inspect diagnostic information.
- Use the existing CPU and NVIDIA CUDA paths where configured and supported.

![Earlier VideOCR interface](Pictures/GUI.png)

The image shows an earlier interface. Controls can differ in current builds.

## Install on Windows

1. Open the [Releases page](https://github.com/SimpleCraftApp/VideoOCR-AMD/releases) and download the Windows x64 installer from the release you want to use.
2. Run the installer and follow its prompts. Installation options vary between releases.
3. Open VideoOCR-AMD from the Start menu. The installer includes the application and its runtime dependencies.

The GPU selection and memory controls described below are present in the current source. Check the release notes for the build you install, as earlier downloads may have different controls.

## Extract subtitles

1. Open a video and choose where to save the SRT file.
2. Choose the AMD DirectML OCR engine and the subtitle language. Older releases may show a slightly different engine label.
3. If useful, select a crop around the subtitles to reduce unrelated on-screen text.
4. Run the extraction and review the resulting SRT for recognition, language-selection, and timing errors.

## AMD DirectML and GPU selection

The current source discovers AMD adapters through DXGI and checks DirectX 12 eligibility. Automatic selection prefers an eligible discrete Radeon adapter, considering available memory. You can also choose an adapter manually. Adapter numbers are not assumed to start with a particular GPU.

Detection alone does **not** establish OCR compatibility. The application also needs an available DirectML provider, working detector and recognizer sessions, successful inference, and evidence that DirectML actually executes model nodes. Some model operations may still run on the CPU. Errors are reported when the AMD path cannot be verified.

Worker limits take account of dedicated memory and the available GPU memory budget when it can be queried. The application applies conservative limits when memory is low or unknown; requested worker counts can be capped. Available memory changes as other applications use the GPU, so installed VRAM is not the same as free VRAM.

## Languages

The AMD DirectML path currently supports **English**, **Simplified Chinese**, and **Traditional Chinese** selection. Simultaneous languages, stylized text, scene text, credits, and mixed-script names may require manual correction. See the [multilingual notes](PREVIEW_5_MULTILINGUAL.md) for the scope and test results. Other upstream language mappings should not be taken as a claim of AMD support.

## GPU compatibility

| Radeon generation | Examples | Status |
| --- | --- | --- |
| RX 9000 / RDNA 4 | RX 9070 XT | Prior real-hardware OCR validation; changes to GPU selection still need a fresh hardware check. |
| RX 9000 / RDNA 4 | Other RX 9000 models | Discovery and selection implemented; hardware OCR unverified. |
| RX 7000 / RDNA 3 | RX 7900 XT, RX 7800 XT | Discovery and selection implemented; hardware OCR unverified. |
| RX 6000 / RDNA 2 | RX 6800 XT, RX 6600 | Discovery and selection implemented; hardware OCR unverified. |

An AMD vendor ID does not guarantee DirectX 12 or DirectML compatibility. See [GPU compatibility and diagnostics](AMD_GPU_COMPATIBILITY.md) for eligibility checks, memory behavior, and limitations. Mocked tests are not hardware validation.

## System requirements

- Windows 11 x64 is the primary development and testing environment.
- For AMD acceleration, a compatible AMD GPU, a working DirectX 12 driver, and DirectML support are required. Compatibility depends on the device and driver.
- Sufficient disk space is required for the application, OCR models, input video, and temporary files. GPU memory requirements depend on the workload and worker count.
- Internet access is needed to download the installer and any models that are not already available locally.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| No eligible Radeon GPU appears | Confirm Windows sees the adapter and its driver supports DirectX 12. Restart the app after hardware or driver changes. |
| DirectML initialization or inference fails | Review the diagnostic message, close GPU-heavy applications, and try fewer workers. Detection by itself does not verify inference. |
| Subtitles include unwanted text | Crop closer to the subtitle area, select the intended language, and review the output. Mixed-script or overlapping text can remain ambiguous. |
| Extraction is slow or runs out of memory | Reduce concurrent GPU workloads or workers. Video decoding and parts of OCR also use the CPU. GPU utilization alone does not measure end-to-end speed. |
| Installation or model access fails | Check available space and folder permissions, then follow the instructions for the specific release. |

For more detail, see [AMD desktop notes](AMD_DESKTOP.md) and [GPU compatibility](AMD_GPU_COMPATIBILITY.md).

## Credits and license

VideoOCR-AMD builds on [VideOCR by Timminator](https://github.com/timminator/VideOCR) and its contributors. It also uses PaddleOCR, PaddleX, ONNX Runtime, and DirectML. See [LICENSE](LICENSE) and the respective projects for license terms.
