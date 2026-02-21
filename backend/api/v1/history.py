# ============================================================
# API 路由层 — 执行明细（/api/v1/history）
# ============================================================
# API 层是整个后端的"入口"，负责：
#   1. 接收 HTTP 请求（从 URL 参数、请求体中提取数据）
#   2. 调用 Service 层处理业务逻辑
#   3. 把结果包装成 JSON 返回给前端
#
# 请求流程:
#   浏览器 → GET /api/v1/history?page=1&case_result=failed
#       → FastAPI 路由匹配 → 调用 get_history_list() 函数
#       → 调用 history_service.list_history() 查数据库
#       → 返回 JSON { items: [...], total: 20, ... }
# ============================================================

# APIRouter: FastAPI 的路由器，用于组织和分组 API 端点（类似于一个迷你 app）
# Depends:   FastAPI 的依赖注入机制 — 自动调用指定函数并把结果作为参数传入
# Query:     声明 URL 查询参数，可以设置默认值、校验规则（如最小值、最大值）
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
# AsyncSession: 异步数据库会话类型（用于类型标注）
from sqlalchemy.ext.asyncio import AsyncSession

# get_db: 数据库会话的提供者函数（定义在 database.py 中）
# FastAPI 的 Depends(get_db) 会自动调用它，创建一个 session 并在请求结束后关闭
from backend.core.database import get_db
# PageResponse: 通用分页响应模型 { items, total, page, page_size }
from backend.schemas.common import PageResponse
# HistoryItem:  单条记录的响应格式；HistoryQuery: 查询参数的格式；HistoryFilterOptions: 筛选选项
from backend.schemas.history import HistoryFilterOptions, HistoryItem, HistoryQuery
# list_history, get_history_options: Service 层的查询函数
from backend.services.history_service import get_history_options, list_history

# 创建一个路由器实例:
# - prefix="/history": 这个路由器下的所有端点都自动加上 /history 前缀
#   （加上总路由的 /api/v1 前缀，最终完整路径就是 /api/v1/history）
# - tags=["执行明细"]: 在 Swagger 文档（/docs）中，这组 API 会被归类到"执行明细"标签下
router = APIRouter(prefix="/history", tags=["执行明细"])


@router.get("/options", response_model=HistoryFilterOptions)
async def get_history_options_endpoint(db: AsyncSession = Depends(get_db)):
    """获取筛选选项，供前端 Select 下拉使用。"""
    return await get_history_options(db)


# @router.get("") 定义一个 GET 请求的端点
# 完整路径: /api/v1/history（prefix="/history" + "" = "/history"）
# response_model=PageResponse[HistoryItem] 的作用：
#   1. 告诉 FastAPI 返回值的 JSON 结构是 PageResponse，其中 items 的每个元素是 HistoryItem
#   2. FastAPI 会自动过滤掉 response_model 中没有定义的字段（数据安全）
#   3. 自动在 Swagger 文档中展示返回值的结构
@router.get("", response_model=PageResponse[HistoryItem])
async def get_history_list(
    # 以下参数来自 URL 查询字符串（即 ?page=1&page_size=20&...）
    # Query() 用于定义参数的约束和默认值：
    # - ge=1:     greater or equal，page 最小值为 1（传 0 会报 422 校验错误）
    # - le=100:   less or equal，page_size 最大值为 100（防止一次查太多数据）
    # - None:     默认值为 None，表示不传时不做筛选
    page: int = Query(1, ge=1),                  # 当前页码，默认 1，最小 1
    page_size: int = Query(20, ge=1, le=100),    # 每页条数，默认 20，范围 1~100
    start_time: Optional[List[str]] = Query(None),     # 筛选批次（多选）
    subtask: Optional[List[str]] = Query(None),         # 筛选分组（多选）
    case_name: Optional[List[str]] = Query(None),      # 用例名多选（可选）
    main_module: Optional[List[str]] = Query(None),    # 筛选主模块（多选）
    case_result: Optional[List[str]] = Query(None),     # 筛选执行结果（多选）
    case_level: Optional[List[str]] = Query(None),      # 筛选用例级别（多选）
    analyzed: Optional[List[int]] = Query(None),       # 筛选是否已分析（多选：1=已分析，0=未分析）
    platform: Optional[List[str]] = Query(None),       # 筛选平台（多选）
    code_branch: Optional[List[str]] = Query(None),    # 筛选代码分支（多选）
    sort_field: Optional[str] = Query(None),           # 排序列
    sort_order: Optional[str] = Query(None),           # 排序方向：asc / desc
    # Depends(get_db) 是 FastAPI 的核心特性"依赖注入":
    #   1. 请求进来时，FastAPI 自动调用 get_db() 函数
    #   2. get_db() 创建一个数据库会话（AsyncSession）并返回
    #   3. 这个 session 自动赋值给参数 db，供下面的代码使用
    #   4. 请求处理完毕后，get_db() 中的 async with 自动关闭 session
    # 这样你不用在每个 API 函数中手动创建/关闭数据库连接。
    db: AsyncSession = Depends(get_db),
):
    # 把 URL 参数打包成 HistoryQuery 对象
    # HistoryQuery 继承了 PageRequest，所以包含 page, page_size, start_time, case_result, platform
    query = HistoryQuery(
        page=page,
        page_size=page_size,
        start_time=start_time,
        subtask=subtask,
        case_name=case_name,
        main_module=main_module,
        case_result=case_result,
        case_level=case_level,
        analyzed=analyzed,
        platform=platform,
        code_branch=code_branch,
        sort_field=sort_field,
        sort_order=sort_order,
    )
    # 调用 Service 层的 list_history 函数，传入数据库会话和查询参数
    # await 表示异步等待 — 在等数据库返回结果期间，服务器可以处理其他请求
    # 返回值是一个元组: (items列表, total总数)
    items, total = await list_history(db, query)
    # 构建分页响应并返回
    # HistoryItem.model_validate(item): 把 SQLAlchemy ORM 对象转成 Pydantic Schema 对象
    #   之所以能这样转，是因为 HistoryItem 设置了 model_config = {"from_attributes": True}
    # 列表推导式 [... for item in items] 对每个 ORM 对象逐一转换
    return PageResponse(
        items=[HistoryItem.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
