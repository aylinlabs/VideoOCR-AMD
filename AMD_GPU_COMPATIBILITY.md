# AMD Radeon DirectML compatibility

The desktop enumerates DXGI adapters in the same index order used by ONNX Runtime. AMD adapters are listed with their index and dedicated memory. Automatic selection prefers a discrete AMD adapter with the largest reported available budget, then dedicated capacity. When budget information is unavailable it uses dedicated capacity to break ties. You can select another listed adapter in the app. Eligibility requires AMD PCI vendor ID 1002 and a successful Direct3D 12 device-creation check. Detection alone is not proof that the OCR models work.

The selected adapter must also have the DirectML execution provider available, initialize both verified models, and execute detector and recognizer nodes on DirectML. The export checks those traces before saving its SRT. The log identifies the selected adapter and reports successful model execution. CPU fallback is rejected. Some non-inference graph operations can still be assigned to CPU and are recorded in the diagnostics.

| Generation | Examples | DirectML eligibility | Physical OCR test status |
|---|---|---|---|
| RDNA 2 | RX 6600, RX 6700 XT, RX 6800 XT | Expected if the DirectX 12 and DirectML checks pass | UNVERIFIED |
| RDNA 3 | RX 7600, RX 7700 XT, RX 7900 XTX | Expected if the DirectX 12 and DirectML checks pass | UNVERIFIED |
| RDNA 4 | RX 9060 XT, RX 9070, RX 9070 XT | Expected if the DirectX 12 and DirectML checks pass | RX 9070 XT previously tested on Preview 5; this change needs a fresh hardware run. Other cards UNVERIFIED. |

Eligibility is not a guarantee of model compatibility, available GPU memory, performance, or support for every driver. Check the log and test a representative video. DirectML and model session errors need to be resolved before an export can succeed.

Automatic worker limits use dedicated capacity and, when DXGI exposes it, the current local video-memory budget minus usage. Cards with less than 10 GiB, unknown capacity, or an unavailable DXGI budget use one worker. Cards from 10 to below 15 GiB use at most two. Larger cards use up to three. Low available budget can reduce the limit further. Manual worker selection may lower this limit. A higher selection is clamped to the current safety limit. The budget can change during a run, so it cannot guarantee that another application will not cause memory pressure. Recognition image batches and FP32 models are unchanged.

To verify on an RX 9070 XT, open the app, select AMD DirectML and Automatic or the RX 9070 XT in the AMD GPU menu, then process a short subtitled video. Check the log for the adapter name and index and the detector/recognizer verification message. Compare the resulting SRT with an earlier export. Also test a queued job and cancellation. This branch has not completed that hardware acceptance test in the current environment.
