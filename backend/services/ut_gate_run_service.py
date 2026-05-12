import logging
from typing import Tuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.ut_gate_run import UtGateRun
from backend.schemas.ut_gate_run import UtGateRunCreate

logger = logging.getLogger(__name__)


class UtGateIdempotencyConflict(Exception):
    """同 idempotency_key 已存在且参与幂等比较的字段与请求不一致。"""


def _payload_matches_existing_row(body: UtGateRunCreate, row: UtGateRun) -> bool:
    """spec/16 §5.1：逐项比较客户端可写字段（NULL 与缺失等价）。"""
    if row.job_name != body.job_name:
        return False
    if int(row.build_number) != int(body.build_number):
        return False
    if (row.build_url or None) != (body.build_url or None):
        return False
    if (row.jenkins_base_url or None) != (body.jenkins_base_url or None):
        return False
    if (row.mr_url or None) != (body.mr_url or None):
        return False
    if bool(row.is_intercepted) != bool(body.is_intercepted):
        return False
    if (row.ut_exit_code if row.ut_exit_code is not None else None) != (
        body.ut_exit_code if body.ut_exit_code is not None else None
    ):
        return False
    return True


async def create_ut_gate_run(db: AsyncSession, body: UtGateRunCreate) -> Tuple[UtGateRun, int]:
    """
    插入或幂等返回已有行。
    返回 (UtGateRun, http_status)，status 为 201 或 200。
    冲突时抛出 UtGateIdempotencyConflict。
    """
    key = body.idempotency_key
    res = await db.execute(select(UtGateRun).where(UtGateRun.idempotency_key == key))
    existing = res.scalar_one_or_none()
    if existing is not None:
        if _payload_matches_existing_row(body, existing):
            return existing, status.HTTP_200_OK
        raise UtGateIdempotencyConflict()

    row = UtGateRun(
        idempotency_key=body.idempotency_key,
        job_name=body.job_name,
        build_number=body.build_number,
        build_url=body.build_url,
        jenkins_base_url=body.jenkins_base_url,
        mr_url=body.mr_url,
        is_intercepted=body.is_intercepted,
        ut_exit_code=body.ut_exit_code,
    )
    db.add(row)
    try:
        await db.commit()
        await db.refresh(row)
        return row, status.HTTP_201_CREATED
    except IntegrityError:
        await db.rollback()
        logger.warning("UT 门禁上报 INSERT 唯一键冲突，进入重试比对: idempotency_key=%s", key)
        res2 = await db.execute(select(UtGateRun).where(UtGateRun.idempotency_key == key))
        row2 = res2.scalar_one_or_none()
        if row2 is None:
            logger.exception("UT 门禁上报唯一键冲突后未查询到记录: idempotency_key=%s", key)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="写入失败，请稍后重试",
            )
        if _payload_matches_existing_row(body, row2):
            return row2, status.HTTP_200_OK
        raise UtGateIdempotencyConflict()
