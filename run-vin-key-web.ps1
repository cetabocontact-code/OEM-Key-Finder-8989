param(
  [string] $HostName = "127.0.0.1",
  [int] $Port = 8989
)

$ErrorActionPreference = "Stop"

$bundledPython = "C:\Users\rawes\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$scriptPath = Join-Path $PSScriptRoot "web_app.py"

if (Test-Path -LiteralPath $bundledPython) {
  & $bundledPython $scriptPath --host $HostName --port $Port
  exit $LASTEXITCODE
}

$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
  & $python.Source $scriptPath --host $HostName --port $Port
  exit $LASTEXITCODE
}

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
  & $py.Source $scriptPath --host $HostName --port $Port
  exit $LASTEXITCODE
}

Write-Error "Python was not found. Install Python or use the bundled Codex runtime."
