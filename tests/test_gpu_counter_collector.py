"""Exercise Windows counter sampling when an engine disappears between reads."""
import base64
import json
import subprocess
import sys
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform == 'win32', 'Windows PowerShell test')
class GpuCounterTests(unittest.TestCase):
    def test_invalid_counter_does_not_stop_later_samples(self) -> None:
        script = Path(__file__).resolve().parents[1] / 'windows' / 'gpu_counter_sample.ps1'
        command = r'''

$script:count = 0
$reader = {
    param($Counter)
    $script:count++
    if ($script:count -eq 1) { throw 'temporarily invalid' }
    [pscustomobject]@{ CounterSamples = @(
        [pscustomobject]@{ Status = 0; Path = $Counter; CookedValue = 42 },
        [pscustomobject]@{ Status = 1; Path = 'invalid'; CookedValue = 100 }
    ) }
}
$records = @(Get-GpuCounterRecords $reader) + @(Get-GpuCounterRecords $reader)
ConvertTo-Json -InputObject $records -Depth 6 -Compress
'''
        prefix = ". '" + str(script).replace("'", "''") + "'\n"
        encoded = base64.b64encode((prefix + command).encode('utf-16-le')).decode('ascii')
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', encoded],
            capture_output=True, text=True, check=True,
        )
        records = json.loads(result.stdout)
        self.assertIn('temporarily invalid', records[0]['error'])
        for record in records[1:]:
            self.assertEqual(len(record['counters']), 1)
            self.assertEqual(record['counters'][0]['value'], 42)
