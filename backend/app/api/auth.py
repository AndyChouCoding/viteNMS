import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security.dependencies import bearer_scheme, get_current_user, require_role
from app.models.user import CreateUserRequest, LoginRequest, LoginResponse, User
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/bootstrap-status")
async def bootstrap_status() -> dict:
    """Public — the frontend uses this to decide whether to show the
    login form or the one-time "create the first admin account" form."""
    return {"needs_bootstrap": not await auth_service.has_any_user()}


@router.post("/bootstrap", response_model=LoginResponse)
async def bootstrap(request: CreateUserRequest) -> LoginResponse:
    """Creates the first account, as an admin, and logs it in immediately.
    Only usable while the users table is empty — this is a one-time,
    unauthenticated setup step for a freshly-deployed tablet, not an
    open registration endpoint."""
    if await auth_service.has_any_user():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Setup already completed"
        )
    user = await auth_service.create_user(request.username, request.password, "admin")
    token, _ = await auth_service.create_session(user.id)
    return LoginResponse(token=token, user=user)


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    user = await auth_service.authenticate(request.username, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password"
        )
    token, _ = await auth_service.create_session(user.id)
    return LoginResponse(token=token, user=user)


@router.post("/logout")
async def logout(
    _: User = Depends(get_current_user),  # rejects already-invalid/expired tokens with 401
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    await auth_service.delete_session(credentials.credentials)
    return {"status": "ok"}


@router.get("/me", response_model=User)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: CreateUserRequest,
    _: User = Depends(require_role("admin")),
) -> User:
    try:
        return await auth_service.create_user(request.username, request.password, request.role)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already exists"
        ) from exc
