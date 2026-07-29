"""Unit tests for SNMP parsing logic, mocked against pysnmp's Slim API.

No real SNMP-speaking hardware is available in this dev environment, so
these tests verify the OID-suffix bookkeeping and LLDP chassis-ID subtype
handling against hand-built responses shaped like real wire data (per the
published LLDP-MIB), rather than against a live device.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.snmp_service import (
    OID_IF_DESCR,
    OID_LLDP_REM_CHASSIS_ID,
    SnmpTarget,
    _octets_to_display,
    _octets_to_mac,
    get_cdp_neighbors,
    get_lldp_neighbors,
    snmp_walk_octets,
)


class _FakeOid:
    def __init__(self, oid: str) -> None:
        self._oid = oid

    def __str__(self) -> str:
        return self._oid


class _FakeOctetString:
    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    def asOctets(self) -> bytes:
        return self._raw

    def __str__(self) -> str:
        return self._raw.decode(errors="replace")


def test_octets_to_mac_formats_six_bytes() -> None:
    assert _octets_to_mac(b"\x00\x11\x22\x33\x44\x55") == "00:11:22:33:44:55"


def test_octets_to_mac_falls_back_to_hex_for_non_mac_length() -> None:
    assert _octets_to_mac(b"\x01\x02\x03") == "010203"


def test_octets_to_display_decodes_printable_ascii() -> None:
    assert _octets_to_display(b"GigabitEthernet0/1") == "GigabitEthernet0/1"


def test_octets_to_display_hex_falls_back_for_binary() -> None:
    assert _octets_to_display(b"\x00\x11\x22\x33\x44\x55") == "001122334455"


@pytest.mark.asyncio
async def test_snmp_walk_octets_stops_at_subtree_boundary() -> None:
    base = OID_LLDP_REM_CHASSIS_ID
    first_batch = (
        None,
        0,
        0,
        [
            (_FakeOid(f"{base}.0.1.1"), _FakeOctetString(b"\x00\x11\x22\x33\x44\x55")),
            (_FakeOid(f"{base}.0.2.1"), _FakeOctetString(b"\x00\x11\x22\x33\x44\x66")),
            # Walked past the subtree — next OID belongs to a different column
            (_FakeOid("1.0.8802.1.1.2.1.4.1.1.6.0.2.1"), _FakeOctetString(b"x")),
        ],
    )

    mock_slim = AsyncMock()
    mock_slim.bulk.return_value = first_batch

    with patch("app.services.snmp_service.Slim") as mock_slim_cls:
        mock_slim_cls.return_value.__enter__.return_value = mock_slim
        target = SnmpTarget(ip="192.0.2.10", community="public")
        result = await snmp_walk_octets(target, base)

    assert result == {
        "0.1.1": b"\x00\x11\x22\x33\x44\x55",
        "0.2.1": b"\x00\x11\x22\x33\x44\x66",
    }
    # Only one bulk call: the third row wasn't under base_oid, so nothing
    # "advanced" the walk on that row, but two rows did before it — the
    # loop should still terminate rather than retry forever.
    assert mock_slim.bulk.await_count == 1


@pytest.mark.asyncio
async def test_get_lldp_neighbors_uses_mac_formatting_for_subtype_4() -> None:
    async def fake_walk(target, base_oid):
        # lldpRemTable's index is <timeMark>.<localPortNum>.<remIndex> —
        # "0.1.1" means localPortNum=1, resolved via ifDescr below.
        suffix = "0.1.1"
        return {
            "1.0.8802.1.1.2.1.4.1.1.4": {suffix: b"4"},  # chassisIdSubtype=macAddress
            "1.0.8802.1.1.2.1.4.1.1.5": {suffix: b"\x00\x11\x22\x33\x44\x55"},
            "1.0.8802.1.1.2.1.4.1.1.7": {suffix: b"Gi0/1"},
            "1.0.8802.1.1.2.1.4.1.1.9": {suffix: b"switch-b"},
            OID_IF_DESCR: {"1": b"GigabitEthernet0/1"},
        }[base_oid]

    with patch("app.services.snmp_service.snmp_walk_octets", side_effect=fake_walk):
        target = SnmpTarget(ip="192.0.2.10", community="public")
        neighbors = await get_lldp_neighbors(target)

    assert len(neighbors) == 1
    assert neighbors[0].chassis_id == "00:11:22:33:44:55"
    assert neighbors[0].port_id == "Gi0/1"
    assert neighbors[0].sys_name == "switch-b"
    assert neighbors[0].local_port == "GigabitEthernet0/1"


@pytest.mark.asyncio
async def test_get_lldp_neighbors_falls_back_to_raw_index_when_ifdescr_missing() -> None:
    async def fake_walk(target, base_oid):
        suffix = "0.7.1"
        return {
            "1.0.8802.1.1.2.1.4.1.1.4": {suffix: b"4"},
            "1.0.8802.1.1.2.1.4.1.1.5": {suffix: b"\x00\x11\x22\x33\x44\x55"},
            "1.0.8802.1.1.2.1.4.1.1.7": {suffix: b"Gi0/1"},
            "1.0.8802.1.1.2.1.4.1.1.9": {suffix: b"switch-b"},
            OID_IF_DESCR: {},  # agent didn't return a name for ifIndex 7
        }[base_oid]

    with patch("app.services.snmp_service.snmp_walk_octets", side_effect=fake_walk):
        target = SnmpTarget(ip="192.0.2.10", community="public")
        neighbors = await get_lldp_neighbors(target)

    assert neighbors[0].local_port == "7"


@pytest.mark.asyncio
async def test_get_lldp_neighbors_returns_empty_when_agent_has_no_lldp() -> None:
    with patch("app.services.snmp_service.snmp_walk_octets", AsyncMock(return_value={})):
        target = SnmpTarget(ip="192.0.2.10", community="public")
        neighbors = await get_lldp_neighbors(target)

    assert neighbors == []


@pytest.mark.asyncio
async def test_get_cdp_neighbors_resolves_local_port_from_ifindex_prefix() -> None:
    async def fake_walk(target, base_oid):
        # cdpCacheTable's index is <ifIndex>.<deviceIndex> — "3.1" means
        # ifIndex=3, resolved via ifDescr below.
        suffix = "3.1"
        return {
            "1.3.6.1.4.1.9.9.23.1.2.1.1.6": {suffix: b"switch-c"},
            "1.3.6.1.4.1.9.9.23.1.2.1.1.7": {suffix: b"Gi0/2"},
            OID_IF_DESCR: {"3": b"GigabitEthernet0/3"},
        }[base_oid]

    with patch("app.services.snmp_service.snmp_walk_octets", side_effect=fake_walk):
        target = SnmpTarget(ip="192.0.2.10", community="public")
        neighbors = await get_cdp_neighbors(target)

    assert len(neighbors) == 1
    assert neighbors[0].chassis_id == "switch-c"
    assert neighbors[0].port_id == "Gi0/2"
    assert neighbors[0].local_port == "GigabitEthernet0/3"
