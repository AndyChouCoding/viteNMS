"""In-memory topology cache, kept fresh by a periodic background task.

The API layer (app/api/topology.py) always serves from this cache rather
than running a live SNMP walk per request — a full discovery pass can take
several seconds per hop, which isn't acceptable request latency, and this
is meant to be a continuously-monitoring on-site device, not an on-demand
scanner.
"""

import asyncio

from app.core.config import settings
from app.core.logging import get_logger
from app.models.topology import TopologyGraph
from app.services import log_service
from app.services.topology_builder import discover_topology

logger = get_logger(__name__)


def _describe(node) -> str:
    return f"{node.label} ({node.ip_address})" if node.ip_address else node.label


class TopologyCache:
    def __init__(self) -> None:
        # Reference reassignment is atomic under the GIL, so readers always
        # see a fully-formed graph — no lock needed for this single field.
        self._graph = TopologyGraph(nodes=[], edges=[], source="uninitialized")
        self._task: asyncio.Task | None = None

    def get(self) -> TopologyGraph:
        return self._graph

    async def _poll_loop(self) -> None:
        while True:
            try:
                previous = self._graph
                new_graph = await discover_topology()
                # Skip logging transitions against the very first poll (an
                # empty "uninitialized" placeholder) — otherwise every
                # startup would log every discovered device as a fresh
                # "connected" event instead of only real state changes.
                if previous.source != "uninitialized":
                    await self._log_transitions(previous, new_graph)
                self._graph = new_graph
                logger.info("topology_poll_complete", node_count=len(self._graph.nodes))
            except Exception as exc:  # noqa: BLE001 - a single bad poll must not kill
                # the loop; the device is meant to keep monitoring indefinitely.
                logger.warning("topology_poll_failed", error=str(exc))
            await asyncio.sleep(settings.TOPOLOGY_POLL_INTERVAL_SECONDS)

    async def _log_transitions(self, previous: TopologyGraph, current: TopologyGraph) -> None:
        previous_ids = {n.id for n in previous.nodes}
        current_by_id = {n.id: n for n in current.nodes}

        for connected_id in current_by_id.keys() - previous_ids:
            await log_service.record_event(
                "Device Connected", f"{_describe(current_by_id[connected_id])} joined the network"
            )

        previous_by_id = {n.id: n for n in previous.nodes}
        for disconnected_id in previous_ids - current_by_id.keys():
            await log_service.record_event(
                "Device Disconnected",
                f"{_describe(previous_by_id[disconnected_id])} left the network",
            )

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None


topology_cache = TopologyCache()
