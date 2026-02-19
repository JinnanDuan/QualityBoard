# ============================================================
# ORM 模型 — pipeline_history 表的 Python 映射
# ============================================================
# ORM (Object-Relational Mapping) 的作用：
# 把数据库里的一张表映射成一个 Python 类，表的每一行就是这个类的一个实例。
# 这样你就可以用 Python 对象的方式来操作数据库，而不用手写 SQL。
#
# 例如: row.case_name  等价于  SELECT case_name FROM pipeline_history WHERE id = ...
# ============================================================

# datetime 是 Python 内置的日期时间类型，用于映射数据库中的 DATETIME 字段
from datetime import datetime
# Optional 表示"可选的"，即字段值可以为 None（对应数据库中 nullable=True 的字段）
from typing import Optional

# 从 SQLAlchemy 导入数据库字段类型和索引定义：
# - Integer: 整数类型，对应 MySQL 的 INT
# - String:  字符串类型，对应 MySQL 的 VARCHAR(n)
# - DateTime: 日期时间类型，对应 MySQL 的 DATETIME
# - Text:    长文本类型，对应 MySQL 的 TEXT（本表未用到，但保留导入）
# - Index:   数据库索引，用于加速查询
from sqlalchemy import Integer, String, DateTime, Text, Index
# Mapped 和 mapped_column 是 SQLAlchemy 2.0 的新式声明方式：
# - Mapped[int] 表示这个字段在 Python 中的类型是 int
# - mapped_column(...) 描述这个字段在数据库中的具体属性（类型、是否可空、默认值等）
from sqlalchemy.orm import Mapped, mapped_column

# Base 是所有 ORM 模型的基类（定义在 base.py 中），所有表映射类都必须继承它
from backend.models.base import Base


# 这个类映射 MySQL 中的 pipeline_history 表 —— 用例级执行明细
# 每一行记录代表某一轮测试中某个用例的一次执行结果
class PipelineHistory(Base):
    # __tablename__ 告诉 SQLAlchemy 这个类对应数据库中的哪张表
    __tablename__ = "pipeline_history"
    # __table_args__ 用于定义表级别的配置，比如索引：
    # 这些索引必须和 database/V1.0.1__create_pipeline_history.sql 中的 DDL 保持一致
    __table_args__ = (
        # 联合索引：按 (start_time, subtask) 加速查询，用于"按轮次+组别"筛选
        Index("idx_timentask", "start_time", "subtask"),
        # 单字段索引：按 main_module 加速查询
        Index("idx_main_module", "main_module"),
        # 联合索引：按 (start_time, case_name) 加速查询
        Index("idx_start_time_case", "start_time", "case_name"),
        # 联合索引：按 (case_name, platform, start_time) 加速查询
        Index("idx_casename_platform_batch", "case_name", "platform", "start_time"),
        # 单字段索引：按 created_at 加速排序/查询
        Index("idx_created_at_desc", "created_at"),
        # extend_existing=True: 如果 SQLAlchemy 运行时已经加载过这张表的元数据，不报错，直接复用
        {"extend_existing": True},
    )

    # ===== 以下是表的每一列（字段）定义 =====
    # 格式: 字段名: Mapped[Python类型] = mapped_column(数据库类型, 约束...)

    # 主键 id，自增整数
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 轮次标识（等同于 batch），格式如 "2026-02-19_10:00:00"
    start_time: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="轮次（等同于batch）")
    # 组别，如 "group-A"
    subtask: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="组别")
    # 测试报告的 URL 地址
    reports_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="测试报告的URL")
    # 日志 URL（必填字段，nullable=False）
    log_url: Mapped[str] = mapped_column(String(250), nullable=False, comment="日志URL")
    # 截图 URL（必填字段）
    screenshot_url: Mapped[str] = mapped_column(String(250), nullable=False, comment="截图URL")
    # 测试用例代码中标记的模块名
    module: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, comment="测试用例代码中标记的模块名")
    # 用例名称，如 "test_login_success"
    case_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用例名称")
    # 本轮执行结果，如 "passed" 或 "failed"
    case_result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="本轮执行结果")
    # 记录创建时间，默认取当前时间
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    # 记录更新时间，每次 UPDATE 时自动更新为当前时间（onupdate 参数）
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    # Jenkins 流水线 URL
    pipeline_url: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="Jenkins流水线URL")
    # 用例级别，如 "P0", "P1", "P2"
    case_level: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="用例级别")
    # 测试用例主模块，如 "auth", "payment", "order"
    main_module: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="测试用例主模块")
    # 用例责任人变更记录（JSON 格式的历史记录）
    owner_history: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用例责任人变更记录")
    # 当前用例责任人（开发人员）
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用例责任人（开发）")
    # 执行平台，如 "Android", "iOS", "Web"
    platform: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="平台名称")
    # 本轮执行时使用的代码分支
    code_branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="本轮执行时使用的IDE代码分支")
    # 是否已给失败用例分配了失败原因（1=已分析, 0=未分析）
    analyzed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0, comment="是否给失败用例分配了失败原因（1=是，0=否）")
