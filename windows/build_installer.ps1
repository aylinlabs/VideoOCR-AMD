param(
    [Parameter(Mandatory)][string]$Bundle,
    [Parameter(Mandatory)][string]$OutputDirectory,
    [string]$Compiler = 'ISCC.exe'
)
$ErrorActionPreference = 'Stop'
$Bundle = (Resolve-Path -LiteralPath $Bundle).Path
$source = Get-FileHash -LiteralPath "$PSScriptRoot/../_version.py"
if ($source.Hash -ne (Get-FileHash -LiteralPath "$Bundle/app/_version.py").Hash) {
    throw 'The prepared desktop bundle has a different version source. Rebuild it first.'
}
$meta = & "$Bundle/runtime/python.exe" "$Bundle/app/_version.py" | ConvertFrom-Json
if ($LASTEXITCODE -or !$meta.artifact) { throw 'Invalid desktop release metadata' }
& $Compiler /Qp "/DBundle=$Bundle" "/DAppVersion=$($meta.version)" "/DWindowsVersion=$($meta.windows)" "/DArtifactName=$($meta.artifact)" "/O$OutputDirectory" "$PSScriptRoot/amd_setup.iss" | Out-Host
if ($LASTEXITCODE) { throw "Installer compilation failed ($LASTEXITCODE)" }
$file = Get-Item -LiteralPath (Join-Path $OutputDirectory ($meta.artifact + '.exe'))
$info = $file.VersionInfo
$numeric = ($info.FileMajorPart, $info.FileMinorPart, $info.FileBuildPart, $info.FilePrivatePart) -join '.'
if ($info.ProductVersion.TrimEnd() -ne $meta.version -or $info.FileVersion.TrimEnd() -ne $meta.version -or $numeric -ne $meta.windows) {
    throw 'Compiled installer version does not match the bundled application'
}
$file
