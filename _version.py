"""Public AMD version and Windows build metadata derived from it."""
import json
import re

__version__ = "0.2.0-preview.6"

_base, _, _preview = __version__.partition("-preview.")
DISPLAY_VERSION = f"VideoOCR-AMD v{_base}" + (f" — Preview {_preview}" if _preview else "")
# Reserve 65535 for the final release of a given major.minor.patch.
WINDOWS_VERSION = f"{_base}.{int(_preview) if _preview else 65535}"
INSTALLER_NAME = f"VideoOCR-AMD-Windows-x64-v{__version__}-Setup"

if __name__ == "__main__":
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-preview\.[1-9]\d*)?", __version__):
        raise ValueError("Invalid AMD release version")
    if any(int(part) > 65535 for part in WINDOWS_VERSION.split(".")) or (_preview and int(_preview) >= 65535):
        raise ValueError("Version exceeds Windows version-resource limits")
    print(json.dumps(dict(version=__version__, windows=WINDOWS_VERSION, artifact=INSTALLER_NAME)))
