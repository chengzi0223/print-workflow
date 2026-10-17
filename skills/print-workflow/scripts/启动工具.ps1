param([ValidateSet('fusion','blender','bambu')][string]$Tool = 'fusion')
$ErrorActionPreference = 'Stop'
$configPath = Join-Path $PSScriptRoot 'config.json'
if (-not (Test-Path -LiteralPath $configPath)) { throw '请先运行 setup.ps1 并填写 config.json。' }
$config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
function Require-File([string]$Path, [string]$Key) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "请核对 config.json 中的 $Key 路径。" }
}
# 启动只恢复应用连接；模型仍需经过效果图和实际模型确认。
switch ($Tool) {
    'fusion' {
        if (-not (Get-Process -Name Fusion360 -ErrorAction SilentlyContinue)) {
            Require-File $config.fusion_launcher 'fusion_launcher'
            Start-Process -FilePath $config.fusion_launcher -WindowStyle Hidden
        }
        Write-Output 'Fusion 已运行或已请求启动，随后通过 MCP 验证响应。'
    }
    'blender' {
        if (Get-NetTCPConnection -LocalPort 9876 -State Listen -ErrorAction SilentlyContinue) {
            Write-Output 'Blender 端口已监听，请通过 MCP 验证场景。'
        } elseif (Get-Process -Name blender -ErrorAction SilentlyContinue) {
            throw 'Blender 已打开；请在当前实例启动 MCP 插件，避免替换未保存场景。'
        } else {
            Require-File $config.blender_exe 'blender_exe'
            if ($config.blender_start_script) {
                Require-File $config.blender_start_script 'blender_start_script'
                Start-Process -FilePath $config.blender_exe -ArgumentList '--python',('"' + $config.blender_start_script + '"') -WindowStyle Hidden
            } else {
                Start-Process -FilePath $config.blender_exe
            }
            Write-Output '已请求启动 Blender，核对插件并通过 MCP 验证响应。'
        }
    }
    'bambu' {
        if (-not (Get-Process -Name bambu-studio -ErrorAction SilentlyContinue)) {
            Require-File $config.bambu_exe 'bambu_exe'
            Start-Process -FilePath $config.bambu_exe
        }
        Write-Output 'Bambu 已运行或已请求启动。导入确认模型请使用 open-bambu。'
    }
}
