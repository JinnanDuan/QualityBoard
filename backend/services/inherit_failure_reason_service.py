# ============================================================
# Inherit Failure Reason Service — 失败原因继承的业务逻辑层
# ============================================================

import hashlib
import logging
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import insert, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.pipeline_failure_reason import PipelineFailureReason
from backend.models.pipeline_history import PipelineHistory
from backend.schemas.inherit_failure_reason import (
    InheritBatchOptionsResponse,
    InheritFailureReasonRequest,
    InheritFailureReasonResponse,
    InheritSourceOptionsResponse,
    InheritSourceRecordItem,
    InheritSourceRecordsResponse,
)

logger = logging.getLogger(__name__)

ph = PipelineHistory
pfr = PipelineFailureReason
ALLOWED_RESULTS = ("failed", "error")  # 继承仅处理失败/异常；skip、passed 等不参与

# 批量 INSERT pfr 每批行数（避免单条 SQL 过大）
_PFR_INSERT_CHUNK = 200
# 批量 UPDATE pipeline_history.id IN 每批 id 数
_HISTORY_UPDATE_CHUNK = 500
# MySQL GET_LOCK 名称最长 64 字符
_LOCK_MAX_LEN = 64
# 获取锁等待秒数（与前端继承超时协调）
_LOCK_TIMEOUT_SEC = 60


def _lock_name_batch(target_batch: str) -> str:
    n = f"inherit_tb_{target_batch}"
    return n[:_LOCK_MAX_LEN]


def _lock_name_case(history_ids: List[int]) -> str:
    key = ",".join(sorted(str(i) for i in history_ids))
    h = hashlib.md5(key.encode("utf-8")).hexdigest()
    n = f"inherit_tc_{h}"
    return n[:_LOCK_MAX_LEN]


async def _mysql_get_lock(db: AsyncSession, lock_name: str, timeout_sec: int = _LOCK_TIMEOUT_SEC) -> bool:
    """返回 True 表示成功获得锁；0/NULL 表示超时或失败。"""
    r = await db.execute(text("SELECT GET_LOCK(:n, :t)"), {"n": lock_name, "t": timeout_sec})
    val = r.scalar_one()
    return val == 1


async def _mysql_release_lock(db: AsyncSession, lock_name: str) -> None:
    await db.execute(text("SELECT RELEASE_LOCK(:n)"), {"n": lock_name})


async def get_inherit_batch_options(
    db: AsyncSession, exclude_batch: Optional[str] = None
) -> InheritBatchOptionsResponse:
    """获取继承弹窗的批次选项，排除当前批次，按时间倒序。仅返回 20 开头的批次（与历史列表默认逻辑一致）。"""
    stmt = (
        select(ph.start_time)
        .where(ph.start_time.is_not(None))
        .where(ph.start_time != "")
        .where(ph.start_time.like("20%"))
        .distinct()
        .order_by(ph.start_time.desc())
        .limit(100)
    )
    if exclude_batch and str(exclude_batch).strip():
        stmt = stmt.where(ph.start_time != exclude_batch.strip())
    result = await db.execute(stmt)
    batches = [r[0] for r in result.all() if r[0]]
    return InheritBatchOptionsResponse(batches=batches)


async def get_inherit_source_options(
    db: AsyncSession,
    case_name: Optional[str] = None,
    platform: Optional[str] = None,
) -> InheritSourceOptionsResponse:
    """获取用例维度源选择三字段选项，支持 case_name、platform 联动缩小范围。"""
    # case_names: 始终返回全部（供下拉展示）
    case_stmt = select(pfr.case_name).where(pfr.case_name.is_not(None)).distinct()
    case_result = await db.execute(case_stmt)
    case_names = sorted(set(r[0] for r in case_result.all() if r[0]), key=lambda x: (x or ""))

    # platforms、batches: 按 case_name、platform 过滤
    filter_stmt = select(pfr.platform, pfr.failed_batch).distinct()
    if case_name and str(case_name).strip():
        filter_stmt = filter_stmt.where(pfr.case_name == case_name.strip())
    if platform and str(platform).strip():
        filter_stmt = filter_stmt.where(pfr.platform == platform.strip())
    filter_result = await db.execute(filter_stmt)
    filter_rows = filter_result.all()

    platforms = sorted(set(r[0] for r in filter_rows if r[0] is not None), key=lambda x: (x or ""))
    batches = sorted(set(r[1] for r in filter_rows if r[1]), key=lambda x: (x or ""), reverse=True)

    return InheritSourceOptionsResponse(
        case_names=case_names,
        platforms=platforms,
        batches=batches,
    )


