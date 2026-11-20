# Build and package AppLocker with PyInstaller.
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    Remove-Item -Recurse -Force "build", "dist", "release\AppLocker.exe", "release\*.sha256" -ErrorAction SilentlyContinue

    Write-Host "== PyInstaller build (one-file, windowed) =="
    # PyInstaller logs INFO to stderr; under $ErrorActionPreference="Stop" that
    # terminates the script in Windows PowerShell 5.1, so temporarily relax it.
    $ErrorActionPreference = "Continue"
    python -m PyInstaller --noconfirm --clean AppLocker.spec 2>&1 | Out-Host
    $ErrorActionPreference = "Stop"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

    New-Item -ItemType Directory -Force -Path "release" | Out-Null
    Copy-Item "dist\AppLocker.exe" "release\AppLocker.exe" -Force

    Write-Host "== Checksums =="
    $hash = (Get-FileHash "release\AppLocker.exe" -Algorithm SHA256).Hash
    $size = (Get-Item "release\AppLocker.exe").Length
    "AppLocker.exe  $hash  sha256" | Set-Content "release\AppLocker.exe.sha256"
    Write-Host "SHA256: $hash"
    Write-Host "Size:   $([math]::Round($size / 1MB, 2)) MB"

    Write-Host "== Done =="
}
finally {
    Pop-Location
}