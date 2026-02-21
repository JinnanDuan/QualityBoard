# ============================================================
# Failure Process Service — 失败记录标注的业务逻辑层
# ============================================================

import logging
from typing import List

from fastapi import HTTPException, status  # HTTP 异常与状态码
from sqlalchemy import and_, select  # 组合条件、构建查询
from sqlalchemy.ext.asyncio import AsyncSession  # 异步数据库会话
from backend.models.case_failed_type import CaseFailedType  # 失败类型表
from backend.models.pipeline_failure_reason import PipelineFailureReason  # 失败原因表
from backend.models.pipeline_history import PipelineHistory  # 执行历史表
from backend.models.ums_email import UmsEmail  # 员工表
from backend.models.ums_module_owner import UmsModuleOwner  # 模块负责人表
from backend.schemas.failure_process import (
    FailureProcessOptions,
    CaseFailedTypeItem,
    OwnerItem,
    ModuleItem,
    FailureProcessRequest,
)

logger = logging.getLogger(__name__)


async def get_failure_process_options(db: AsyncSession) -> FailureProcessOptions:
    """获取标注弹窗所需的选项数据（失败类型、跟踪人、模块）。"""
    # 1. 查询 case_failed_type，按 id 排序
    cft_stmt = select(CaseFailedType).order_by(CaseFailedType.id)
    cft_result = await db.execute(cft_stmt)
    case_failed_types = [
        CaseFailedTypeItem(
            id=row.id,
            failed_reason_type=row.failed_reason_type,
            owner=row.owner,
        )
        for row in cft_result.scalars().all()
    ]

    # 2. 查询 ums_email，按 employee_id 排序
    ums_stmt = select(UmsEmail).order_by(UmsEmail.employee_id)
    ums_result = await db.execute(ums_stmt)
    owners = [
        OwnerItem(employee_id=row.employee_id, name=row.name)
        for row in ums_result.scalars().all()
    ]

    # 3. 查询 ums_module_owner，按 module 排序
    umo_stmt = select(UmsModuleOwner).order_by(UmsModuleOwner.module)
    umo_result = await db.execute(umo_stmt)
    modules = [
        ModuleItem(module=row.module, owner=row.owner)
        for row in umo_result.scalars().all()
    ]

    return FailureProcessOptions(
        case_failed_types=case_failed_types,
        owners=owners,
        modules=modules,
    )


async def process_failure(
    db: AsyncSession,
    req: FailureProcessRequest,
    analyzer_employee_id: str,  # 当前登录用户工号，写入 pipeline_failure_reason.analyzer
) -> None:
    """
    处理失败记录标注：更新 pipeline_history.analyzed，插入或更新 pipeline_failure_reason。
    """
    if not req.history_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="history_ids 不能为空")

    # 1. 校验并获取所有 history 记录，确保存在且 case_result=failed
    stmt = select(PipelineHistory).where(PipelineHistory.id.in_(req.history_ids))
    result = await db.execute(stmt)
    histories = list(result.scalars().all())

    if len(histories) != len(req.history_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="部分记录不存在",
        )

    for h in histories:
        if h.case_result != "failed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"记录 id={h.id} 不是失败记录，无法标注",
            )

    # 2. 更新 pipeline_history.analyzed = 1
    for h in histories:
        h.analyzed = 1

    # 3. 对每条记录，按 (case_name, start_time, platform) 判断 INSERT 或 UPDATE
    for h in histories:
        case_name = h.case_name
        failed_batch = h.start_time
        platform = h.platform

        if not case_name or failed_batch is None or platform is None:
            continue  # 关键字段缺失则跳过

        # 按 (case_name, failed_batch, platform) 查询是否已有 pipeline_failure_reason
        pfr_stmt = select(PipelineFailureReason).where(
            and_(
                PipelineFailureReason.case_name == case_name,
                PipelineFailureReason.failed_batch == failed_batch,
                PipelineFailureReason.platform == platform,
            )
        )
        pfr_result = await db.execute(pfr_stmt)
        existing = pfr_result.scalars().first()

        if existing:
            # 已存在则 UPDATE
            existing.owner = req.owner
            existing.reason = req.reason
            existing.failed_type = req.failed_type
            existing.analyzer = analyzer_employee_id
        else:
            # 不存在则 INSERT
            new_pfr = PipelineFailureReason(
                case_name=case_name,
                failed_batch=failed_batch,
                platform=platform,
                owner=req.owner,
                reason=req.reason,
                failed_type=req.failed_type,
                analyzer=analyzer_employee_id,
            )
            db.add(new_pfr)

    try:
        await db.commit()
        owner_masked = f"{req.owner[:2]}***" if req.owner and len(req.owner) > 2 else "***"
        logger.info(
            "失败标注提交成功 记录数=%d failed_type=%s owner=%s analyzer=%s",
            len(histories),
            req.failed_type,
            owner_masked,
            analyzer_employee_id,
        )
    except Exception as e:
        logger.exception("失败标注提交失败: %s", e)
        raise
