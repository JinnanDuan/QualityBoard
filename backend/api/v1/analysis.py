from fastapi import APIRouter

router = APIRouter(prefix="/analysis", tags=["失败分析"])


@router.get("")
async def list_analysis():
    return {"message": "TODO"}


@router.post("")
async def create_analysis():
    return {"message": "TODO"}
