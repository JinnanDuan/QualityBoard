from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.schemas.auth import CurrentUserResponse, LoginRequest, LoginResponse
from backend.services.auth_service import authenticate_user, get_user_info

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=LoginResponse)
async def login(login_req: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await authenticate_user(db, login_req)


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_info(
    payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_user_info(db, payload["sub"])


@router.post("/logout")
async def logout(payload: dict = Depends(get_current_user)):
    return {"message": "退出成功"}
