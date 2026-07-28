#!/usr/bin/env bash
# ============================================================
# LiteLLM 本地网关启动脚本
# 用途：启动 LiteLLM 代理网关，统一接入豆包 + DeepSeek
#
# 使用方法：
#   1. 先配置 .env 中的 ARK_API_KEY 和 DEEPSEEK_API_KEY
#   2. source .env && bash scripts/start_litellm_gateway.sh
#
# 网关地址：http://localhost:4000
# API Key： sk-litellm-local（可修改 litellm_config.yaml 中 master_key）
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 检查环境变量
if [ -z "${ARK_API_KEY:-}" ]; then
    echo "⚠️  警告: ARK_API_KEY 未设置，豆包模型将不可用"
    echo "   请在 .env 中设置: ARK_API_KEY=你的火山引擎API Key"
fi

if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
    echo "⚠️  警告: DEEPSEEK_API_KEY 未设置，DeepSeek 备用模型将不可用"
    echo "   请在 .env 中设置: DEEPSEEK_API_KEY=你的DeepSeek API Key"
fi

echo "=========================================="
echo "  启动 LiteLLM 本地协议转换网关"
echo "=========================================="
echo "  主模型: 豆包 Doubao (ARK)"
echo "  备用:   DeepSeek"
echo "  端口:   4000"
echo "  API:    http://localhost:4000"
echo "  Key:    sk-litellm-local"
echo "=========================================="
echo ""

cd "$PROJECT_ROOT"

# 启动 LiteLLM 网关
exec litellm --config litellm_config.yaml --port 4000
