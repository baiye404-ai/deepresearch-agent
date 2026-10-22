"""Redis 连接工厂 —— 统一入口 + 无 Redis 时的内存降级。

设计说明：
  本机/开发环境常常没有 Redis 服务。此模块在 ``REDIS_URL`` 指向 localhost
  （或 127.0.0.1）且连不上真实 Redis 时，自动降级为进程内 fake Redis，
  使登录（会话存储）和任务队列仍可运行。

  降级只发生在"本机地址连不上"这一种情况：
    - 真实 Redis 可用        → 始终使用真实 Redis
    - 远端地址连不上          → 报错，不静默降级（避免线上掩盖故障）
    - 可通过 REDIS_ALLOW_FAKE=0 关闭降级行为

  内存模式下重启即丢数据（会话、任务队列、事件流都在内存里）。
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

import redis.asyncio as aioredis
from loguru import logger

DEFAULT_REDIS_URL = "redis://localhost:6379/0"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

_shared_client: object | None = None
_backend_kind: str | None = None


def get_redis_url() -> str:
    """读取 REDIS_URL（默认 localhost:6379/0）."""
    return os.getenv("REDIS_URL", DEFAULT_REDIS_URL)


def _fake_allowed() -> bool:
    """是否允许降级为内存 Redis（默认允许，REDIS_ALLOW_FAKE=0 可关闭）."""
    return os.getenv("REDIS_ALLOW_FAKE", "1").strip().lower() not in {"0", "false", "no"}


def _is_local_url(url: str) -> bool:
    """URL 是否指向本机（只有本机地址才允许降级）."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host in _LOCAL_HOSTS


def _make_fake_redis() -> object:
    """创建进程内 fake Redis；fakeredis 不可用时抛 ImportError."""
    import fakeredis.aioredis as fake_aioredis

    logger.warning(
        "[Redis] 未检测到本机 Redis，已降级为内存 fake Redis（重启即丢数据）。"
        "如需持久化请在 {} 启动真实 Redis，或设置 REDIS_ALLOW_FAKE=0 关闭降级。",
        get_redis_url(),
    )
    return fake_aioredis.FakeRedis(decode_responses=True)


async def _probe(client: object) -> None:
    """探活，确认客户端真的能用."""
    await client.ping()  # type: ignore[attr-defined]


async def _close_quietly(client: object) -> None:
    """尽力关闭一个连接（探活失败时清理用）."""
    try:
        closer = getattr(client, "aclose", None) or getattr(client, "close", None)
        if closer is not None:
            result = closer()
            if hasattr(result, "__await__"):
                await result
    except Exception:
        pass


async def get_redis() -> object:
    """获取共享的 Redis 客户端（首次调用时确定真实/内存后端）."""
    global _shared_client, _backend_kind

    if _shared_client is not None:
        return _shared_client

    url = get_redis_url()
    # socket_timeout=None：任务队列用 XREADGROUP BLOCK 5000ms 阻塞读，
    # redis-py 默认 5s 的 socket 读超时会先于阻塞结束触发，导致
    # "Timeout reading from ..." 反复报错。阻塞时长应由 block 参数控制。
    client = aioredis.from_url(url, decode_responses=True, socket_timeout=None)
    try:
        await _probe(client)
        _shared_client, _backend_kind = client, "redis"
        logger.info("[Redis] 已连接真实 Redis: {}", url)
        return _shared_client
    except Exception as conn_exc:  # 连不上
        await _close_quietly(client)
        if not (_is_local_url(url) and _fake_allowed()):
            logger.error(
                "[Redis] 连接失败且不允许降级（url={}, 原因={}: {}）",
                url,
                type(conn_exc).__name__,
                conn_exc,
            )
            raise
        logger.warning(
            "[Redis] 连接 {} 失败（{}: {}），降级为内存 Redis",
            url,
            type(conn_exc).__name__,
            conn_exc,
        )

    fake = _make_fake_redis()
    await _probe(fake)
    _shared_client, _backend_kind = fake, "fakeredis"
    return _shared_client


async def reset_redis() -> None:
    """丢弃缓存的客户端（测试或切换配置时使用）."""
    global _shared_client, _backend_kind
    if _shared_client is not None:
        await _close_quietly(_shared_client)
    _shared_client, _backend_kind = None, None


def redis_backend_kind() -> str | None:
    """当前后端类型：'redis' / 'fakeredis' / None（尚未初始化）."""
    return _backend_kind
