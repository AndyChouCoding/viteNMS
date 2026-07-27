from fastapi import APIRouter

from app.models.topology import TopologyGraph
from app.services.snmp_service import get_stub_topology

router = APIRouter(tags=["topology"])


@router.get("/topology", response_model=TopologyGraph)
async def get_topology() -> TopologyGraph:
    return await get_stub_topology()
