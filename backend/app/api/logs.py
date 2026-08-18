from fastapi import APIRouter, Depends

from app.core.security.dependencies import require_role
from app.models.log import LogEntry
from app.models.user import User
from app.services import log_service

router = APIRouter(tags=["logs"])


@router.get("/logs", response_model=list[LogEntry])
async def get_logs(_: User = Depends(require_role("viewer"))) -> list[LogEntry]:
    return await log_service.list_events()
