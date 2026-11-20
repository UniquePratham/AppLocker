# Build the AppLocker Inno Setup installer.
#
# Produces release\AppLockerSetup-<version>.exe from release\AppLocker.exe
# (run build.ps1 first to produce the EXE).
#
# Usage:
#   .\installer\build_installer.ps1                # default version 2.0.0
#   .\installer\build_installer.ps1 -Version 2.1.0

[cmdletbinding()]
param(
    [string]$Version = "2.0.0"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    if (!(Test-Path -LiteralPath "release\AppLocker.exe")) {
        throw "release\AppLocker.exe not found. Run build.ps1 first."
    }

    $iscc = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $iscc) {
        $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        if ($cmd) { $iscc = $cmd.Source }
    }
    if (-not $iscc) {
        throw "ISCC.exe (Inno Setup 6) not found. Install Inno Setup 6 and retry."
    }

    Write-Host "== Inno Setup compile (AppLocker $Version) =="
    & $iscc "/DMyAppVersion=$Version" "installer\AppLocker.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compile failed (exit $LASTEXITCODE)" }

    $out = Get-Item "release\AppLockerSetup-$Version.exe"
    $size = [math]::Round($out.Length / 1MB, 2)
    Write-Host "Installer built: $($out.FullName) ($size MB)"
}
finally {
    Pop-Location
}