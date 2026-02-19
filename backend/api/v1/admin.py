from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["管理员后台"])


@router.get("/users")
async def list_users():
    return {"message": "TODO"}


@router.get("/modules")
async def list_modules():
    return {"message": "TODO"}


@router.get("/dict/failed-types")
async def list_failed_types():
    return {"message": "TODO"}


@router.get("/dict/offline-types")
async def list_offline_types():
    return {"message": "TODO"}
