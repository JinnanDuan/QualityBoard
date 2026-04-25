import json
import logging
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.history_search_template import HistorySearchTemplate
from backend.schemas.history import HistoryQuery
from backend.schemas.history_search_template import HistorySearchTemplateCreate, HistorySearchTemplateItem

logger = logging.getLogger(__name__)

MAX_TEMPLATES_PER_USER = 10


async def list_search_templates(db: AsyncSession, employee_id: str) -> List[HistorySearchTemplateItem]:
    if not employee_id or not str(employee_id).strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    eid = str(employee_id).strip()
    stmt = (
        select(HistorySearchTemplate)
        .where(HistorySearchTemplate.employee_id == eid)
        .order_by(HistorySearchTemplate.updated_at.desc(), HistorySearchTemplate.id.desc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    items: List[HistorySearchTemplateItem] = []
    for row in rows:
        try:
            raw = json.loads(row.query_json)
            q = HistoryQuery.model_validate(raw)
        except Exception:
            logger.exception("搜索模板 query_json 解析失败 template_id=%s", row.id)
            continue
        items.append(
            HistorySearchTemplateItem(
                id=int(row.id),
                name=row.name,
                query_params=q,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        )
    return items


async def create_search_template(
    db: AsyncSession, employee_id: str, body: HistorySearchTemplateCreate
) -> HistorySearchTemplateItem:
    if not employee_id or not str(employee_id).strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    eid = str(employee_id).strip()
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="模板名称不能为空")

    cnt_stmt = select(func.count()).select_from(HistorySearchTemplate).where(HistorySearchTemplate.employee_id == eid)
    cnt_result = await db.execute(cnt_stmt)
    count_val = int(cnt_result.scalar_one() or 0)
    if count_val >= MAX_TEMPLATES_PER_USER:
        logger.warning("用户搜索模板已达上限 employee_id=%s count=%s", eid, count_val)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="模板已达上限，请先删除模板",
        )

    payload = body.query_params.model_dump(mode="json")
    row = HistorySearchTemplate(
        employee_id=eid,
        name=name,
        query_json=json.dumps(payload, ensure_ascii=False),
    )
    db.add(row)
    try:
        await db.commit()
        await db.refresh(row)
    except IntegrityError:
        await db.rollback()
        logger.warning("搜索模板名称重复 employee_id=%s name=%s", eid, name)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="模板名称已存在！",
        )
    except Exception:
        await db.rollback()
        logger.exception("创建搜索模板失败 employee_id=%s", eid)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="保存失败")

    logger.info("已创建历史搜索模板 id=%s employee_id=%s name=%s", row.id, eid, name)
    return HistorySearchTemplateItem(
        id=int(row.id),
        name=row.name,
        query_params=body.query_params,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def delete_search_template(db: AsyncSession, employee_id: str, template_id: int) -> None:
    if not employee_id or not str(employee_id).strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    eid = str(employee_id).strip()
    stmt = delete(HistorySearchTemplate).where(
        and_(
            HistorySearchTemplate.id == template_id,
            HistorySearchTemplate.employee_id == eid,
        )
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    await db.commit()
    logger.info("已删除历史搜索模板 id=%s employee_id=%s", template_id, eid)