async def get_inherit_source_records(
    db: AsyncSession,
    case_name: str,
    platform: Optional[str] = None,
    batch: Optional[str] = None,
) -> InheritSourceRecordsResponse:
    """根据三字段筛选，返回匹配的 pfr 记录列表，供用户选择。"""
    case_name = (case_name or "").strip()
    if not case_name:
        return InheritSourceRecordsResponse(records=[])

    # 使用 raw SQL 避免 ORM 潜在问题，与诊断脚本一致
    sql = (
        "SELECT id, case_name, platform, failed_batch, failed_type, owner, reason "
        "FROM pipeline_failure_reason WHERE case_name = :case_name"
    )
    params: dict = {"case_name": case_name}
    if platform and str(platform).strip():
        sql += " AND platform = :platform"
        params["platform"] = platform.strip()
    if batch and str(batch).strip():
        sql += " AND failed_batch = :batch"
        params["batch"] = batch.strip()
    sql += " ORDER BY failed_batch DESC, platform ASC"

    result = await db.execute(text(sql), params)
    rows = result.fetchall()
    logger.info(
        "inherit-source-records: case_name=%r platform=%r batch=%r -> %d 条",
        case_name,
        platform,
        batch,
        len(rows),
    )

    records = [
        InheritSourceRecordItem(
            id=r[0],
            case_name=r[1],
            platform=r[2],
            failed_batch=r[3],
            failed_type=r[4],
            owner=r[5],
            reason=r[6],
        )
        for r in rows
    ]
    return InheritSourceRecordsResponse(records=records)


async def inherit_failure_reason(
    db: AsyncSession,
    req: InheritFailureReasonRequest,
    operator_employee_id: str,
) -> InheritFailureReasonResponse:
    """
    执行失败原因继承。根据 inherit_mode 分支：批次维度按 (case_name, platform) 匹配；
    用例维度将源记录的失败原因原样复制到勾选用例。
    """
    if req.inherit_mode == "batch":
        return await _inherit_batch(db, req, operator_employee_id)
    else:
        return await _inherit_case(db, req, operator_employee_id)


async def _bulk_insert_pfr_rows(db: AsyncSession, rows: List[Dict]) -> None:
    """批量插入 pipeline_failure_reason，分块执行。"""
    if not rows:
        return
    for i in range(0, len(rows), _PFR_INSERT_CHUNK):
        chunk = rows[i : i + _PFR_INSERT_CHUNK]
        await db.execute(insert(pfr), chunk)


async def _bulk_set_analyzed(db: AsyncSession, history_ids: List[int]) -> None:
    """批量将 pipeline_history.analyzed 置为 1。"""
    if not history_ids:
        return
    for i in range(0, len(history_ids), _HISTORY_UPDATE_CHUNK):
        chunk = history_ids[i : i + _HISTORY_UPDATE_CHUNK]
        await db.execute(update(ph).where(ph.id.in_(chunk)).values(analyzed=1))


async def _inherit_batch(
    db: AsyncSession,
    req: InheritFailureReasonRequest,
    operator_employee_id: str,
) -> InheritFailureReasonResponse:
    """批次维度：仅对未分析（analyzed=0/NULL）的 failed/error 继承；仅 INSERT pfr；MySQL 锁防并发。"""
    source_batch = req.source_batch.strip()
    target_batch = req.target_batch.strip()
    lock_name = _lock_name_batch(target_batch)

    # 校验 target_batch 存在
    check_stmt = select(ph).where(ph.start_time == target_batch).limit(1)
    check_result = await db.execute(check_stmt)
    if not check_result.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="目标批次不存在")

    if not await _mysql_get_lock(db, lock_name):
        logger.warning("继承批次锁获取失败 lock=%s 操作人=%s", lock_name, operator_employee_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="当前目标批次正在其他继承任务中处理，请稍后重试",
        )

    try:
        # 仅未分析的 failed/error
        target_stmt = select(ph).where(
            ph.start_time == target_batch,
            ph.case_result.in_(ALLOWED_RESULTS),
            or_(ph.analyzed == 0, ph.analyzed.is_(None)),
        )
        target_result = await db.execute(target_stmt)
        target_histories = list(target_result.scalars().all())

        source_pfr_stmt = select(pfr).where(pfr.failed_batch == source_batch)
        source_pfr_result = await db.execute(source_pfr_stmt)
        source_pfr_list = list(source_pfr_result.scalars().all())
        source_map = {
            (r.case_name, r.platform): r
            for r in source_pfr_list
            if r.case_name is not None and r.platform is not None
        }

        pfr_rows: List[Dict] = []
        history_ids: List[int] = []
        skipped = 0

        for th in target_histories:
            case_name = th.case_name
            platform = th.platform
            if not case_name or platform is None:
                skipped += 1
                continue

            key = (case_name, platform)
            source_pfr = source_map.get(key)
            if not source_pfr:
                skipped += 1
                continue

            target_failed_batch = th.start_time
            if not target_failed_batch:
                skipped += 1
                continue

            pfr_rows.append(
                {
                    "case_name": case_name,
                    "failed_batch": target_failed_batch,
                    "platform": platform,
                    "owner": source_pfr.owner,
                    "reason": source_pfr.reason,
                    "failed_type": source_pfr.failed_type,
                    "analyzer": source_pfr.analyzer,
                    "created_at": source_pfr.created_at,
                    "recover_batch": None,
                    "dts_num": None,
                }
            )
            history_ids.append(th.id)

        inherited = len(history_ids)

        await _bulk_insert_pfr_rows(db, pfr_rows)
        await _bulk_set_analyzed(db, history_ids)

        await db.commit()
        logger.info(
            "继承失败原因：维度=batch，继承数量=%d，跳过=%d，操作人=%s",
            inherited,
            skipped,
            operator_employee_id,
        )
        return InheritFailureReasonResponse(
            success=True,
            inherited_count=inherited,
            skipped_count=skipped,
            message=f"继承成功，共继承 {inherited} 条" + (f"，跳过 {skipped} 条" if skipped else ""),
        )
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        logger.exception("继承失败原因失败: %s", e)
        await db.rollback()
        raise
    finally:
        await _mysql_release_lock(db, lock_name)


