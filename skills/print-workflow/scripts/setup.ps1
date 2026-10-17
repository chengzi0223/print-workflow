param([string]$PythonExecutable = 'python')
$ErrorActionPreference = 'Stop'
# 安装只准备工作流依赖；不安装建模软件或修改用户已有配置。
$runtime = Join-Path $PSScriptRoot '.runtime'
$python = Join-Path $runtime 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    if (Test-Path -LiteralPath $runtime) { throw '存在不完整的 .runtime，请先检查该目录；安装器不会自动删除。' }
    & $PythonExecutable -m venv $runtime
    if ($LASTEXITCODE -ne 0) { throw 'Python 环境创建失败，请使用真实的 Python 3.11+ 路径。' }
}
& $python -m pip install -r (Join-Path $PSScriptRoot 'requirements-lock.txt')
if ($LASTEXITCODE -ne 0) { throw '依赖安装失败。' }
$config = Join-Path $PSScriptRoot 'config.json'
if (-not (Test-Path -LiteralPath $config)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'config.example.json') -Destination $config
}
Write-Output '依赖已准备。请编辑 scripts/config.json，填写实际软件路径，再运行 工作流.ps1 doctor。'
