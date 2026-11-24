import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from _version import DISPLAY_VERSION, INSTALLER_NAME, WINDOWS_VERSION, __version__
from amd_updates import available_update, version_key


def release(tag: str, *, draft: bool = False, preview: bool = True) -> dict[str, object]:
    return {'tag_name': tag, 'draft': draft, 'prerelease': preview}


class ReleaseTests(unittest.TestCase):
    def test_migration_and_stable_order(self) -> None:
        tags = ['v1.6.0-amd-preview.4', 'v1.6.0-amd-preview.5', 'v0.2.0-preview.6',
                'v0.2.0-preview.10', 'v0.2.0-rc.1', 'v0.2.0', 'v0.3.0-alpha.1']
        for first, second in zip(tags, tags[1:], strict=False):
            a, b = version_key(first), version_key(second)
            assert a is not None and b is not None
            self.assertLess(a, b)
        for tag in ('latest', 'v0.2', 'v0.2.0-preview.x', 'v01.2.3', 'v0.2.0-preview.6/other'):
            self.assertIsNone(version_key(tag))

    def test_published_channels_and_url(self) -> None:
        releases = [release('v1.6.0-amd-preview.5'), release('v0.2.0-preview.9', draft=True),
                    release('bad'), release('v0.2.0-preview.7'), release('v0.1.0', preview=False)]
        for current, expected in [('0.2.0-preview.6', 'v0.2.0-preview.7'), ('0.2.0', None),
                                  ('0.2.0-preview.7', None), ('1.6.0-amd-preview.5', 'v0.2.0-preview.7')]:
            with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(releases).encode())):
                found = available_update(current)
                self.assertEqual(found, {'version': expected, 'url': f'https://github.com/aylinlabs/VideoOCR-AMD/releases/tag/{expected}'} if expected else None)

    def test_offline_error_is_distinct_from_no_update(self) -> None:
        with patch('urllib.request.urlopen', side_effect=URLError('offline')), self.assertRaises(URLError):
            available_update()

    def test_metadata(self) -> None:
        self.assertIn(__version__, INSTALLER_NAME)
        self.assertIn(__version__.split('-')[0], DISPLAY_VERSION)
        self.assertEqual(len(WINDOWS_VERSION.split('.')), 4)
