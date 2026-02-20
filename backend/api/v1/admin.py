from fastapi import APIRouter, Depends

from backend.core.security import require_admin

router = APIRouter(prefix="/admin", tags=["管理员后台"])


@router.get("/users")
async def list_users(_: dict = Depends(require_admin)):
    return {"message": "TODO"}


@router.get("/modules")
async def list_modules(_: dict = Depends(require_admin)):
    return {"message": "TODO"}


@router.get("/dict/failed-types")
async def list_failed_types(_: dict = Depends(require_admin)):
    return {"message": "TODO"}


@router.get("/dict/offline-types")
async def list_offline_types(_: dict = Depends(require_admin)):
    return {"message": "TODO"}
