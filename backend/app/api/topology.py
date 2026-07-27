from fastapi import APIRouter

from app.models.topology import TopologyGraph
from app.services.topology_cache import topology_cache

router = APIRouter(tags=["topology"])


@router.get("/topology", response_model=TopologyGraph)
async def get_topology() -> TopologyGraph:
    """Serves the latest cached discovery pass — see topology_cache.py for
    why this doesn't run a live SNMP walk per request."""
    return topology_cache.get()
