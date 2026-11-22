# Build the Aegis Inno Setup installer.
#
# Produces release\AegisSetup-<version>.exe from release\Aegis.exe
# (run build.ps1 first to produce the EXE).
#
# Usage:
#   .\installer\build_installer.ps1                # default version 2.1.0
#   .\installer\build_installer.ps1 -Version 2.1.0

[cmdletbinding()]
param(
    [string]$Version = "2.1.0"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    if (!(Test-Path -LiteralPath "release\Aegis.exe")) {
        throw "release\Aegis.exe not found. Run build.ps1 first."
    }
    if (!(Test-Path -LiteralPath "applocker\assets\aegis.ico")) {
        throw "applocker\assets\aegis.ico not found. Run build.ps1 to regenerate assets."
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

    Write-Host "== Inno Setup compile (Aegis $Version) =="
    & $iscc "/DMyAppVersion=$Version" "installer\AppLocker.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compile failed (exit $LASTEXITCODE)" }

    $out = Get-Item "release\AegisSetup-$Version.exe"
    $size = [math]::Round($out.Length / 1MB, 2)
    Write-Host "Installer built: $($out.FullName) ($size MB)"
}
finally {
    Pop-Location
}