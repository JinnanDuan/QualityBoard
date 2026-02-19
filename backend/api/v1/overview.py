from fastapi import APIRouter

router = APIRouter(prefix="/overview", tags=["分组概览"])


@router.get("")
async def list_overview():
    return {"message": "TODO"}
