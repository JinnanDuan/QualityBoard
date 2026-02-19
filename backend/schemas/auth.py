from typing import Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    employee_id: str
    password: str


class UserInfo(BaseModel):
    employee_id: str
    name: str
    email: str
    role: str

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class CurrentUserResponse(BaseModel):
    employee_id: str
    name: str
    email: str
    domain_account: Optional[str] = None
    role: str

    model_config = {"from_attributes": True}
