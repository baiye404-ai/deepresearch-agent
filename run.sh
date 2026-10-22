#!/usr/bin/env bash
# 本地开发：环境变量与依赖安装脚本
#
# ⚠️ 本文件不得包含任何真实密钥。
# 请先在 shell 中导出变量（或写入 backend/.env，该文件已被 .gitignore 忽略）：
#   APP_TOKEN           LLM 服务 API Key（必需）
#   LLM_BASE_URL        OpenAI 兼容端点（可选，默认 DashScope）
#   MCP_APP_ID          MCP 工具应用 ID（可选）
#   LANGSMITH_API_KEY   LangSmith 追踪（可选）
#
# 用法：
#   export APP_TOKEN=sk-xxxxxxxx
#   ./run.sh

set -euo pipefail

: "${APP_TOKEN:?请先 export APP_TOKEN（不要把密钥写进本文件）}"
export LLM_BASE_URL="${LLM_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
export MCP_APP_ID="${MCP_APP_ID:-}"
export LANGSMITH_API_KEY="${LANGSMITH_API_KEY:-}"

cd backend
pip install .
cd ..

cd frontend
npm install
cd ..

make dev
