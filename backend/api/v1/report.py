from fastapi import APIRouter

router = APIRouter(prefix="/report", tags=["总结报告"])


@router.post("")
async def generate_report():
    return {"message": "TODO"}


@router.get("/{report_id}")
async def get_report(report_id: int):
    return {"message": "TODO"}
