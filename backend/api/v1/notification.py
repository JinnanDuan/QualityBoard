from fastapi import APIRouter

router = APIRouter(prefix="/notification", tags=["通知"])


@router.get("/config")
async def get_notification_config():
    return {"message": "TODO"}


@router.post("/send")
async def send_notification():
    return {"message": "TODO"}
