# ============================================================
# History Schema — 执行明细的请求/响应数据模型
# ============================================================
# 这个文件定义了两个 Schema：
# 1. HistoryItem:  响应模型 — 描述返回给前端的每条执行记录长什么样
# 2. HistoryQuery: 请求模型 — 描述前端可以传哪些查询/筛选参数
# ============================================================

# datetime: Python 的日期时间类型，用于 created_at、updated_at 字段
from datetime import datetime
# List: 列表类型；Optional: 表示字段可以为 None（前端 JSON 中会显示为 null）
from typing import List, Optional

# BaseModel: Pydantic 的基类，所有 Schema 都继承它以获得自动校验能力
from pydantic import BaseModel

# PageRequest: 我们自定义的分页请求基类（包含 page 和 page_size 字段）
from backend.schemas.common import PageRequest


# HistoryItem — 单条执行记录的响应模型
# 它的字段和 PipelineHistory ORM 模型一一对应。
# 区别在于：ORM 模型面向数据库（定义字段的 SQL 类型、索引等），
#           Schema 面向 API（定义 JSON 的序列化格式、字段校验规则等）。
class HistoryItem(BaseModel):
    # --- 以下每个字段对应 pipeline_history 表的一列 ---
    id: int                                       # 主键 ID
    start_time: Optional[str] = None              # 轮次标识
    subtask: Optional[str] = None                 # 组别
    reports_url: Optional[str] = None             # 测试报告 URL
    log_url: str                                  # 日志 URL
    screenshot_url: str                           # 截图 URL
    module: Optional[str] = None                  # 模块名
    case_name: Optional[str] = None               # 用例名称
    case_result: Optional[str] = None             # 执行结果 (passed/failed)
    created_at: Optional[datetime] = None         # 创建时间
    updated_at: Optional[datetime] = None         # 更新时间
    pipeline_url: Optional[str] = None            # Jenkins 流水线 URL
    case_level: str = ""                          # 用例级别 (P0/P1/P2)
    main_module: str = ""                         # 主模块
    owner_history: Optional[str] = None           # 责任人变更记录
    owner: Optional[str] = None                   # 当前责任人
    platform: Optional[str] = None                # 平台 (Android/iOS/Web)
    code_branch: Optional[str] = None             # 代码分支
    analyzed: Optional[int] = 0                   # 是否已分析 (1=是, 0=否)
    failure_owner: Optional[str] = None           # 失败跟踪人（来自 pipeline_failure_reason.owner）
    failed_type: Optional[str] = None             # 失败原因分类（来自 pipeline_failure_reason.failed_type）

    # model_config 是 Pydantic v2 的配置方式（替代 v1 的 class Config）
    # "from_attributes": True 的作用：
    #   允许直接把 SQLAlchemy ORM 对象转成这个 Schema。
    #   比如 HistoryItem.model_validate(orm_obj)，Pydantic 会自动读取 orm_obj 的属性来填充字段。
    #   如果不设置这个，Pydantic 只能接受 dict，不能接受 ORM 对象。
    model_config = {"from_attributes": True}


# HistoryQuery — 查询参数模型
# 继承 PageRequest，自动获得 page 和 page_size 字段。
# 支持 10 个可选筛选条件，case_name 支持模糊搜索，其余支持多选。
class HistoryQuery(PageRequest):
    start_time: Optional[List[str]] = None       # 按批次筛选（多选）
    subtask: Optional[List[str]] = None          # 按分组筛选（多选）
    case_name: Optional[List[str]] = None        # 按用例名多选（可选）
    main_module: Optional[List[str]] = None     # 按主模块筛选（多选）
    case_result: Optional[List[str]] = None     # 按执行结果筛选（多选）
    case_level: Optional[List[str]] = None       # 按用例级别筛选（多选）
    analyzed: Optional[List[int]] = None        # 按是否已分析筛选（多选：1=已分析，0=未分析）
    platform: Optional[List[str]] = None         # 按平台筛选（多选）
    code_branch: Optional[List[str]] = None      # 按代码分支筛选（多选）
    failure_owner: Optional[List[str]] = None    # 按失败跟踪人筛选（多选）
    failed_type: Optional[List[str]] = None      # 按失败原因筛选（多选）
    sort_field: Optional[str] = None             # 排序列（如 start_time, case_name）
    sort_order: Optional[str] = None             # 排序方向：asc / desc


# HistoryFilterOptions — 筛选选项响应模型
# 供 GET /api/v1/history/options 返回各字段的去重选项
class HistoryFilterOptions(BaseModel):
    start_time: List[str] = []
    subtask: List[str] = []
    case_name: List[str] = []
    main_module: List[str] = []
    case_result: List[str] = []
    case_level: List[str] = []
    platform: List[str] = []
    code_branch: List[str] = []
    failure_owner: List[str] = []
    failed_type: List[str] = []
