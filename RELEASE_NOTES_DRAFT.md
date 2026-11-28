# Draft release notes — VideoOCR-AMD v0.2.0 — Preview 6

**Draft for review.** The release and installer have not been published as part of this documentation work.

- Proposed tag: `v0.2.0-preview.6`
- Expected installer: `VideoOCR-AMD-Windows-x64-v0.2.0-preview.6-Setup.exe`

## Overview

This preview extends Radeon discovery and diagnostics while retaining the existing DirectML OCR models and multilingual extraction.

## What's new

- Discover eligible AMD adapters and choose a Radeon GPU automatically or manually.
- Check DirectX 12 eligibility and verify DirectML execution for both detection and recognition. Finding a GPU alone does not prove OCR compatibility.
- Apply conservative, memory-aware worker limits using available budget information when available.

## Improvements

- The Windows installer offers an installation directory, optional desktop shortcut, Start Menu integration, and launch-on-finish.
- Independent fork versioning, installer naming, and update checks handle AMD preview tags.
- Opt-in profiling and diagnostic tools help investigate performance and stability. On one previously measured RX 9070 XT workload, three workers outperformed a forced single worker. This is an observation, not a new optimization or a guarantee for other workloads.

## Compatibility

The RX 9070 XT has prior real-hardware OCR validation. The current GPU-selection changes still require a fresh end-to-end hardware check. Other RX 9000, RX 7000, and RX 6000 models are compatibility targets whose OCR operation remains **unverified on physical hardware**. DirectX 12 eligibility and successful DirectML inference depend on the adapter, driver, and available memory.

## Known limitations

- AMD language selection supports English, Simplified Chinese, and Traditional Chinese. Review SRT output for OCR and language-selection errors.
- Some operations and video processing use the CPU; GPU utilization is not a measure of overall throughput.
- Experimental cross-image recognition batching is not included. Its prior test changed recognized text and confidence scores.
- A new adapter or driver combination requires actual detector and recognizer inference validation.

## Installation and upgrade

Download the Windows x64 setup file from the release assets once published, run it, and follow the prompts. Choose a destination and optionally create a desktop shortcut. Existing installations retain the application identity for upgrade and uninstall; user settings should be preserved. Review the installer prompts and verify the upgrade on your system.

## Credits

Thanks to [Timminator and the original VideOCR contributors](https://github.com/timminator/VideOCR), and to the PaddleOCR, PaddleX, ONNX Runtime, and DirectML projects.
