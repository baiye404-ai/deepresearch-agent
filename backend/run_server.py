"""本地部署入口：强制使用 Selector 事件循环启动 FastAPI 应用。

为什么需要这个文件（而不是直接 `uvicorn agent.app:app`）：
  Windows 上 asyncio 默认使用 ProactorEventLoop，而 psycopg 的异步模式明确
  不支持它：
      "Psycopg cannot use the 'ProactorEventLoop' to run in async mode."
  本项目的 LangGraph checkpoint 使用 PostgreSQL（AsyncPostgresSaver + psycopg），
  因此必须在 SelectorEventLoop 下运行。

  实现方式：uvicorn 通过 `uvicorn.loops.asyncio:asyncio_loop_factory` 这个
  字符串在运行时动态解析事件循环工厂（见 uvicorn Config.get_loop_factory），
  因此必须替换 `uvicorn.Config.get_loop_factory` 的返回值，而不是改
  `asyncio.set_event_loop_policy`（会被 uvicorn 覆盖）。

副作用：Selector 循环在 Windows 上不支持 asyncio 子进程（create_subprocess_*）。
本项目不使用 asyncio 子进程，因此无影响。

用法：
    python run_server.py
环境变量：
    APP_HOST（默认 127.0.0.1）、APP_PORT（默认 2024）、APP_RELOAD（默认 0）
"""
from __future__ import annotations

import asyncio
import os
import sys


def _force_selector_loop_in_uvicorn() -> None:
    """让 uvicorn 用 SelectorEventLoop（psycopg 异步模式的要求）."""
    if sys.platform != "win32":
        return

    import uvicorn

    def get_selector_loop_factory(self):  # noqa: ANN001, ARG001
        return asyncio.SelectorEventLoop

    uvicorn.Config.get_loop_factory = get_selector_loop_factory


def main() -> None:
    _force_selector_loop_in_uvicorn()

    import uvicorn

    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "2024"))
    reload_enabled = os.getenv("APP_RELOAD", "0") == "1"

    uvicorn.run(
        "agent.app:app",
        host=host,
        port=port,
        reload=reload_enabled,
        loop="asyncio",
    )


if __name__ == "__main__":
    main()
