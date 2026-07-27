"""SNMP query helpers, using raw numeric OIDs rather than symbolic MIB
names. pysnmp can dynamically load MIB modules to resolve symbolic names
(e.g. `ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0)`), but that dynamic
import is exactly what PyInstaller's static analysis tends to miss when
freezing the backend (see the project plan's "Risks" section) — numeric
OIDs sidestep MIB compilation entirely, so there's nothing for PyInstaller
to miss.

No real SNMP-speaking hardware was available to test this against during
development; the OID table and response parsing follow the published MIB
definitions (RFC 1213 / IF-MIB / IEEE 802.1AB LLDP-MIB / Cisco CDP-MIB),
but should be treated as unverified against live devices until exercised
on a real network.
"""

from dataclasses import dataclass

from pysnmp.hlapi.v1arch.asyncio import ObjectIdentity, ObjectType, Slim

from app.core.logging import get_logger

logger = get_logger(__name__)

SNMP_PORT = 161
_BULK_MAX_REPETITIONS = 20
_WALK_MAX_ITERATIONS = 50  # hard cap so a misbehaving agent can't loop forever

# SNMPv2-MIB (RFC 1213 / RFC 3418)
OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_SYS_NAME = "1.3.6.1.2.1.1.5.0"

# IF-MIB (RFC 2863)
OID_IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
OID_IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"  # 1 = up, 2 = down

# LLDP-MIB (IEEE 802.1AB) — lldpRemTable, keyed by
# <lldpRemTimeMark>.<lldpRemLocalPortNum>.<lldpRemIndex>
OID_LLDP_REM_CHASSIS_ID_SUBTYPE = "1.0.8802.1.1.2.1.4.1.1.4"
OID_LLDP_REM_CHASSIS_ID = "1.0.8802.1.1.2.1.4.1.1.5"
OID_LLDP_REM_PORT_ID = "1.0.8802.1.1.2.1.4.1.1.7"
OID_LLDP_REM_SYS_NAME = "1.0.8802.1.1.2.1.4.1.1.9"
_LLDP_CHASSIS_SUBTYPE_MAC_ADDRESS = "4"

# CDP-MIB (Cisco proprietary) — fallback for gear with LLDP disabled
OID_CDP_CACHE_DEVICE_ID = "1.3.6.1.4.1.9.9.23.1.2.1.1.6"
OID_CDP_CACHE_DEVICE_PORT = "1.3.6.1.4.1.9.9.23.1.2.1.1.7"


@dataclass
class SnmpTarget:
    ip: str
    community: str
    timeout: int = 2
    retries: int = 1


@dataclass
class LldpNeighbor:
    chassis_id: str  # MAC-formatted when chassisIdSubtype=macAddress, else hex
    port_id: str
    sys_name: str | None


def _octets_to_display(raw: bytes) -> str:
    """Best-effort text for an OCTET STRING that may be binary (MAC bytes)
    or printable ASCII (interface names) — LLDP subtypes mix both."""
    try:
        text = raw.decode("ascii")
        if text.isprintable():
            return text
    except UnicodeDecodeError:
        pass
    return raw.hex()


def _octets_to_mac(raw: bytes) -> str:
    if len(raw) != 6:
        return raw.hex()
    return ":".join(f"{b:02x}" for b in raw)


async def snmp_get(target: SnmpTarget, oid: str) -> str | None:
    with Slim(2) as slim:
        error_indication, error_status, _, var_binds = await slim.get(
            target.community,
            target.ip,
            SNMP_PORT,
            ObjectType(ObjectIdentity(oid)),
            timeout=target.timeout,
            retries=target.retries,
        )
    if error_indication or error_status or not var_binds:
        return None
    return str(var_binds[0][1])


async def snmp_walk_octets(target: SnmpTarget, base_oid: str) -> dict[str, bytes]:
    """GETBULK-walk a subtree, returning {oid_suffix_after_base: raw_bytes}."""
    results: dict[str, bytes] = {}
    current_oid = base_oid
    with Slim(2) as slim:
        for _ in range(_WALK_MAX_ITERATIONS):
            error_indication, error_status, _, var_bind_table = await slim.bulk(
                target.community,
                target.ip,
                SNMP_PORT,
                0,
                _BULK_MAX_REPETITIONS,
                ObjectType(ObjectIdentity(current_oid)),
                timeout=target.timeout,
                retries=target.retries,
            )
            if error_indication or error_status or not var_bind_table:
                break

            reached_end = False
            last_oid = current_oid
            for var_bind in var_bind_table:
                oid_str = str(var_bind[0])
                if not oid_str.startswith(base_oid + "."):
                    # GETBULK returns strictly increasing OIDs, so once one
                    # row falls outside the subtree, every row after it does
                    # too — no need to keep scanning this batch.
                    reached_end = True
                    break
                raw_value = var_bind[1]
                results[oid_str[len(base_oid) + 1 :]] = (
                    raw_value.asOctets() if hasattr(raw_value, "asOctets") else str(raw_value).encode()
                )
                last_oid = oid_str

            if reached_end or last_oid == current_oid:
                break
            current_oid = last_oid
    return results


async def get_system_info(target: SnmpTarget) -> tuple[str | None, str | None]:
    """Returns (sysDescr, sysName)."""
    sys_descr = await snmp_get(target, OID_SYS_DESCR)
    sys_name = await snmp_get(target, OID_SYS_NAME)
    return sys_descr, sys_name


async def get_lldp_neighbors(target: SnmpTarget) -> list[LldpNeighbor]:
    chassis_subtypes = await snmp_walk_octets(target, OID_LLDP_REM_CHASSIS_ID_SUBTYPE)
    if not chassis_subtypes:
        return []
    chassis_ids = await snmp_walk_octets(target, OID_LLDP_REM_CHASSIS_ID)
    port_ids = await snmp_walk_octets(target, OID_LLDP_REM_PORT_ID)
    sys_names = await snmp_walk_octets(target, OID_LLDP_REM_SYS_NAME)

    neighbors = []
    for suffix, raw_chassis_id in chassis_ids.items():
        subtype = chassis_subtypes.get(suffix, b"").decode(errors="replace")
        chassis_id = (
            _octets_to_mac(raw_chassis_id)
            if subtype == _LLDP_CHASSIS_SUBTYPE_MAC_ADDRESS
            else _octets_to_display(raw_chassis_id)
        )
        raw_sys_name = sys_names.get(suffix)
        neighbors.append(
            LldpNeighbor(
                chassis_id=chassis_id,
                port_id=_octets_to_display(port_ids.get(suffix, b"")),
                sys_name=_octets_to_display(raw_sys_name) if raw_sys_name else None,
            )
        )
    return neighbors


async def get_cdp_neighbors(target: SnmpTarget) -> list[LldpNeighbor]:
    """CDP fallback for Cisco gear with LLDP disabled. Returned as
    LldpNeighbor too — the topology builder treats both uniformly since it
    only needs an identity (here, device ID rather than chassis MAC), a
    port, and a display name."""
    device_ids = await snmp_walk_octets(target, OID_CDP_CACHE_DEVICE_ID)
    device_ports = await snmp_walk_octets(target, OID_CDP_CACHE_DEVICE_PORT)

    neighbors = []
    for suffix, raw_device_id in device_ids.items():
        device_id = _octets_to_display(raw_device_id)
        neighbors.append(
            LldpNeighbor(
                chassis_id=device_id,
                port_id=_octets_to_display(device_ports.get(suffix, b"")),
                sys_name=device_id,
            )
        )
    return neighbors
