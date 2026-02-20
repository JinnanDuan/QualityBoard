from fastapi import APIRouter, Depends

from backend.core.security import require_admin

router = APIRouter(prefix="/cases", tags=["用例管理"])


@router.get("")
async def list_cases(_: dict = Depends(require_admin)):
    return {"message": "TODO"}


@router.put("/{case_id}")
async def update_case(case_id: int, _: dict = Depends(require_admin)):
    return {"message": "TODO"}
