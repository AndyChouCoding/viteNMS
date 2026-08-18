import ipaddress
from unittest.mock import AsyncMock, patch

from app.services.network_discovery import (
    _ping_host,
    _parse_arp_output,
    _parse_ping_rtt,
    get_local_ips,
    get_primary_local_address,
    normalize_mac,
    ping_once,
    read_arp_table,
    sweep_local_subnets,
)

MACOS_PING_SUCCESS_OUTPUT = """\
PING 172.20.10.1 (172.20.10.1): 56 data bytes
64 bytes from 172.20.10.1: icmp_seq=0 ttl=64 time=1.234 ms

--- 172.20.10.1 ping statistics ---
1 packets transmitted, 1 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 1.234/1.234/1.234/0.000 ms
"""

WINDOWS_PING_SUCCESS_OUTPUT = """\
Pinging 192.168.1.1 with 32 bytes of data:
Reply from 192.168.1.1: bytes=32 time=1ms TTL=64

Ping statistics for 192.168.1.1:
    Packets: Sent = 1, Received = 1, Lost = 0 (0% loss),
"""

WINDOWS_PING_SUBMILLISECOND_OUTPUT = """\
Reply from 192.168.1.1: bytes=32 time<1ms TTL=64
"""

# Traditional Chinese ping.exe output — the reply line's field labels are
# localized ("時間" instead of "time"), unlike the "=1ms"/"<1ms" value format.
WINDOWS_PING_SUCCESS_OUTPUT_ZH_TW = """\
正在使用 32 位元組的資料 Ping 192.168.1.1:
從 192.168.1.1 的回覆: 位元組=32 時間=1ms TTL=64

192.168.1.1 的 Ping 統計資料:
    封包: 已傳送 = 1，已收到 = 1，已遺失 = 0 (0% 遺失)，
"""

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


def test_get_primary_local_address_pairs_ip_with_its_interfaces_mac() -> None:
    class _FakeFamily:
        def __init__(self, name: str) -> None:
            self.name = name

    class _FakeAddr:
        def __init__(self, family: str, address: str) -> None:
            self.family = _FakeFamily(family)
            self.address = address

    fake_interfaces = {
        "lo0": [_FakeAddr("AF_INET", "127.0.0.1")],
        "en0": [
            _FakeAddr("AF_INET", "172.20.10.3"),
            _FakeAddr("AF_LINK", "2e:f3:12:b1:aa:49"),
            _FakeAddr("AF_INET6", "fe80::1"),
        ],
    }

    with patch(
        "app.services.network_discovery.psutil.net_if_addrs",
        return_value=fake_interfaces,
    ):
        ip, mac = get_primary_local_address()

    assert ip == "172.20.10.3"
    assert mac == "2e:f3:12:b1:aa:49"


def test_get_local_ips_excludes_link_local_apipa_addresses() -> None:
    class _FakeFamily:
        def __init__(self, name: str) -> None:
            self.name = name

    class _FakeAddr:
        def __init__(self, family: str, address: str) -> None:
            self.family = _FakeFamily(family)
            self.address = address

    fake_interfaces = {
        # A disabled/unplugged adapter Windows assigned an APIPA address to.
        "vEthernet": [_FakeAddr("AF_INET", "169.254.83.12")],
        "en0": [_FakeAddr("AF_INET", "172.20.10.3")],
    }

    with patch(
        "app.services.network_discovery.psutil.net_if_addrs",
        return_value=fake_interfaces,
    ):
        assert get_local_ips() == {"172.20.10.3"}


def test_get_primary_local_address_skips_link_local_interfaces() -> None:
    class _FakeFamily:
        def __init__(self, name: str) -> None:
            self.name = name

    class _FakeAddr:
        def __init__(self, family: str, address: str) -> None:
            self.family = _FakeFamily(family)
            self.address = address

    fake_interfaces = {
        # Enumerated before the real adapter — must not win just by being first.
        "vEthernet": [_FakeAddr("AF_INET", "169.254.83.12")],
        "en0": [
            _FakeAddr("AF_INET", "172.20.10.3"),
            _FakeAddr("AF_LINK", "2e:f3:12:b1:aa:49"),
        ],
    }

    with patch(
        "app.services.network_discovery.psutil.net_if_addrs",
        return_value=fake_interfaces,
    ):
        ip, mac = get_primary_local_address()

    assert ip == "172.20.10.3"
    assert mac == "2e:f3:12:b1:aa:49"


def test_get_primary_local_address_returns_none_pair_without_a_nonloopback_ipv4() -> None:
    class _FakeFamily:
        def __init__(self, name: str) -> None:
            self.name = name

    class _FakeAddr:
        def __init__(self, family: str, address: str) -> None:
            self.family = _FakeFamily(family)
            self.address = address

    fake_interfaces = {"lo0": [_FakeAddr("AF_INET", "127.0.0.1")]}

    with patch(
        "app.services.network_discovery.psutil.net_if_addrs",
        return_value=fake_interfaces,
    ):
        assert get_primary_local_address() == (None, None)


async def test_read_arp_table_skips_reverse_dns_on_macos_and_linux() -> None:
    """Regression test: non-Windows `arp -a` resolves each entry's hostname
    via reverse DNS before printing, which can take several seconds on
    networks without local reverse DNS — enough to blow past the read
    timeout and silently return zero entries every time. `-n` skips that
    lookup; we only need the IP/MAC pairs."""
    captured_args = []

    class _FakeProcess:
        returncode = 0

        async def communicate(self):
            return MACOS_ARP_OUTPUT.encode(), b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured_args.extend(args)
        return _FakeProcess()

    with (
        patch("app.services.network_discovery.platform.system", return_value="Darwin"),
        patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec),
    ):
        await read_arp_table()

    assert captured_args == ["arp", "-an"]


