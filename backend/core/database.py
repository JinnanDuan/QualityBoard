# ============================================================
# 数据库连接层 — 负责创建数据库引擎和会话工厂
# ============================================================
# 在 Web 应用中，每个用户请求需要一个独立的"数据库会话"(session)来执行 SQL，
# 请求结束后会话自动关闭。这个文件就是用来管理这些会话的。
# ============================================================

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

# SQLAlchemy 是 Python 最流行的 ORM(对象关系映射)库。
# "async" 前缀表示异步版本 — 不会阻塞其他请求，性能更好。
# - AsyncSession:    异步数据库会话，用它来执行查询
# - async_sessionmaker: 会话工厂，每次调用都会创建一个新的 AsyncSession
# - create_async_engine: 创建异步数据库引擎（底层连接池）
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 从项目配置模块中导入 settings 对象（里面包含 DATABASE_URL 等配置项，读取自 .env 文件）
from backend.core.config import settings

# 创建异步数据库引擎 — 这是整个应用与 MySQL 通信的"桥梁"
# - settings.DATABASE_URL: 数据库连接字符串，格式如 mysql+aiomysql://user:password@host:port/dbname
# - echo:                 False，SQL 由下方事件统一输出（含耗时），便于与 echo 的格式区分
# - pool_pre_ping=True:   每次从连接池取连接前先 ping 一下数据库，避免拿到已断开的连接
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

logger = logging.getLogger(__name__)
logger.info("数据库引擎已创建 LOG_SQL=%s", settings.LOG_SQL)

# 当 LOG_SQL 开启时，注册事件：将 SQL 与查询耗时合并到同一行输出
if settings.LOG_SQL:
    _sql_logger = logging.getLogger("sqlalchemy.engine.Engine")

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ARG001
        conn.info["_query_start"] = time.perf_counter()
        conn.info["_query_statement"] = statement

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ARG001
        start = conn.info.pop("_query_start", None)
        stmt = conn.info.pop("_query_statement", statement)
        if start is not None:
            duration_ms = (time.perf_counter() - start) * 1000
            compact = " ".join(stmt.split())
            params_str = "" if parameters is None else " %r" % (parameters,)
            _sql_logger.info("%s [query took %.1fms]%s", compact, duration_ms, params_str)

# 创建会话工厂 — 之后每次需要数据库会话时，调用 async_session_factory() 即可得到一个新的 AsyncSession
# - class_=AsyncSession:      指定工厂生产的会话类型
# - expire_on_commit=False:   提交事务后不自动让已加载的对象过期（避免提交后再访问字段时触发额外查询）
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def async_session_on_pinned_connection() -> AsyncIterator[AsyncSession]:
    """
    在单条池连接上创建 AsyncSession，直至上下文结束再归还连接。

    普通 get_db 会话在 commit() 后可能把连接放回池并改用另一条连接执行后续 SQL；
    而 MySQL GET_LOCK / RELEASE_LOCK 必须发生在**同一连接**上，否则 RELEASE 无效、
    锁会随旧连接滞留在池中，导致后续同名的 GET_LOCK 长时间阻塞直至超时。
    """
    async with engine.connect() as conn:
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()


# 这是 FastAPI 的"依赖注入"函数 — 后面 API 层会通过 Depends(get_db) 来自动调用它
# 它是一个异步生成器（async generator），用 yield 而非 return：
#   1. 请求进来时 → 创建一个数据库会话并交给 API 函数使用
#   2. API 函数执行完毕 → yield 之后的代码执行（这里由 async with 自动关闭会话）
# 这样可以保证：每个请求有独立的会话，请求结束后会话必定被关闭，不会泄漏连接。
async def get_db() -> AsyncSession:  # type: ignore[misc]
    try:
        async with async_session_factory() as session:
            yield session
    except Exception as e:
        logger.exception("数据库会话异常: %s", e)
        raise
