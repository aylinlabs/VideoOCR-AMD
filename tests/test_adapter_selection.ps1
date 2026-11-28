$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\amd_experiment\adapter_selection.ps1')
function Assert-Fails([string]$json) {
    $failed = $false
    try { Get-SelectedAmdAdapter -Json $json | Out-Null } catch { $failed = $true }
    if (-not $failed) { throw "Expected selection failure: $json" }
}
$case = '[{"index":0,"name":"Other GPU","vendor_id":"8086","directx12":true,"dedicated_bytes":200},{"index":2,"name":"RX 6800","vendor_id":"1002","directx12":true,"dedicated_bytes":16},{"index":3,"name":"RX 7900","vendor_id":"1002","directx12":true,"dedicated_bytes":20},{"index":4,"name":"RX 9070 XT","vendor_id":"1002","directx12":false,"dedicated_bytes":32}]'
if ((Get-SelectedAmdAdapter -Json $case) -ne 3) { throw 'Wrong automatic selection' }
if ((Get-SelectedAmdAdapter -Json $case -Index 2) -ne 2) { throw 'Wrong manual selection' }
Assert-Fails '[]'
Assert-Fails 'not-json'
Assert-Fails '[{"index":1,"name":"AMD","vendor_id":"1002","directx12":false}]'
Assert-Fails '[{"index":"oops","name":"AMD","vendor_id":"1002","directx12":true}]'
Write-Host 'Adapter selection tests passed.'
