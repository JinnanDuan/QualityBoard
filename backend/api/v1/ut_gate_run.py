import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user, verify_ut_gate_integration_token
from backend.schemas.common import PageResponse
from backend.schemas.ut_gate_run import UtGateRunCreate, UtGateRunItem, UtGateRunQuery
from backend.services.ut_gate_run_service import UtGateIdempotencyConflict, create_ut_gate_run, list_ut_gate_runs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ut-gate-runs", tags=["UT门禁上报"])


@router.get(
    "",
    response_model=PageResponse[UtGateRunItem],
    summary="分页查询 UT 门禁上报记录",
    description="筛选 `reported_at` 使用 `start_time`/`end_time`（与 History 批次 `start_time` 无关）。规约见 `spec/17_ut_gate_runs_get_api_spec.md`。",
)
async def get_ut_gate_runs(
    query: UtGateRunQuery = Depends(),
    db: AsyncSession = Depends(get_db),
    _payload: dict = Depends(get_current_user),
):
    rows, total = await list_ut_gate_runs(db, query)
    return PageResponse(
        items=[UtGateRunItem.model_validate(r) for r in rows],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


@router.post(
    "",
    response_model=UtGateRunItem,
    response_model_exclude_none=False,
    responses={
        200: {"description": "幂等键已存在且内容一致（spec/16 §5.2）"},
        201: {"description": "新建记录"},
        409: {"description": "幂等键已存在且请求内容不一致"},
    },
    summary="上报 UT 门禁单次构建结果",
    description="实现规约见 `spec/16_ut_gate_report_post_api_spec.md`。",
)
async def post_ut_gate_run(
    body: UtGateRunCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_ut_gate_integration_token),
):
    try:
        row, http_status = await create_ut_gate_run(db, body)
    except UtGateIdempotencyConflict:
        logger.warning(
            "UT 门禁上报幂等冲突 idempotency_key=%s job_name=%s build_number=%s",
            body.idempotency_key,
            body.job_name,
            body.build_number,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="幂等键已存在且请求内容不一致",
        )

    logger.info(
        "UT 门禁上报成功 http_status=%s id=%s idempotency_key=%s job_name=%s build_number=%s",
        http_status,
        row.id,
        body.idempotency_key,
        body.job_name,
        body.build_number,
    )
    payload = UtGateRunItem.model_validate(row).model_dump(mode="json")
    return JSONResponse(status_code=http_status, content=payload)
