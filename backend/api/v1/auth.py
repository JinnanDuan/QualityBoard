from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login")
async def login():
    return {"message": "TODO"}


@router.post("/logout")
async def logout():
    return {"message": "TODO"}


@router.get("/me")
async def get_current_user_info():
    return {"message": "TODO"}
