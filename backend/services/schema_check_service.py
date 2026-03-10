"""数据库表结构一致性校验服务。

在系统启动时校验 database/ 下 DDL 文件与数据库实际结构是否一致。
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.core.config import settings

logger = logging.getLogger(__name__)

# 表名 -> DDL 文件名映射（spec 第 9 节）
TABLE_DDL_MAP = {
    "pipeline_overview": "V1.0.2__create_pipeline_overview.sql",
    "pipeline_history": "V1.0.1__create_pipeline_history.sql",
    "pipeline_failure_reason": "V1.0.3__create_pipeline_failure_reason.sql",
    "pipeline_cases": "V1.0.4__create_pipeline_cases.sql",
    "ums_email": "V1.0.5__create_ums_email.sql",
    "ums_module_owner": "V1.0.6__create_ums_module_owner.sql",
    "case_failed_type": "V1.0.7__create_case_failed_type.sql",
    "case_offline_type": "V1.0.8__create_case_offline_type.sql",
    "sys_audit_log": "V1.0.9__create_sys_audit_log.sql",
    "report_snapshot": "V1.1.0__create_report_snapshot.sql",
}

TABLE_RE = re.compile(r"CREATE\s+TABLE\s+`([^`]+)`\s*\(", re.IGNORECASE)
COL_RE = re.compile(r"^\s*`([^`]+)`\s+(\S+)(.*)$", re.IGNORECASE | re.MULTILINE)
PRIMARY_KEY_RE = re.compile(r"PRIMARY\s+KEY\s*\(([^)]+)\)", re.IGNORECASE)
KEY_RE = re.compile(r"(?:UNIQUE\s+)?KEY\s+`([^`]+)`\s*\(([^)]+)\)", re.IGNORECASE)
COL_LIST_RE = re.compile(r"`([^`]+)`")


def _normalize_default(rest: str) -> Optional[str]:
    """从字段定义 rest 部分解析并归一化默认值。"""
    rest_upper = rest.upper()
    if "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP" in rest_upper:
        return "CURRENT_TIMESTAMP ON UPDATE"
    if "DEFAULT CURRENT_TIMESTAMP" in rest_upper:
        return "CURRENT_TIMESTAMP"
    default_match = re.search(r"DEFAULT\s+(.+?)(?:\s|$|COMMENT)", rest, re.IGNORECASE | re.DOTALL)
    if not default_match:
        return None
    val = default_match.group(1).strip().rstrip(",").strip()
    if re.match(r"^NULL$", val, re.IGNORECASE):
        return "NULL"
    if val in ("''", '""', "''"):
        return "''"
    if re.match(r"^['\"]?0['\"]?$", val):
        return "0"
    if val.startswith("'") and val.endswith("'"):
        return val[1:-1] if len(val) > 2 else "''"
    return val


def _parse_ddl_file(path: Path) -> Dict[str, Any]:
    """解析单个 DDL 文件，提取表名、字段列表（含 default）、主键、索引。"""
    content = path.read_text(encoding="utf-8")
    table_match = TABLE_RE.search(content)
    if not table_match:
        raise ValueError("无法解析表名: %s" % path.name)
    table_name = table_match.group(1)

    columns = []
    primary_key = []
    indexes = []

    for line in content.split("\n"):
        stripped = line.strip()
        pk_match = PRIMARY_KEY_RE.search(stripped)
        if pk_match:
            primary_key = [m.group(1) for m in COL_LIST_RE.finditer(pk_match.group(1))]
            continue
        key_match = KEY_RE.search(stripped)
        if key_match and "CONSTRAINT" not in stripped.upper() and "FOREIGN" not in stripped.upper():
            idx_name = key_match.group(1)
            if idx_name.upper() != "PRIMARY":
                cols = [m.group(1) for m in COL_LIST_RE.finditer(key_match.group(2))]
                unique = stripped.upper().startswith("UNIQUE")
                indexes.append({"name": idx_name, "columns": cols, "unique": unique})
            continue
        col_match = COL_RE.match(stripped)
        if not col_match:
            continue
        col_name = col_match.group(1)
        col_type = col_match.group(2)
        rest = col_match.group(3)
        if col_name.upper().startswith(("PRIMARY", "KEY", "UNIQUE", "CONSTRAINT", "FOREIGN")):
            continue
        valid_types = ("int", "varchar", "datetime", "text", "tinyint", "bigint", "float", "double")
        if not col_type.lower().startswith(valid_types):
            continue
        nullable = "NOT NULL" not in rest.upper()
        default = _normalize_default(rest)
        columns.append({
            "name": col_name,
            "type": col_type,
            "nullable": nullable,
            "default": default,
        })
    return {
        "table": table_name,
        "columns": columns,
        "primary_key": primary_key,
        "indexes": indexes,
    }


def _normalize_column_type(mysql_type: str) -> str:
    """归一化 MySQL 类型用于比较。"""
    t = mysql_type.lower().strip()
    if t.startswith("int("):
        return "int"
    if t in ("tinyint(1)", "boolean"):
        return "tinyint(1)"
    return t


def _types_equivalent(ddl_type: str, actual_type: str) -> bool:
    """判断 DDL 类型与数据库实际类型是否等价。"""
    n_ddl = _normalize_column_type(ddl_type)
    n_actual = _normalize_column_type(actual_type)
    return n_ddl == n_actual


def _defaults_equivalent(exp_default: Optional[str], act_default: Optional[str]) -> bool:
    """判断默认值是否等价。"""
    def _norm(d: Optional[str]) -> Optional[str]:
        if d is None or (isinstance(d, str) and d.strip().upper() == "NULL"):
            return None
        return str(d).strip() if d else None
    return _norm(exp_default) == _norm(act_default)


def get_expected_schema(database_dir: Path) -> Dict[str, Dict[str, Any]]:
    """按表-DDL 映射读取 DDL 文件，返回期望结构。"""
    result = {}
    for table_name, ddl_file in TABLE_DDL_MAP.items():
        path = database_dir / ddl_file
        if not path.exists():
            raise FileNotFoundError("DDL 文件不存在: %s" % path)
        parsed = _parse_ddl_file(path)
        result[table_name] = {
            "columns": parsed["columns"],
            "primary_key": parsed["primary_key"],
            "indexes": parsed["indexes"],
        }
    return result


def _normalize_actual_default(col_default: Optional[str], extra: Optional[str]) -> Optional[str]:
    """归一化 MySQL 返回的 COLUMN_DEFAULT 和 EXTRA。"""
    has_on_update = extra and "on update current_timestamp" in (extra or "").lower()
    val = (col_default or "").strip()
    if val.startswith("'") and val.endswith("'"):
        val = val[1:-1]
    if has_on_update and (val.upper() == "CURRENT_TIMESTAMP" or val == ""):
        return "CURRENT_TIMESTAMP ON UPDATE"
    if col_default is None:
        return None
    if col_default == "" or val == "":
        return "''"
    if val.upper() == "NULL":
        return "NULL"
    if val.upper() == "CURRENT_TIMESTAMP":
        return "CURRENT_TIMESTAMP"
    if re.match(r"^['\"]?0['\"]?$", val):
        return "0"
    return col_default.strip()


async def get_actual_schema(engine: AsyncEngine, db_name: str) -> Dict[str, Dict[str, Any]]:
    """查询 information_schema 获取实际表结构。"""
    result = {}
    async with engine.connect() as conn:
        for table_name in TABLE_DDL_MAP.keys():
            col_rows = await conn.execute(
                text("""
                    SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = :db AND TABLE_NAME = :tbl
                    ORDER BY ORDINAL_POSITION
                """),
                {"db": db_name, "tbl": table_name},
            )
            columns = []
            for row in col_rows:
                default = _normalize_actual_default(row[3], row[4])
                columns.append({
                    "name": row[0],
                    "type": row[1],
                    "nullable": row[2] == "YES",
                    "default": default,
                })
            stat_rows = await conn.execute(
                text("""
                    SELECT INDEX_NAME, COLUMN_NAME, NON_UNIQUE
                    FROM information_schema.STATISTICS
                    WHERE TABLE_SCHEMA = :db AND TABLE_NAME = :tbl
                    ORDER BY INDEX_NAME, SEQ_IN_INDEX
                """),
                {"db": db_name, "tbl": table_name},
            )
            primary_key = []
            idx_map = {}
            for row in stat_rows:
                idx_name = row[0]
                if idx_name == "PRIMARY":
                    primary_key.append(row[1])
                else:
                    if idx_name not in idx_map:
                        idx_map[idx_name] = {"columns": [], "unique": row[2] == 0}
                    idx_map[idx_name]["columns"].append(row[1])
            indexes = [{"name": k, "columns": v["columns"], "unique": v["unique"]} for k, v in idx_map.items()]
            result[table_name] = {
                "columns": columns,
                "primary_key": primary_key,
                "indexes": indexes,
            }
    return result


def _parse_db_name_from_url(url: str) -> str:
    """从 DATABASE_URL 解析数据库名。"""
    from urllib.parse import urlparse, unquote
    parsed = urlparse(url)
    path = parsed.path or "/"
    db_part = path.split("?")[0].strip("/")
    return unquote(db_part) if db_part else ""


def compare_schemas(
    expected: Dict[str, Dict[str, Any]],
    actual: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """比较期望结构与实际结构，返回差异列表。"""
    diffs = []
    for table_name, exp_data in expected.items():
        if table_name not in actual:
            diffs.append({
                "type": "表缺失",
                "table": table_name,
                "field": None,
                "detail": "数据库中不存在该表",
            })
            continue
        act_data = actual[table_name]
        exp_cols = {c["name"]: c for c in exp_data["columns"]}
        act_cols = {c["name"]: c for c in act_data["columns"]}
        for col_name, exp_col in exp_cols.items():
            if col_name not in act_cols:
                diffs.append({
                    "type": "字段缺失",
                    "table": table_name,
                    "field": col_name,
                    "detail": "DDL 中定义但数据库中不存在",
                })
                continue
            act_col = act_cols[col_name]
            if not _types_equivalent(exp_col["type"], act_col["type"]):
                diffs.append({
                    "type": "类型不同",
                    "table": table_name,
                    "field": col_name,
                    "detail": "DDL=%s, 实际=%s" % (exp_col["type"], act_col["type"]),
                })
            if exp_col["nullable"] != act_col["nullable"]:
                ddl_null = "NULL" if exp_col["nullable"] else "NOT NULL"
                act_null = "NULL" if act_col["nullable"] else "NOT NULL"
                diffs.append({
                    "type": "可空性不同",
                    "table": table_name,
                    "field": col_name,
                    "detail": "DDL=%s, 实际=%s" % (ddl_null, act_null),
                })
            exp_default = exp_col.get("default")
            act_default = act_col.get("default")
            if not _defaults_equivalent(exp_default, act_default):
                ddl_def = "NULL" if exp_default is None else str(exp_default)
                act_def = "NULL" if act_default is None else str(act_default)
                diffs.append({
                    "type": "默认值不同",
                    "table": table_name,
                    "field": col_name,
                    "detail": "DDL=%s, 实际=%s" % (ddl_def, act_def),
                })
        for col_name in act_cols:
            if col_name not in exp_cols:
                diffs.append({
                    "type": "字段多余",
                    "table": table_name,
                    "field": col_name,
                    "detail": "数据库中存在但 DDL 未定义",
                })
        exp_pk = exp_data.get("primary_key", [])
        act_pk = act_data.get("primary_key", [])
        if exp_pk and not act_pk:
            diffs.append({
                "type": "主键缺失",
                "table": table_name,
                "field": None,
                "detail": "DDL 定义主键(%s)，数据库中无主键" % ",".join(exp_pk),
            })
        elif exp_pk and act_pk and exp_pk != act_pk:
            diffs.append({
                "type": "主键不同",
                "table": table_name,
                "field": None,
                "detail": "DDL 主键=%s, 实际主键=%s" % (",".join(exp_pk), ",".join(act_pk)),
            })
        exp_indexes = {idx["name"]: idx for idx in exp_data.get("indexes", [])}
        act_indexes = {idx["name"]: idx for idx in act_data.get("indexes", [])}
        for idx_name, exp_idx in exp_indexes.items():
            if idx_name not in act_indexes:
                diffs.append({
                    "type": "索引缺失",
                    "table": table_name,
                    "field": None,
                    "index": idx_name,
                    "detail": "DDL 中定义但数据库中不存在",
                })
                continue
            act_idx = act_indexes[idx_name]
            if exp_idx["columns"] != act_idx["columns"]:
                exp_cols_str = "(%s)" % ",".join(exp_idx["columns"])
                act_cols_str = "(%s)" % ",".join(act_idx["columns"])
                diffs.append({
                    "type": "索引列不同",
                    "table": table_name,
                    "field": None,
                    "index": idx_name,
                    "detail": "DDL=%s, 实际=%s" % (exp_cols_str, act_cols_str),
                })
            if exp_idx["unique"] != act_idx["unique"]:
                ddl_uniq = "UNIQUE" if exp_idx["unique"] else "普通索引"
                act_uniq = "UNIQUE" if act_idx["unique"] else "普通索引"
                diffs.append({
                    "type": "索引唯一性不同",
                    "table": table_name,
                    "field": None,
                    "index": idx_name,
                    "detail": "DDL=%s, 实际=%s" % (ddl_uniq, act_uniq),
                })
        for idx_name in act_indexes:
            if idx_name not in exp_indexes:
                diffs.append({
                    "type": "索引多余",
                    "table": table_name,
                    "field": None,
                    "index": idx_name,
                    "detail": "数据库中存在但 DDL 未定义",
                })
    return diffs


def format_diff_report(diffs: List[Dict[str, Any]]) -> str:
    """格式化差异报告。"""
    lines = ["[DB Schema Check] 校验失败，发现 %d 处不一致：" % len(diffs), ""]
    type_labels = {
        "表缺失": "[表缺失]",
        "字段缺失": "[字段缺失]",
        "字段多余": "[字段多余]",
        "类型不同": "[类型不同]",
        "可空性不同": "[可空性不同]",
        "默认值不同": "[默认值不同]",
        "主键缺失": "[主键缺失]",
        "主键不同": "[主键不同]",
        "索引缺失": "[索引缺失]",
        "索引多余": "[索引多余]",
        "索引列不同": "[索引列不同]",
        "索引唯一性不同": "[索引唯一性不同]",
    }
    for d in diffs:
        label = type_labels.get(d["type"], "[%s]" % d["type"])
        if d.get("index"):
            lines.append("%s 表 %s, 索引 %s: %s" % (label, d["table"], d["index"], d["detail"]))
        elif d.get("field"):
            lines.append("%s 表 %s, 字段 %s: %s" % (label, d["table"], d["field"], d["detail"]))
        else:
            lines.append("%s %s: %s" % (label, d["table"], d["detail"]))
    lines.extend([
        "",
        "请执行 database/V1.0.x__xxx.sql 等迁移脚本，或联系 DBA 同步表结构。",
    ])
    return "\n".join(lines)


async def run_schema_check() -> Tuple[bool, List[Dict[str, Any]]]:
    """主入口：执行表结构一致性校验，返回 (是否一致, 差异列表)。"""
    from backend.core.database import engine
    db_name = _parse_db_name_from_url(settings.DATABASE_URL)
    if not db_name:
        raise ValueError("无法从 DATABASE_URL 解析数据库名")
    project_root = Path(__file__).resolve().parent.parent.parent
    database_dir = project_root / "database"
    expected = get_expected_schema(database_dir)
    actual = await get_actual_schema(engine, db_name)
    diffs = compare_schemas(expected, actual)
    return (len(diffs) == 0, diffs)
