# Exercise actual per-user installation only on GitHub's disposable Windows VM.
param([Parameter(Mandatory)][string]$Setup)
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or !$env:ImageOS) { throw 'Run this check on a hosted Windows runner' }
$default = Join-Path $env:LOCALAPPDATA 'Programs/VideoOCR-AMD'
$custom = Join-Path $env:RUNNER_TEMP 'Custom OCR installation'
$prefs = Join-Path $env:APPDATA 'VideOCR-AMD/videocr_gui_config.ini'
$desktop = Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'VideoOCR-AMD.lnk'
$start = Join-Path ([Environment]::GetFolderPath('Programs')) 'VideoOCR-AMD.lnk'
$key = 'HKCU:/Software/Microsoft/Windows/CurrentVersion/Uninstall/{3F76B8ED-A880-454A-9897-EEC40E06F710}_is1'
$version = (python _version.py | ConvertFrom-Json).version
function Run-Setup([string]$File, [string]$Options) {
    $process = Start-Process -FilePath $File -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART $Options" -Wait -PassThru
    if ($process.ExitCode) { throw "$File exited $($process.ExitCode)" }
}
function Check-Install([string]$Dir, [bool]$HasDesktop) {
    $entry = Get-ItemProperty -LiteralPath $key
    if ($entry.DisplayVersion -ne $version -or $entry.InstallLocation.TrimEnd('\') -ne $Dir) { throw 'Incorrect registered installation' }
    if (!(Test-Path -LiteralPath "$Dir/VideOCR-AMD.exe") -or !(Test-Path -LiteralPath $start)) { throw 'Missing launcher or Start menu entry' }
    if ((Test-Path -LiteralPath $desktop) -ne $HasDesktop) { throw 'Unexpected desktop shortcut state' }
    $shell = New-Object -ComObject WScript.Shell
    if ($shell.CreateShortcut($start).TargetPath -ne (Join-Path $Dir 'VideOCR-AMD.exe')) { throw 'Start shortcut targets wrong launcher' }
    if ($HasDesktop -and $shell.CreateShortcut($desktop).TargetPath -ne (Join-Path $Dir 'VideOCR-AMD.exe')) { throw 'Desktop shortcut targets wrong launcher' }
}
function Uninstall {
    $uninstaller = (Get-ItemProperty -LiteralPath $key).UninstallString.Trim('"')
    Run-Setup $uninstaller ''
    if ((Test-Path $key) -or (Test-Path $start) -or (Test-Path $desktop)) { throw 'Uninstall left registration or shortcuts' }
}
if ((Test-Path $key) -or (Test-Path $prefs)) { throw 'Expected a fresh user profile' }
Run-Setup $Setup ''
Check-Install $default $false
Uninstall

# Install the published predecessor, then let Setup rediscover its custom path via the shared AppId.
$release = Invoke-RestMethod 'https://api.github.com/repos/aylinlabs/VideoOCR-AMD/releases/tags/v1.6.0-amd-preview.5'
$assets = @($release.assets | Where-Object name -Match 'Setup\.exe$')
if ($assets.Count -ne 1 -or $assets[0].digest -notmatch '^sha256:[0-9a-f]{64}$') { throw 'Expected one checksummed Preview 5 installer' }
$old = Join-Path $env:RUNNER_TEMP 'previous-setup.exe'
Invoke-WebRequest $assets[0].browser_download_url -OutFile $old
if ("sha256:$((Get-FileHash $old).Hash)" -ne $assets[0].digest) { throw 'Preview 5 installer checksum mismatch' }
Run-Setup $old ('/DIR="{0}"' -f $custom)
$oldVersion = (Get-ItemProperty -LiteralPath $key).DisplayVersion
if ($oldVersion -notlike '1.6.0-amd-preview.*') { throw "Unexpected predecessor $oldVersion" }
New-Item -ItemType Directory (Split-Path $prefs) -Force | Out-Null
Set-Content -LiteralPath $prefs -Value "[General]`r`nproof=keep"
$settingsHash = (Get-FileHash $prefs).Hash
Run-Setup $Setup '/TASKS="desktopicon"'
Check-Install $custom $true
Run-Setup $Setup ''
Check-Install $custom $true
if ((Get-FileHash $prefs).Hash -ne $settingsHash) { throw 'Upgrade or reinstall modified settings' }
Uninstall
if ((Get-FileHash $prefs).Hash -ne $settingsHash -or (Test-Path "$custom/VideOCR-AMD.exe")) { throw 'Uninstall failed to preserve settings or remove launcher' }
Run-Setup $Setup ('/DIR="{0}" /TASKS="desktopicon"' -f $custom)
Check-Install $custom $true
Uninstall
