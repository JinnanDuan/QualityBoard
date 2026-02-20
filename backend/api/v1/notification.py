from fastapi import APIRouter, Depends

from backend.core.security import require_admin

router = APIRouter(prefix="/notification", tags=["通知"])


@router.get("/config")
async def get_notification_config(_: dict = Depends(require_admin)):
    return {"message": "TODO"}


@router.post("/send")
async def send_notification(_: dict = Depends(require_admin)):
    return {"message": "TODO"}
