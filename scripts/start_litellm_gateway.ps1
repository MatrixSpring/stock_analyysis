# ============================================================
# LiteLLM 本地网关启动脚本 (Windows PowerShell)
# 用途：启动 LiteLLM 代理网关，统一接入豆包 + DeepSeek
#
# 使用方法：
#   1. 先配置 .env 中的 ARK_API_KEY 和 DEEPSEEK_API_KEY
#   2. powershell -ExecutionPolicy Bypass -File scripts/start_litellm_gateway.ps1
#
# 网关地址：http://localhost:4000
# API Key： sk-litellm-local
# ============================================================

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# 检查环境变量
if (-not $env:ARK_API_KEY) {
    Write-Host "⚠️  警告: ARK_API_KEY 未设置，豆包模型将不可用" -ForegroundColor Yellow
    Write-Host "   请在 .env 中设置: ARK_API_KEY=你的火山引擎API Key"
}

if (-not $env:DEEPSEEK_API_KEY) {
    Write-Host "⚠️  警告: DEEPSEEK_API_KEY 未设置，DeepSeek 备用模型将不可用" -ForegroundColor Yellow
    Write-Host "   请在 .env 中设置: DEEPSEEK_API_KEY=你的DeepSeek API Key"
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  启动 LiteLLM 本地协议转换网关" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  主模型: 豆包 Doubao (ARK)"
Write-Host "  备用:   DeepSeek"
Write-Host "  端口:   4000"
Write-Host "  API:    http://localhost:4000"
Write-Host "  Key:    sk-litellm-local"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $ProjectRoot

# 启动 LiteLLM 网关
litellm --config litellm_config.yaml --port 4000
