"""本地轻量启动辅助：SQLite 建表 + 初始用户写入。

背景：项目默认使用 PostgreSQL（``DATABASE_URL=postgresql+asyncpg://...``）。
本机没有 Postgres 时，可把 ``DATABASE_URL`` 切到 SQLite
（``sqlite+aiosqlite:///<绝对路径>``），由本模块在应用启动时自动建表并写入
初始用户，免去手工执行 ``python -m agent.db.init_db``。

非 SQLite（例如 Postgres）时不产生任何副作用，仍按原流程手工初始化。
"""
from __future__ import annotations

from urllib.parse import urlparse

import bcrypt as _bcrypt
from loguru import logger
from sqlalchemy import select

from agent.db.engine import DATABASE_URL, get_engine, get_session_factory
from agent.db.models import Base, User

# 与 agent/db/init_db.py 的 INITIAL_USERS 保持一致（本地开发默认账号）
INITIAL_USERS = [
    {"username": "zhangsan", "password": "zhangsan"},
    {"username": "lisi", "password": "lisi"},
]

_setup_done = False


def _hash_password(plain: str) -> str:
    """对明文密码进行 bcrypt 哈希."""
    return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def is_sqlite() -> bool:
    """当前 DATABASE_URL 是否指向 SQLite."""
    return DATABASE_URL.startswith("sqlite")


def sqlite_file_path() -> str:
    """从 DATABASE_URL 提取 SQLite 文件路径（相对路径按当前工作目录解析）."""
    url = DATABASE_URL.split("///", 1)[-1]
    return urlparse(f"sqlite:///{url}").path or url


async def setup_sqlite_if_needed() -> None:
    """SQLite 模式下建表 + 幂等写入初始用户；非 SQLite 直接返回."""
    global _setup_done

    if _setup_done or not is_sqlite():
        return

    engine = get_engine()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("[Bootstrap] SQLite 表已就绪: {}", sqlite_file_path())

    async with get_session_factory()() as session:
        for item in INITIAL_USERS:
            existing = await session.execute(
                select(User).where(User.username == item["username"])
            )
            if existing.scalar_one_or_none() is None:
                session.add(
                    User(
                        username=item["username"],
                        password=_hash_password(item["password"]),
                    )
                )
                logger.info("[Bootstrap] 已创建初始用户 {}（密码同用户名）", item["username"])
        await session.commit()

    _setup_done = True
