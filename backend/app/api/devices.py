from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security.dependencies import require_role
from app.models.ping import PingResult
from app.models.user import User
from app.services.network_discovery import ping_once
from app.services.topology_cache import topology_cache

router = APIRouter(tags=["devices"])


@router.post("/devices/{device_id}/ping", response_model=PingResult)
async def ping_device(device_id: str, _: User = Depends(require_role("operator"))) -> PingResult:
    """Pings a single device on demand, for the Host Monitor tab.

    Requires operator (not just viewer) since — unlike GET /topology — this
    actively sends traffic at the caller's request. Takes a device_id from
    the cached topology rather than an arbitrary IP so this endpoint can't
    be used as a scanning proxy against hosts the tablet hasn't already
    discovered.
    """
    node = next((n for n in topology_cache.get().nodes if n.id == device_id), None)
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown device")
    if node.ip_address is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Device has no known IP address"
        )

    outcome = await ping_once(node.ip_address)
    return PingResult(success=outcome.success, latency_ms=outcome.latency_ms)
