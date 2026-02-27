$ErrorActionPreference = "Stop"

Write-Host "=== Building Ouroboros.exe ==="

$PythonPath = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonPath) {
    Write-Error "ERROR: python not found in PATH."
    exit 1
}
Write-Host "Found Python at: $($PythonPath.Source)"

Write-Host "--- Bundling Conda environment ---"
$CondaEnvPath = (python -c "import sys; print(sys.prefix)").Trim()
if (Test-Path "python-standalone") { Remove-Item -Recurse -Force "python-standalone" }
Write-Host "Copying from: $CondaEnvPath"
Copy-Item -Path $CondaEnvPath -Destination "python-standalone" -Recurse

Write-Host "--- Installing launcher dependencies ---"
python -m pip install -q pyinstaller
python -m pip install -q -r requirements-launcher.txt

Write-Host "--- Installing agent dependencies into bundled Python ---"
& "python-standalone\python.exe" -m pip install -q -r requirements.txt

if (Test-Path "build") { Rename-Item -Path "build" -NewName "build_old" -ErrorAction SilentlyContinue; Remove-Item -Recurse -Force "build_old" -ErrorAction SilentlyContinue }
if (Test-Path "dist") { Rename-Item -Path "dist" -NewName "dist_old" -ErrorAction SilentlyContinue; Remove-Item -Recurse -Force "dist_old" -ErrorAction SilentlyContinue }

Write-Host "--- Running PyInstaller ---"
python -m PyInstaller Ouroboros.spec --clean --noconfirm

Write-Host ""
Write-Host "=== Done ==="
Write-Host "Executable built to dist/Ouroboros"
