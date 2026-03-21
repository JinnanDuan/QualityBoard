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
from backend.core.dependencies import get_current_user  # 从 JWT 解析当前用户，未登录返回 401
# PageResponse: 通用分页响应模型 { items, total, page, page_size }
from backend.schemas.common import PageResponse
# HistoryItem:  单条记录的响应格式；HistoryQuery: 查询参数的格式；HistoryFilterOptions: 筛选选项
from backend.schemas.history import HistoryFilterOptions, HistoryItem, HistoryQuery
from backend.schemas.failure_process import FailureProcessOptions, FailureProcessRequest  # 失败标注 Schema
from backend.schemas.inherit_failure_reason import (
    InheritBatchOptionsResponse,
    InheritFailureReasonRequest,
    InheritFailureReasonResponse,
    InheritSourceOptionsResponse,
    InheritSourceRecordsResponse,
)
from backend.schemas.one_click_analyze import OneClickAnalyzeRequest, OneClickAnalyzeResponse
# list_history, get_history_options: Service 层的查询函数
from backend.services.history_service import get_history_options, list_history
from backend.services.failure_process_service import get_failure_process_options, process_failure  # 失败标注 Service
from backend.services.inherit_failure_reason_service import (
    get_inherit_batch_options,
    get_inherit_source_options,
    get_inherit_source_records,
    inherit_failure_reason,
)
from backend.services.one_click_analyze_service import one_click_analyze

# 创建一个路由器实例:
# - prefix="/history": 这个路由器下的所有端点都自动加上 /history 前缀
#   （加上总路由的 /api/v1 前缀，最终完整路径就是 /api/v1/history）
# - tags=["执行明细"]: 在 Swagger 文档（/docs）中，这组 API 会被归类到"执行明细"标签下
router = APIRouter(prefix="/history", tags=["执行明细"])


@router.get("/options", response_model=HistoryFilterOptions)
async def get_history_options_endpoint(db: AsyncSession = Depends(get_db)):
    """获取筛选选项，供前端 Select 下拉使用。"""
    return await get_history_options(db)


@router.get("/failure-process-options", response_model=FailureProcessOptions)
async def get_failure_process_options_endpoint(
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),  # 需登录，payload["sub"] 为工号
):
    """获取失败记录标注弹窗所需的选项数据（失败类型、跟踪人、模块）。"""
    return await get_failure_process_options(db)


@router.post("/failure-process")
async def post_failure_process(
    req: FailureProcessRequest,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),  # 需登录
):
    """提交失败记录标注，更新 pipeline_history.analyzed 与 pipeline_failure_reason。"""
    analyzer_employee_id = payload.get("sub", "")  # JWT 的 sub 存的是工号
    await process_failure(db, req, analyzer_employee_id)
    return {"success": True, "message": "标注成功"}


@router.get("/inherit-batch-options", response_model=InheritBatchOptionsResponse)
async def get_inherit_batch_options_endpoint(
    exclude_batch: Optional[str] = Query(None, description="排除的批次"),
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
):
    """获取继承弹窗的批次选项，排除当前批次，按时间倒序。"""
    return await get_inherit_batch_options(db, exclude_batch)


@router.get("/inherit-source-options", response_model=InheritSourceOptionsResponse)
async def get_inherit_source_options_endpoint(
    case_name: Optional[str] = Query(None, description="源用例名，用于联动缩小 platforms、batches"),
    platform: Optional[str] = Query(None, description="源平台，用于联动缩小 batches"),
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
):
    """获取用例维度源选择三字段选项（case_names、platforms、batches），支持级联筛选。"""
    return await get_inherit_source_options(db, case_name, platform)


@router.get("/inherit-source-records", response_model=InheritSourceRecordsResponse)
async def get_inherit_source_records_endpoint(
    case_name: str = Query(..., description="源用例名，必填"),
    platform: Optional[str] = Query(None, description="源平台，可选"),
    batch: Optional[str] = Query(None, description="源批次，可选"),
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
):
    """根据三字段筛选，返回匹配的源记录列表，供用户选择后再执行继承。"""
    return await get_inherit_source_records(db, case_name, platform, batch)


@router.post("/inherit-failure-reason", response_model=InheritFailureReasonResponse)
async def post_inherit_failure_reason(
    req: InheritFailureReasonRequest,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
):
    """执行失败原因继承，支持批次维度和用例维度。"""
    operator_employee_id = payload.get("sub", "")
    return await inherit_failure_reason(db, req, operator_employee_id)


@router.post("/one-click-analyze", response_model=OneClickAnalyzeResponse)
async def post_one_click_analyze(
    req: OneClickAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
):
    """一键分析：整批未分析失败/异常用例标记为 bug，跟踪人为用例开发责任人（姓名+工号）。"""
    analyzer_employee_id = payload.get("sub", "")
    return await one_click_analyze(db, req, analyzer_employee_id)


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
    failure_owner: Optional[List[str]] = Query(None),  # 筛选失败跟踪人（多选）
    failed_type: Optional[List[str]] = Query(None),    # 筛选失败原因（多选）
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
        failure_owner=failure_owner,
        failed_type=failed_type,
        sort_field=sort_field,
        sort_order=sort_order,
    )
    # 调用 Service 层的 list_history 函数，传入数据库会话和查询参数
    # 返回值是 (items, total)，items 为 (ph, failure_owner, failed_type, reason, failure_analyzer, analyzed_at, case_owner_display) 元组列表
    items, total = await list_history(db, query)
    # 组装 HistoryItem：从 ORM 转 Schema，并注入 failure_*；owner 为用例开发责任人展示（main_module→ums_module_owner，姓名+工号）
    result_items = [
        HistoryItem.model_validate(ph).model_copy(
            update={
                "owner": case_owner_display,
                "failure_owner": fo,
                "failed_type": ft,
                "reason": reason,
                "failure_analyzer": fa,
                "analyzed_at": analyzed_at,
            }
        )
        for ph, fo, ft, reason, fa, analyzed_at, case_owner_display in items
    ]
    return PageResponse(
        items=result_items,
        total=total,
        page=page,
        page_size=page_size,
    )
