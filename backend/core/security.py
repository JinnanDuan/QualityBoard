from datetime import datetime, timedelta
from typing import Optional

from jose import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

from backend.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def require_admin(token=Depends(bearer_scheme)) -> dict:
    """Dependency: require admin role. Placeholder implementation."""
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = verify_token(token.credentials)
    if payload.get("sub") not in settings.ADMIN_EMPLOYEE_IDS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return payload
