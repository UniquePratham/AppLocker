# Aegis installer (portable, per-user).
#
# Installs Aegis.exe into %LOCALAPPDATA%\Programs\Aegis (no admin
# required), registers an uninstall entry, and optionally enables the
# "run at login" startup entry that the app uses.
#
# Usage:
#   .\install.ps1                    # install from .\release\Aegis.exe
#   .\install.ps1 -Startup           # also enable run-at-login
#   .\install.ps1 -Uninstall         # remove installed copy + uninstall entry

[cmdletbinding()]
param(
    [switch]$Uninstall,
    [switch]$Startup,
    [string]$Source = "$PSScriptRoot\release\Aegis.exe"
)

$ErrorActionPreference = "Stop"
$appName = "Aegis"
$installDir = Join-Path $env:LOCALAPPDATA "Programs\Aegis"
$exe = Join-Path $installDir "Aegis.exe"

function Get-UninstallKey($suffix = "") {
    $reg = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\${appName}${suffix}"
    return $reg
}

if ($Uninstall) {
    Write-Host "Uninstalling Aegis..."
    if (Test-Path $exe) {
        Remove-Item -LiteralPath $installDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -Path (Get-UninstallKey) -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Uninstaller entry removed."
    Write-Host "Note: protected-app policies and your master password remain in %LOCALAPPDATA%\Aegis."
    exit 0
}

if (!(Test-Path $Source)) {
    Write-Error "Aegis.exe not found at '$Source'. Run build.ps1 first."
}

New-Item -ItemType Directory -Force -Path $installDir | Out-Null
Copy-Item -LiteralPath $Source -Destination $exe -Force

$version = (Get-Item $exe).VersionInfo.ProductVersion
if (-not $version) { $version = "2.0.0" }

$uninstallKey = Get-UninstallKey
New-Item -Path $uninstallKey -Force | Out-Null
Set-ItemProperty $uninstallKey -Name "DisplayName" -Value $appName
Set-ItemProperty $uninstallKey -Name "DisplayVersion" -Value $version
Set-ItemProperty $uninstallKey -Name "DisplayIcon" -Value "`"$exe`""
Set-ItemProperty $uninstallKey -Name "Publisher" -Value "Pratham Agarwal"
Set-ItemProperty $uninstallKey -Name "InstallLocation" -Value $installDir
Set-ItemProperty $uninstallKey -Name "UninstallString" -Value "powershell -NoProfile -ExecutionPolicy Bypass -File `"${PSScriptRoot}\install.ps1`" -Uninstall"
Set-ItemProperty $uninstallKey -Name "InstallDate" -Value (Get-Date -Format "yyyyMMdd")
Set-ItemProperty $uninstallKey -Name "NoModify" -Value 1
Set-ItemProperty $uninstallKey -Name "NoRepair" -Value 1

if ($Startup) {
    $key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    Set-ItemProperty $key -Name $appName -Value "`"$exe`""
    Write-Host "Run-at-login enabled for the current user."
}

Write-Host "Aegis v$version installed to $exe"
Write-Host "Run it now by opening: $exe"