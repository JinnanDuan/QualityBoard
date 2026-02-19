from fastapi import APIRouter

router = APIRouter(prefix="/cases", tags=["用例管理"])


@router.get("")
async def list_cases():
    return {"message": "TODO"}


@router.put("/{case_id}")
async def update_case(case_id: int):
    return {"message": "TODO"}
