import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security.dependencies import bearer_scheme, get_current_user, require_role
from app.models.user import CreateUserRequest, LoginRequest, LoginResponse, User
from app.services import auth_service, log_service

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
        await log_service.record_event(
            "Login Failed", f"Failed login attempt for username '{request.username}'"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password"
        )
    token, _ = await auth_service.create_session(user.id)
    await log_service.record_event("Login", f"{user.username} logged in")
    return LoginResponse(token=token, user=user)


@router.post("/logout")
async def logout(
    user: User = Depends(get_current_user),  # rejects already-invalid/expired tokens with 401
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    await auth_service.delete_session(credentials.credentials)
    await log_service.record_event("Logout", f"{user.username} logged out")
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


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current: User = Depends(require_role("admin")),
) -> None:
    target = await auth_service.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    # Deleting the only account entirely just resets to a fresh "needs
    # bootstrap" state, which is fine. What's not fine is deleting the last
    # admin while other (non-admin) accounts remain — those would be
    # permanently orphaned, since bootstrap only ever fires on an empty
    # table and creating new users requires an existing admin.
    if (
        target.role == "admin"
        and await auth_service.count_admins() <= 1
        and await auth_service.count_users() > 1
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete the last admin account while other accounts remain",
        )
    await auth_service.delete_user(user_id)
    await log_service.record_event(
        "User Deleted", f"{current.username} deleted user '{target.username}'"
    )
