# Read-only environment report. No serial numbers, credentials, or user paths.
$ErrorActionPreference = 'Continue'
$report = [ordered]@{}
$os = Get-CimInstance Win32_OperatingSystem
$report.windows = $os.Caption
$report.build = $os.BuildNumber
$report.architecture = $os.OSArchitecture
$app = Join-Path $env:ProgramFiles 'Elgato\StreamDeck\StreamDeck.exe'
$report.stream_deck_version = if (Test-Path $app) { (Get-Item $app).VersionInfo.ProductVersion } else { 'not found at default location' }
$report.d6_present = [bool](Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like '*VID_3142&PID_0060*' })
$report.virtual_driver = @(Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'ROOT\D6VIRTUALDECK\*' } | Select-Object Status,FriendlyName)
$report.wdk_build_targets = [bool](Test-Path "${env:ProgramFiles(x86)}\Windows Kits\10\build\*\WindowsDriver.Common.targets")
try { $report.secure_boot = Confirm-SecureBootUEFI -ErrorAction Stop } catch { $report.secure_boot = 'unknown (query unavailable)' }
$report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'diagnostic.json') -Encoding UTF8
$report | ConvertTo-Json -Depth 4
Write-Host 'Saved diagnostic.json. This script made no system changes.'
