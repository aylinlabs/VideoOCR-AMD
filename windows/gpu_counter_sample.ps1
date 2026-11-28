function Get-GpuCounterRecords {
    param([scriptblock]$ReadCounter)
    foreach ($counter in '\GPU Engine(*)\Utilization Percentage', '\GPU Adapter Memory(*)\Dedicated Usage') {
        try {
            $sample = & $ReadCounter $counter
            $valid = @($sample.CounterSamples | Where-Object Status -eq 0 | ForEach-Object {
                @{ path = $_.Path; value = $_.CookedValue }
            })
            @{ timestamp = (Get-Date).ToString('o'); counters = $valid }
        }
        catch {
            @{ timestamp = (Get-Date).ToString('o'); counter = $counter; error = $_.Exception.Message }
        }
    }
}
