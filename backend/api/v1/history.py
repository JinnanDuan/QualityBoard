from fastapi import APIRouter

router = APIRouter(prefix="/history", tags=["执行明细"])


@router.get("")
async def list_history():
    return {"message": "TODO"}