async def _inherit_case(
    db: AsyncSession,
    req: InheritFailureReasonRequest,
    operator_employee_id: str,
) -> InheritFailureReasonResponse:
    """用例维度：仅对未分析记录继承；仅 INSERT pfr；MySQL 锁防并发。"""
    if req.source_pfr_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先筛选并选择一条源记录")

    lock_name = _lock_name_case(list(req.history_ids or []))

    source_pfr_stmt = select(pfr).where(pfr.id == req.source_pfr_id)
    source_pfr_result = await db.execute(source_pfr_stmt)
    source_pfr = source_pfr_result.scalars().first()

    if not source_pfr:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="源记录不存在或已删除")

    if not await _mysql_get_lock(db, lock_name):
        logger.warning("继承用例锁获取失败 lock=%s 操作人=%s", lock_name, operator_employee_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="当前勾选范围正在其他继承任务中处理，请稍后重试",
        )

    try:
        target_stmt = select(ph).where(ph.id.in_(req.history_ids))
        target_result = await db.execute(target_stmt)
        target_histories = list(target_result.scalars().all())

        if len(target_histories) != len(req.history_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="部分勾选记录不存在")

        for th in target_histories:
            if th.case_result not in ALLOWED_RESULTS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"记录 id={th.id} 不是失败/异常记录，无法继承",
                )

        pfr_rows: List[Dict] = []
        history_ids: List[int] = []
        skipped = 0

        for th in target_histories:
            if th.analyzed is not None and th.analyzed != 0:
                skipped += 1
                continue

            case_name = th.case_name
            failed_batch = th.start_time
            platform = th.platform
            if not case_name or failed_batch is None or platform is None:
                skipped += 1
                continue

            pfr_rows.append(
                {
                    "case_name": case_name,
                    "failed_batch": failed_batch,
                    "platform": platform,
                    "owner": source_pfr.owner,
                    "reason": source_pfr.reason,
                    "failed_type": source_pfr.failed_type,
                    "analyzer": source_pfr.analyzer,
                    "created_at": source_pfr.created_at,
                    "recover_batch": None,
                    "dts_num": None,
                }
            )
            history_ids.append(th.id)

        inherited = len(history_ids)

        if inherited == 0:
            await db.commit()
            logger.info(
                "继承失败原因：维度=case，继承数量=0，跳过=%d，操作人=%s",
                skipped,
                operator_employee_id,
            )
            return InheritFailureReasonResponse(
                success=True,
                inherited_count=0,
                skipped_count=skipped,
                message="所选记录均已分析或无法继承，未写入数据",
            )

        await _bulk_insert_pfr_rows(db, pfr_rows)
        await _bulk_set_analyzed(db, history_ids)

        await db.commit()
        logger.info(
            "继承失败原因：维度=case，继承数量=%d，跳过=%d，操作人=%s",
            inherited,
            skipped,
            operator_employee_id,
        )
        return InheritFailureReasonResponse(
            success=True,
            inherited_count=inherited,
            skipped_count=skipped,
            message=f"继承成功，共继承 {inherited} 条" + (f"，跳过 {skipped} 条" if skipped else ""),
        )
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        logger.exception("继承失败原因失败: %s", e)
        await db.rollback()
        raise
    finally:
        await _mysql_release_lock(db, lock_name)

