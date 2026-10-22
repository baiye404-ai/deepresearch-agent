"""本地调试脚本：直接调一次 Agent，验证密钥与联通性。

密钥一律通过环境变量注入，**不要硬编码到本文件**。

用法（在 backend 目录下）：
    # Windows cmd
    set APP_TOKEN=sk-xxxx
    python -m test.test_agent

    # bash
    export APP_TOKEN=sk-xxxx
    python -m test.test_agent
"""

import os

# 占位空值：真实值请通过环境变量提供（写入仓库会被视为密钥泄露）
os.environ.setdefault("APP_TOKEN", "")
os.environ.setdefault(
    "LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
os.environ.setdefault("APP_ID", "")
os.environ.setdefault("GEMINI_API_KEY", "")

from agent.base_agent import *  # noqa: E402,F403

if __name__ == "__main__":
    if not os.environ.get("APP_TOKEN"):
        raise SystemExit("请先设置环境变量 APP_TOKEN（不要写进代码）")

    agent = Agent()
    response = agent("中国的首都是哪里？")
    print(response)
