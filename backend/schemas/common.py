# ============================================================
# 公共 Schema — 分页请求/响应的通用模型
# ============================================================
# Schema（模式/模型）在 FastAPI 中承担"数据校验"的角色：
# - 请求 Schema: 校验前端发来的参数是否合法（比如 page 必须 >= 1）
# - 响应 Schema: 定义 API 返回给前端的 JSON 数据格式
# 它们使用 Pydantic 库实现，Pydantic 会自动做类型检查和转换。
# ============================================================

# Generic: Python 的泛型支持，让一个类可以适配不同的数据类型
# List: 列表类型
# Optional: 可选类型（值可以是 None）
# TypeVar: 类型变量，用于定义泛型参数
from typing import Generic, List, Optional, TypeVar

# BaseModel 是 Pydantic 的核心基类，所有 Schema 都要继承它
# 继承 BaseModel 后，Pydantic 会自动：
#   1. 校验传入数据的类型（比如 page 必须是 int，传字符串会报错）
#   2. 提供 JSON 序列化/反序列化能力
#   3. 自动生成 API 文档中的参数说明
from pydantic import BaseModel

# 定义一个泛型类型变量 T — 可以代表任意类型
# 后面 PageResponse[HistoryItem] 中的 HistoryItem 就会替换这个 T
T = TypeVar("T")


# 分页请求基类 — 其他查询 Schema 可以继承它，自动获得 page 和 page_size 字段
# 前端请求 GET /api/v1/history?page=2&page_size=10 时，这两个参数就会映射到这里
class PageRequest(BaseModel):
    page: int = 1          # 当前页码，默认第 1 页
    page_size: int = 20    # 每页条数，默认 20 条


# 分页响应基类 — 泛型类，T 代表列表中每个元素的类型
# 使用方式: PageResponse[HistoryItem] 表示 items 是 HistoryItem 的列表
# 返回给前端的 JSON 格式如下:
# {
#   "items": [...],      ← 当前页的数据列表
#   "total": 100,        ← 符合条件的总记录数（用于前端计算总页数）
#   "page": 1,           ← 当前页码
#   "page_size": 20      ← 每页条数
# }
class PageResponse(BaseModel, Generic[T]):
    items: List[T] = []    # 当前页的数据列表，默认空列表
    total: int = 0         # 总记录数
    page: int = 1          # 当前页码
    page_size: int = 20    # 每页条数


# 通用 API 响应包装 — 用于非分页的接口返回
# 返回格式: { "code": 0, "message": "ok", "data": {...} }
class ApiResponse(BaseModel, Generic[T]):
    code: int = 0               # 业务状态码（0 表示成功，非 0 表示错误）
    message: str = "ok"         # 状态描述
    data: Optional[T] = None    # 实际数据（可以为 None）
