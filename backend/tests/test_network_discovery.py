import ipaddress
from unittest.mock import AsyncMock, patch

from app.services.network_discovery import (
    _parse_arp_output,
    get_local_ips,
    normalize_mac,
    read_arp_table,
    sweep_local_subnets,
)

MACOS_ARP_OUTPUT = """\
? (172.20.10.1) at f2:1f:c7:6b:ec:64 on en0 ifscope [ethernet]
? (172.20.10.3) at 2e:f3:12:b1:aa:49 on en0 ifscope permanent [ethernet]
? (172.20.10.15) at ff:ff:ff:ff:ff:ff on en0 ifscope [ethernet]
? (172.20.10.20) at (incomplete) on en0 ifscope [ethernet]
mdns.mcast.net (224.0.0.251) at 1:0:5e:0:0:fb on en0 ifscope permanent [ethernet]
"""

WINDOWS_ARP_OUTPUT = """\
Interface: 192.168.1.100 --- 0x3
  Internet Address      Physical Address      Type
  192.168.1.1            ac-22-05-ab-cd-ef     dynamic
  192.168.1.50            00-11-22-33-44-55     dynamic
  192.168.1.255          ff-ff-ff-ff-ff-ff     static
  224.0.0.22             01-00-5e-00-00-16     static
"""


def test_normalize_mac_pads_unix_style_octets() -> None:
    assert normalize_mac("1:0:5e:0:0:fb") == "01:00:5e:00:00:fb"


def test_normalize_mac_lowercases_and_keeps_colons() -> None:
    assert normalize_mac("AC:22:05:AB:CD:EF") == "ac:22:05:ab:cd:ef"


def test_normalize_mac_handles_windows_hyphens() -> None:
    assert normalize_mac("AC-22-05-AB-CD-EF") == "ac:22:05:ab:cd:ef"


def test_normalize_mac_handles_cisco_dot_notation() -> None:
    assert normalize_mac("0011.2233.4455") == "00:11:22:33:44:55"


def test_parse_macos_arp_output_excludes_broadcast_and_multicast() -> None:
    entries = _parse_arp_output(MACOS_ARP_OUTPUT)
    ips = {e.ip for e in entries}

    assert ips == {"172.20.10.1", "172.20.10.3"}
    assert "172.20.10.15" not in ips  # broadcast MAC
    assert "172.20.10.20" not in ips  # incomplete
    assert "224.0.0.251" not in ips  # multicast IP + multicast MAC


def test_parse_windows_arp_output_excludes_broadcast_and_multicast() -> None:
    entries = _parse_arp_output(WINDOWS_ARP_OUTPUT)
    ips = {e.ip for e in entries}

    assert ips == {"192.168.1.1", "192.168.1.50"}
    assert "192.168.1.255" not in ips
    assert "224.0.0.22" not in ips


def test_parse_arp_output_normalizes_macs() -> None:
    entries = _parse_arp_output(MACOS_ARP_OUTPUT)
    by_ip = {e.ip: e.mac for e in entries}

    assert by_ip["172.20.10.1"] == "f2:1f:c7:6b:ec:64"


def test_get_local_ips_excludes_loopback_and_non_ipv4() -> None:
    class _FakeFamily:
        def __init__(self, name: str) -> None:
            self.name = name

    class _FakeAddr:
        def __init__(self, family: str, address: str) -> None:
            self.family = _FakeFamily(family)
            self.address = address

    fake_interfaces = {
        "en0": [
            _FakeAddr("AF_INET", "172.20.10.3"),
            _FakeAddr("AF_INET6", "fe80::1"),
        ],
        "lo0": [_FakeAddr("AF_INET", "127.0.0.1")],
    }

    with patch(
        "app.services.network_discovery.psutil.net_if_addrs",
        return_value=fake_interfaces,
    ):
        assert get_local_ips() == {"172.20.10.3"}


async def test_read_arp_table_excludes_this_machines_own_ip() -> None:
    """macOS adds a "permanent" self-referential ARP entry for the
    interface's own IP (see get_local_ips' docstring) — this must not
    show up as a phantom second device in the discovered topology."""

    class _FakeProcess:
        returncode = 0

        async def communicate(self):
            return MACOS_ARP_OUTPUT.encode(), b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        return _FakeProcess()

    with (
        patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec),
        patch(
            "app.services.network_discovery.get_local_ips",
            return_value={"172.20.10.3"},
        ),
    ):
        entries = await read_arp_table()

    ips = {e.ip for e in entries}
    assert "172.20.10.3" not in ips  # this machine's own IP
    assert "172.20.10.1" in ips  # a real neighbor, still present


async def test_sweep_pings_every_host_in_a_small_subnet() -> None:
    small_subnet = ipaddress.IPv4Network("192.0.2.0/28")  # 14 usable hosts

    with (
        patch(
            "app.services.network_discovery.get_local_subnets",
            return_value=[small_subnet],
        ),
        patch(
            "app.services.network_discovery._ping_host", AsyncMock(return_value=None)
        ) as mock_ping,
    ):
        await sweep_local_subnets()

    assert mock_ping.await_count == 14


async def test_sweep_skips_subnets_larger_than_the_cap() -> None:
    huge_subnet = ipaddress.IPv4Network("10.0.0.0/16")  # 65534 usable hosts

    with (
        patch(
            "app.services.network_discovery.get_local_subnets",
            return_value=[huge_subnet],
        ),
        patch(
            "app.services.network_discovery._ping_host", AsyncMock(return_value=None)
        ) as mock_ping,
    ):
        await sweep_local_subnets()

    mock_ping.assert_not_called()
