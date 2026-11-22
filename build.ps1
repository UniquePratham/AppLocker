# Build and package Aegis with PyInstaller.
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    Remove-Item -Recurse -Force "build", "dist", "release\Aegis.exe", "release\*.sha256" -ErrorAction SilentlyContinue

    Write-Host "== Regenerating brand assets =="
    python -c "import sys; sys.path.insert(0,'.'); from applocker.util.brand import build_assets; build_assets()"
    if ($LASTEXITCODE -ne 0) { throw "Asset generation failed" }

    Write-Host "== PyInstaller build (one-file, windowed) =="
    # PyInstaller logs INFO to stderr; under $ErrorActionPreference="Stop" that
    # terminates the script in Windows PowerShell 5.1, so temporarily relax it.
    $ErrorActionPreference = "Continue"
    python -m PyInstaller --noconfirm --clean AppLocker.spec 2>&1 | Out-Host
    $ErrorActionPreference = "Stop"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

    New-Item -ItemType Directory -Force -Path "release" | Out-Null
    Copy-Item "dist\Aegis.exe" "release\Aegis.exe" -Force

    Write-Host "== Checksums =="
    $hash = (Get-FileHash "release\Aegis.exe" -Algorithm SHA256).Hash
    $size = (Get-Item "release\Aegis.exe").Length
    "Aegis.exe  $hash  sha256" | Set-Content "release\Aegis.exe.sha256"
    Write-Host "SHA256: $hash"
    Write-Host "Size:   $([math]::Round($size / 1MB, 2)) MB"

    Write-Host "== Done =="
}
finally {
    Pop-Location
}