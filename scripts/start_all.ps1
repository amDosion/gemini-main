param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ArgsFromCli
)

$RootDir = Split-Path -Path $PSScriptRoot -Parent
Set-Location $RootDir

if (Get-Command py -ErrorAction SilentlyContinue) {
  py scripts/start_all.py @ArgsFromCli
  exit $LASTEXITCODE
}

if (Get-Command python -ErrorAction SilentlyContinue) {
  python scripts/start_all.py @ArgsFromCli
  exit $LASTEXITCODE
}

Write-Error "python/py not found in PATH"
exit 1