async def test_read_arp_table_uses_plain_flag_on_windows() -> None:
    """Windows' `arp -a` doesn't do reverse DNS and doesn't accept `-n`
    the same way non-Windows arp does, so it's left unmodified."""
    captured_args = []

    class _FakeProcess:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured_args.extend(args)
        return _FakeProcess()

    with (
        patch("app.services.network_discovery.platform.system", return_value="Windows"),
        patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec),
    ):
        await read_arp_table()

    assert captured_args == ["arp", "-a"]


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


def test_parse_ping_rtt_from_macos_output() -> None:
    assert _parse_ping_rtt(MACOS_PING_SUCCESS_OUTPUT) == 1.234


def test_parse_ping_rtt_from_windows_output() -> None:
    assert _parse_ping_rtt(WINDOWS_PING_SUCCESS_OUTPUT) == 1.0


def test_parse_ping_rtt_handles_windows_submillisecond_replies() -> None:
    assert _parse_ping_rtt(WINDOWS_PING_SUBMILLISECOND_OUTPUT) == 1.0


def test_parse_ping_rtt_from_localized_windows_output() -> None:
    assert _parse_ping_rtt(WINDOWS_PING_SUCCESS_OUTPUT_ZH_TW) == 1.0


def test_parse_ping_rtt_returns_none_when_no_reply_line_present() -> None:
    assert _parse_ping_rtt("Request timeout for icmp_seq 0") is None


async def test_ping_once_uses_millisecond_wait_time_on_macos() -> None:
    """Regression test: BSD/macOS ping's -W is milliseconds, not seconds like
    Linux's iputils. Passing a bare "2" (meant as 2 seconds) makes macOS wait
    only 2ms per packet — real replies arrive later, so the process still
    exits 0 but the per-packet "time=" line (which _parse_ping_rtt needs)
    never prints, silently turning every successful ping into a
    success-with-no-latency result."""
    captured_args = []

    class _FakeProcess:
        returncode = 0

        async def communicate(self):
            return MACOS_PING_SUCCESS_OUTPUT.encode(), b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured_args.extend(args)
        return _FakeProcess()

    with (
        patch("app.services.network_discovery.platform.system", return_value="Darwin"),
        patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec),
    ):
        await ping_once("172.20.10.1")

    assert "-W" in captured_args
    wait_value = captured_args[captured_args.index("-W") + 1]
    assert int(wait_value) >= 1000  # milliseconds, not seconds


async def test_ping_once_uses_second_wait_time_on_linux() -> None:
    captured_args = []

    class _FakeProcess:
        returncode = 0

        async def communicate(self):
            return MACOS_PING_SUCCESS_OUTPUT.encode(), b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured_args.extend(args)
        return _FakeProcess()

    with (
        patch("app.services.network_discovery.platform.system", return_value="Linux"),
        patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec),
    ):
        await ping_once("172.20.10.1")

    assert "-W" in captured_args
    wait_value = captured_args[captured_args.index("-W") + 1]
    assert int(wait_value) < 1000  # seconds, not milliseconds


async def test_ping_host_uses_millisecond_wait_time_on_macos() -> None:
    """Same BSD/macOS -W-is-milliseconds unit as ping_once, in the
    fire-and-forget sweep ping used to nudge ARP entries into existence.
    Doesn't affect whether an entry gets recorded (that happens as soon as
    the OS sends the ARP request, before this process ever sees a reply),
    but "-W 1" silently meaning 1ms instead of 1s was still worth fixing
    for consistency."""
    captured_args = []

    class _FakeProcess:
        returncode = 0

        async def wait(self):
            return 0

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured_args.extend(args)
        return _FakeProcess()

    with (
        patch("app.services.network_discovery.platform.system", return_value="Darwin"),
        patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec),
    ):
        await _ping_host("172.20.10.1")

    assert "-W" in captured_args
    wait_value = captured_args[captured_args.index("-W") + 1]
    assert int(wait_value) >= 1000  # milliseconds, not seconds


async def test_ping_host_uses_second_wait_time_on_linux() -> None:
    captured_args = []

    class _FakeProcess:
        returncode = 0

        async def wait(self):
            return 0

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured_args.extend(args)
        return _FakeProcess()

    with (
        patch("app.services.network_discovery.platform.system", return_value="Linux"),
        patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec),
    ):
        await _ping_host("172.20.10.1")

    assert "-W" in captured_args
    wait_value = captured_args[captured_args.index("-W") + 1]
    assert int(wait_value) < 1000  # seconds, not milliseconds


async def test_ping_once_reports_success_and_latency() -> None:
    class _FakeProcess:
        returncode = 0

        async def communicate(self):
            return MACOS_PING_SUCCESS_OUTPUT.encode(), b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        return _FakeProcess()

    with patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec):
        outcome = await ping_once("172.20.10.1")

    assert outcome.success is True
    assert outcome.latency_ms == 1.234


async def test_ping_once_reports_failure_on_nonzero_exit() -> None:
    class _FakeProcess:
        returncode = 2

        async def communicate(self):
            return b"", b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        return _FakeProcess()

    with patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec):
        outcome = await ping_once("192.0.2.1")

    assert outcome.success is False
    assert outcome.latency_ms is None


async def test_ping_once_reports_failure_on_timeout() -> None:
    async def fake_create_subprocess_exec(*args, **kwargs):
        raise TimeoutError

    with patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec):
        outcome = await ping_once("192.0.2.1")

    assert outcome.success is False
    assert outcome.latency_ms is None


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
