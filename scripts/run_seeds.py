#!/usr/bin/env python3
"""
执行 database/ 下的种子数据 SQL 文件。
从 .env 读取 DATABASE_URL，按依赖顺序执行。
"""
import asyncio
import sys
from pathlib import Path

# 确保 backend 在路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.config import settings
import aiomysql


def parse_database_url(url: str) -> dict:
    """解析 mysql+aiomysql://user:pass@host:port/db?charset=utf8mb4"""
    from urllib.parse import urlparse
    parsed = urlparse(url.replace("mysql+aiomysql://", "mysql://"))
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 3306,
        "user": parsed.username or "root",
        "password": parsed.password or "",
        "db": (parsed.path or "/dt_infra").lstrip("/").split("?")[0] or "dt_infra",
        "charset": "utf8mb4",
    }


def split_sql_statements(sql: str):
    """按分号分割 SQL 语句，跳过注释。"""
    statements = []
    current = []
    for line in sql.split("\n"):
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        current.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(current).rstrip(";").strip()
            if stmt:
                statements.append(stmt)
            current = []
    if current:
        stmt = "\n".join(current).strip()
        if stmt:
            statements.append(stmt)
    return statements


async def main():
    url = settings.DATABASE_URL
    if not url:
        print("错误: 未设置 DATABASE_URL")
        return 1

    cfg = parse_database_url(url)
    root = Path(__file__).resolve().parent.parent
    seeds = [
        root / "database" / "seed_ums_email.sql",
        root / "database" / "seed_case_failed_type.sql",
        root / "database" / "seed_ums_module_owner.sql",
        root / "database" / "seed_pipeline_history.sql",
        root / "database" / "seed_pipeline_failure_reason.sql",
    ]

    conn = await aiomysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        db=cfg["db"],
        charset=cfg["charset"],
    )

    try:
        async with conn.cursor() as cur:
            for fp in seeds:
                if not fp.exists():
                    print(f"跳过（不存在）: {fp.name}")
                    continue
                print(f"执行: {fp.name} ...", end=" ", flush=True)
                try:
                    sql = fp.read_text(encoding="utf-8")
                    for stmt in split_sql_statements(sql):
                        await cur.execute(stmt)
                    await conn.commit()
                    print("OK")
                except Exception as e:
                    print(f"失败: {e}")
                    raise
    finally:
        conn.close()

    print("全部种子数据执行完成。")
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
