Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName Microsoft.VisualBasic
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$report = $null
try {
    $picker = New-Object System.Windows.Forms.FolderBrowserDialog
    $picker.Description = 'Choose the installed VideoOCR-AMD folder containing app and runtime'
    $picker.SelectedPath = Join-Path $env:LOCALAPPDATA 'Programs\VideoOCR-AMD'
    if ($picker.ShowDialog() -ne 'OK') { return }
    $python = Join-Path $picker.SelectedPath 'runtime\python.exe'
    $models = Join-Path $picker.SelectedPath 'app\models'
    if (!(Test-Path $python) -or !(Test-Path "$models\det\inference.onnx") -or !(Test-Path "$models\rec\inference.onnx")) { throw 'Choose the installation folder containing the runtime and models.' }
    $file = New-Object System.Windows.Forms.OpenFileDialog
    $file.Title = 'Choose the same video used for the previous benchmark'
    $file.Filter = 'Video files|*.mp4;*.mkv;*.avi;*.mov;*.webm|All files|*.*'
    if ($file.ShowDialog() -ne 'OK') { return }
    $start = [Microsoft.VisualBasic.Interaction]::InputBox('Start time (minutes:seconds)', 'Benchmark excerpt', '0:00')
    $end = [Microsoft.VisualBasic.Interaction]::InputBox('End time (minutes:seconds)', 'Benchmark excerpt', '7:00')
    if ($start -notmatch '^\d+:\d{2}$' -or $end -notmatch '^\d+:\d{2}$') { throw 'Enter times such as 0:00 and 7:00.' }
    $report = Join-Path ([Environment]::GetFolderPath('Desktop')) ('VideoOCR-batch-experiment-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Path $report | Out-Null
    $share = Join-Path $report 'report'
    New-Item -ItemType Directory -Path $share | Out-Null
    $capture = Join-Path $report 'capture'
    $probe = Join-Path $report 'probe'
    $profile = Join-Path $root 'amd_experiment\profile_video.py'
    $bench = Join-Path $root 'amd_experiment\benchmark_recognition_batches.py'
    $info = @{ video_sha256 = (Get-FileHash -LiteralPath $file.FileName).Hash; start = $start; end = $end;
               detection_sha256 = (Get-FileHash "$models\det\inference.onnx").Hash;
               recognition_sha256 = (Get-FileHash "$models\rec\inference.onnx").Hash }
    $info | ConvertTo-Json | Set-Content "$share\inputs.json" -Encoding utf8
    $counterJob = Start-Job -ArgumentList $share, (Join-Path $PSScriptRoot 'gpu_counter_sample.ps1') -ScriptBlock {
        param($Destination, $CounterScript)
        . $CounterScript
        while ($true) {
            foreach ($record in (Get-GpuCounterRecords { param($Counter) Get-Counter $Counter -ErrorAction Stop })) {
                $record | ConvertTo-Json -Depth 6 -Compress | Add-Content "$Destination\gpu-counters.jsonl" -Encoding utf8
            }
            Start-Sleep -Seconds 2
        }
    }
    Write-Host 'Capturing the normal three-worker Stage 3 inputs. Please keep this window open.'
    $arguments = @('-B', ('"{0}"' -f $profile), ('"{0}"' -f $file.FileName), ('"{0}"' -f $models), ('"{0}"' -f $capture), '--start', $start, '--end', $end, '--workers', '3', '--lang', 'en', '--capture-recognition-inputs')
    $process = Start-Process -FilePath $python -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput "$share\capture.log" -RedirectStandardError "$share\capture-stderr.log"
    if ($process.ExitCode -ne 0 -or !(Test-Path "$capture\summary.json") -or !(Test-Path "$capture\output.srt")) { throw "Capture failed (exit $($process.ExitCode))." }
    Copy-Item "$capture\summary.json", "$capture\execution.json", "$capture\output.srt" -Destination $share
    if ([System.Windows.Forms.MessageBox]::Show('Compare the captured SRT with a saved SRT from your previous benchmark?', 'Compare baseline', 'YesNo') -eq 'Yes') {
        $baseline = New-Object System.Windows.Forms.OpenFileDialog
        $baseline.Title = 'Choose the previous benchmark output.srt'
        $baseline.Filter = 'Subtitle files|*.srt|All files|*.*'
        if ($baseline.ShowDialog() -eq 'OK') {
            $oldHash = (Get-FileHash -LiteralPath $baseline.FileName).Hash
            $newHash = (Get-FileHash "$capture\output.srt").Hash
            @{ previous_sha256 = $oldHash; capture_sha256 = $newHash; identical = ($oldHash -eq $newHash) } | ConvertTo-Json | Set-Content "$share\srt-comparison.json" -Encoding utf8
        }
    }
    Write-Host 'Comparing original recognition with experimental batches. This may take several minutes.'
    $arguments = @('-B', ('"{0}"' -f $bench), ('"{0}"' -f "$capture\recognition-inputs"), ('"{0}"' -f $models), ('"{0}"' -f $probe), '--repeat', '3')
    $process = Start-Process -FilePath $python -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput "$share\probe.log" -RedirectStandardError "$share\probe-stderr.log"
    if (Test-Path "$probe\recognition-benchmark.json") { Copy-Item "$probe\recognition-benchmark.json" $share }
    if ($process.ExitCode -ne 0) { throw "Recognition probe failed or detected a parity difference (exit $($process.ExitCode))." }
    Write-Host 'Experiment completed.'
}
catch {
    Write-Host "Experiment stopped: $($_.Exception.Message)"
    if ($report) { $_.Exception.ToString() | Set-Content "$share\error.txt" -Encoding utf8 }
}
finally {
    if ($counterJob) { Stop-Job $counterJob -ErrorAction SilentlyContinue; Remove-Job $counterJob -Force -ErrorAction SilentlyContinue }
    if ($report -and (Test-Path $share)) {
        Compress-Archive -Path "$share\*" -DestinationPath "$report.zip"
        Write-Host "Report saved to $report.zip. Captured images remain in $capture."
        [System.Windows.Forms.MessageBox]::Show("Report saved to $report.zip. Review the subtitle text and file paths before sharing.", 'VideoOCR batch experiment') | Out-Null
    }
}
