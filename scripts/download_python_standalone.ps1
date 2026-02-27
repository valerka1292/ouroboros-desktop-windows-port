$ErrorActionPreference = "Stop"

$RELEASE = "20260211"
$PY_VERSION = "3.10.19"
$DEST = "python-standalone"

$PLATFORM = "x86_64-pc-windows-msvc-shared"
$FILENAME = "cpython-${PY_VERSION}+${RELEASE}-${PLATFORM}-install_only.tar.gz"
$URL = "https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE}/${FILENAME}"

Write-Host "=== Downloading Python ${PY_VERSION} for ${PLATFORM} ==="
Write-Host "URL: ${URL}"

if (Test-Path $DEST) { Remove-Item -Recurse -Force $DEST }
if (Test-Path "_python_tmp") { Remove-Item -Recurse -Force "_python_tmp" }
New-Item -ItemType Directory -Force -Path "_python_tmp" | Out-Null

$OutFile = "_python_tmp\$FILENAME"
Invoke-WebRequest -Uri $URL -OutFile $OutFile

Write-Host "Extracting..."
tar -xzf $OutFile -C _python_tmp

Move-Item -Path "_python_tmp\python" -Destination $DEST
Remove-Item -Recurse -Force "_python_tmp"

Write-Host "`n=== Installing agent dependencies ==="
& "$DEST\python.exe" -m pip install --quiet -r requirements.txt

Write-Host "`n=== Done ==="
Write-Host "Python: $DEST\python.exe"
& "$DEST\python.exe" --version
