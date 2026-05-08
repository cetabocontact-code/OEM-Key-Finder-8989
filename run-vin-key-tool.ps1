param(
  [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
  [string[]] $VinArgs
)

$ErrorActionPreference = "Stop"

$bundledPython = "C:\Users\rawes\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$scriptPath = Join-Path $PSScriptRoot "vin_key_tool.py"

if (Test-Path -LiteralPath $bundledPython) {
  & $bundledPython $scriptPath @VinArgs
  exit $LASTEXITCODE
}

$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
  & $python.Source $scriptPath @VinArgs
  exit $LASTEXITCODE
}

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
  & $py.Source $scriptPath @VinArgs
  exit $LASTEXITCODE
}

Write-Error "Python was not found. Install Python or use the bundled Codex runtime."
