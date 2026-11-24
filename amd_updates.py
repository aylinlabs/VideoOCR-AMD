"""Find published fork releases on the current user's update channel."""
from __future__ import annotations

import json
import re
import urllib.request

from _version import __version__

REPO = "aylinlabs/VideoOCR-AMD"
_VERSION = re.compile(r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-(alpha|beta|preview|rc)\.(0|[1-9]\d*))?", re.ASCII)


def version_key(tag: str) -> tuple[int, ...] | None:
    old = re.fullmatch(r"v?1\.6\.0-amd-preview\.([1-9]\d*)", tag, re.ASCII)
    if old:
        return (0, int(old[1]))
    match = _VERSION.fullmatch(tag)
    if not match:
        return None
    major, minor, patch, stage, number = match.groups()
    return (1, int(major), int(minor), int(patch), ('alpha', 'beta', 'preview', 'rc', None).index(stage), int(number or 0))


def available_update(current: str = __version__) -> dict[str, str] | None:
    best = version_key(current)
    if best is None:
        raise ValueError("Unknown installed version")
    preview_channel = '-' in current
    result = None
    page = 1
    while True:
        request = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases?per_page=100&page={page}",
                                         headers={'User-Agent': 'VideoOCR-AMD', 'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(request, timeout=5) as response:
            releases = json.load(response)
        if not isinstance(releases, list):
            raise ValueError("Unexpected GitHub releases response")
        for release in releases:
            if not isinstance(release, dict) or release.get('draft') is not False:
                continue
            tag = release.get('tag_name')
            if not isinstance(tag, str) or (not preview_channel and (release.get('prerelease') or '-' in tag)):
                continue
            key = version_key(tag)
            if key is not None and key > best:
                best = key
                result = {'version': tag, 'url': f'https://github.com/{REPO}/releases/tag/{tag}'}
        if len(releases) < 100:
            return result
        page += 1
