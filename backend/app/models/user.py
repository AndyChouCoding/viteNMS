from typing import Literal

from pydantic import BaseModel

Role = Literal["viewer", "operator", "admin"]

_ROLE_RANK: dict[Role, int] = {"viewer": 0, "operator": 1, "admin": 2}


def role_at_least(role: Role, minimum: Role) -> bool:
    return _ROLE_RANK[role] >= _ROLE_RANK[minimum]


class User(BaseModel):
    """Public user representation — never carries the password hash."""

    id: int
    username: str
    role: Role


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: User


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: Role
