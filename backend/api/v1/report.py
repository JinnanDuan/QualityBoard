from fastapi import APIRouter, Depends

from backend.core.security import require_admin

router = APIRouter(prefix="/report", tags=["总结报告"])


@router.post("")
async def generate_report(_: dict = Depends(require_admin)):
    return {"message": "TODO"}


@router.get("/{report_id}")
async def get_report(report_id: int, _: dict = Depends(require_admin)):
    return {"message": "TODO"}
