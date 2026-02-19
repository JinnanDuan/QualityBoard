from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["看板"])


@router.get("/trend")
async def get_trend_data():
    return {"message": "TODO"}


@router.get("/stats")
async def get_stats_cards():
    return {"message": "TODO"}
