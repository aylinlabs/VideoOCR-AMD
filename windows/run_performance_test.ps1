Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName Microsoft.VisualBasic
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$report = $null
try {
    $picker = New-Object System.Windows.Forms.FolderBrowserDialog
    $picker.Description = 'Choose the VideoOCR-AMD installation folder containing app and runtime'
    $picker.SelectedPath = Join-Path $env:LOCALAPPDATA 'Programs\VideoOCR-AMD'
    if ($picker.ShowDialog() -ne 'OK') { return }
    $bundle = $picker.SelectedPath
    $python = Join-Path $bundle 'runtime\python.exe'
    $models = Join-Path $bundle 'app\models'
    if (!(Test-Path -LiteralPath $python) -or !(Test-Path -LiteralPath "$models\det\inference.onnx") -or !(Test-Path -LiteralPath "$models\rec\inference.onnx")) {
        throw 'That folder does not contain the bundled Python runtime and OCR models.'
    }
    $file = New-Object System.Windows.Forms.OpenFileDialog
    $file.Title = 'Choose the same subtitled video for each run'
    $file.Filter = 'Video files|*.mp4;*.mkv;*.avi;*.mov;*.webm|All files|*.*'
    if ($file.ShowDialog() -ne 'OK') { return }
    $start = [Microsoft.VisualBasic.Interaction]::InputBox('Start time (minutes:seconds)', 'Benchmark excerpt', '0:00')
    $end = [Microsoft.VisualBasic.Interaction]::InputBox('End time (minutes:seconds). Use a short subtitled section for the first test.', 'Benchmark excerpt', '2:00')
    if ($start -notmatch '^\d+:\d{2}$' -or $end -notmatch '^\d+:\d{2}$') { throw 'Enter times such as 0:00 and 2:00.' }
    $desktop = [Environment]::GetFolderPath('Desktop')
    $report = Join-Path $desktop ('VideoOCR-benchmark-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Path $report | Out-Null
    $profile = Join-Path $root 'amd_experiment\profile_video.py'
    $metadata = [ordered]@{
        video_sha256 = (Get-FileHash -LiteralPath $file.FileName -Algorithm SHA256).Hash
        detection_sha256 = (Get-FileHash -LiteralPath "$models\det\inference.onnx").Hash
        recognition_sha256 = (Get-FileHash -LiteralPath "$models\rec\inference.onnx").Hash
        start = $start; end = $end; language = 'en'; adapter = 0
        gpu_counters = 'Machine-wide Windows GPU engine and adapter counters are sampled when available.'
        privacy = 'Logs may contain file paths and recognized text. Review them before sharing.'
    }
    $metadata | ConvertTo-Json | Set-Content -LiteralPath "$report\test-info.json" -Encoding utf8
    $counterJob = Start-Job -ArgumentList $report -ScriptBlock {
        param($Destination)
        try {
            while ($true) {
                $sample = Get-Counter '\GPU Engine(*)\Utilization Percentage', '\GPU Adapter Memory(*)\Dedicated Usage' -ErrorAction Stop
                $record = @{ timestamp = (Get-Date).ToString('o'); counters = @($sample.CounterSamples | ForEach-Object {
                    @{ path = $_.Path; value = $_.CookedValue }
                }) }
                $record | ConvertTo-Json -Depth 5 -Compress | Add-Content -LiteralPath "$Destination\gpu-counters.jsonl" -Encoding utf8
                Start-Sleep -Seconds 2
            }
        }
        catch {
            $_.Exception.Message | Set-Content -LiteralPath "$Destination\gpu-counters-unavailable.txt" -Encoding utf8
        }
    }
    $runs = @(@('warmup', 1), @('one-1', 1), @('three-1', 3), @('three-2', 3), @('one-2', 1), @('one-3', 1), @('three-3', 3))
    foreach ($run in $runs) {
        $name = $run[0]
        $workers = $run[1]
        Write-Host "Running $name with $workers worker(s). Please keep this window open."
        $output = Join-Path $report $name
        $log = Join-Path $report "$name.log"
        $errorLog = Join-Path $report "$name-stderr.log"
        $arguments = @('-B', ('"{0}"' -f $profile), ('"{0}"' -f $file.FileName), ('"{0}"' -f $models),
                       ('"{0}"' -f $output), '--start', $start, '--end', $end,
                       '--workers', $workers, '--lang', 'en')
        $process = Start-Process -FilePath $python -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $log -RedirectStandardError $errorLog
        if ($process.ExitCode -ne 0 -or !(Test-Path "$output\summary.json") -or !(Test-Path "$output\output.srt") -or !(Test-Path "$output\execution.json")) {
            throw "The $name run failed (exit $($process.ExitCode)). Check its log and stderr log. Remaining runs were stopped."
        }
        $evidence = Get-Content "$output\execution.json" -Raw | ConvertFrom-Json
        if (!$evidence.sampled_node_events.ocr.rec.counts.DmlExecutionProvider) {
            throw "The $name run lacks DirectML recognition evidence."
        }
        (Get-FileHash "$output\output.srt").Hash | Set-Content "$output\srt-sha256.txt"
    }
    $hashes = @($runs | ForEach-Object { (Get-Content (Join-Path $report ($_[0] + '\srt-sha256.txt')) -Raw).Trim() } | Select-Object -Unique)
    if ($hashes.Count -eq 1) { 'All SRT hashes match.' | Set-Content "$report\comparison.txt" }
    else { 'SRT hashes differ. Review the outputs before considering any performance results equivalent.' | Set-Content "$report\comparison.txt" }
    $summaryLines = @('Times are seconds. The warmup is excluded from ranges.', '')
    foreach ($workers in 1, 3) {
        $measurements = @(1..3 | ForEach-Object {
            Get-Content (Join-Path $report ("$(@('one', 'three')[($workers - 1) / 2])-$_\summary.json")) -Raw | ConvertFrom-Json
        })
        $summaryLines += "Requested workers: $workers"
        foreach ($key in 'stage1_s', 'stage2_s', 'stage3_s', 'finalize_s', 'total_s', 'recognition_crops_per_s', 'peak_sampled_process_tree_rss_bytes') {
            $values = @($measurements | ForEach-Object { [double]$_.$key } | Sort-Object)
            $summaryLines += ("  {0}: min {1:N2}, median {2:N2}, max {3:N2}" -f $key, $values[0], $values[1], $values[2])
        }
        $summaryLines += ''
    }
    $summaryLines | Set-Content "$report\results.txt" -Encoding utf8
    Write-Host 'Finished. The report includes the subtitle outputs for comparison.'
}
catch {
    Write-Host "Benchmark stopped: $($_.Exception.Message)"
    if ($report) { $_.Exception.ToString() | Set-Content -LiteralPath "$report\error.txt" }
}
finally {
    if ($counterJob) {
        Stop-Job $counterJob -ErrorAction SilentlyContinue
        Remove-Job $counterJob -Force -ErrorAction SilentlyContinue
    }
    if ($report -and (Test-Path -LiteralPath $report)) {
        Compress-Archive -Path "$report\*" -DestinationPath "$report.zip"
        Write-Host "Report saved to $report.zip"
        Write-Host 'The report includes logs, local file paths, and subtitle text. Review before sharing.'
        [System.Windows.Forms.MessageBox]::Show("Report saved to $report.zip`nReview its logs and subtitle text before sharing.", 'VideoOCR benchmark') | Out-Null
    }
}
