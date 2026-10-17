$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.runtime\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw '请先运行 scripts/setup.ps1 创建独立 Python 环境。' }
& $python -X utf8 (Join-Path $PSScriptRoot 'workflow.py') @args
exit $LASTEXITCODE
