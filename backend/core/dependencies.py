from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import verify_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db_session() -> AsyncSession:  # type: ignore[misc]
    async with get_db() as session:
        yield session


async def get_current_user(token=Depends(bearer_scheme)) -> dict:
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return verify_token(token.credentials)
