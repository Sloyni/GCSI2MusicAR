$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    $taskBundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $taskBundledPython) {
        & $taskBundledPython -m venv .venv
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -m venv .venv
    } else {
        & python -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 ou 3.12 est requis. Installez Python 3.12 puis relancez ce script.' }
}
& $taskPython -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Installation des dependances interrompue. Relancez Installer.ps1.' }
& $taskPython scripts/download_assets.py
if ($LASTEXITCODE -ne 0) { throw 'Telechargement interrompu. Verifiez Internet puis relancez Installer.ps1.' }
Write-Host 'MusicAR est pret. Double-cliquez sur Demarrer.cmd.' -ForegroundColor Green

