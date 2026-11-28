function Get-SelectedAmdAdapter {
    param([Parameter(Mandatory = $true)][string]$Json, [Nullable[int]]$Index = $null)
    $parsed = ConvertFrom-Json -InputObject $Json -ErrorAction Stop
    $selected = @($parsed | Where-Object { $_.vendor_id -eq '1002' -and $_.directx12 -eq $true })
    if ($null -ne $Index) { $selected = @($selected | Where-Object { $_.index -eq $Index }) }
    if ($selected.Count -eq 0) { throw 'No selected AMD GPU passed the DirectX 12 check.' }
    $selected = @($selected | Sort-Object -Property dedicated_bytes -Descending)
    $indexValue = 0
    if (-not [int]::TryParse([string]$selected[0].index, [ref]$indexValue) -or $indexValue -lt 0) { throw 'DXGI adapter index is invalid.' }
    return $indexValue
}
