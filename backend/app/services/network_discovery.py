"""Local network detection and ARP cache reading.

Deliberately avoids raw sockets: everything here shells out to OS
utilities the platform already ships (`arp`, `ping`) rather than opening
sockets directly in this process. See the IEC 62443 minimal-privilege note
in the project README — v1.0.0's discovery needs no elevated privilege
for *this* process, unlike the future Npcap-based diagnostic module (the
OS ping/arp binaries may themselves hold raw-socket capability, but that's
privilege already granted to the platform, not something we escalate to).

`read_arp_table()` alone is purely passive: the OS ARP cache only holds
entries for hosts this machine has actually exchanged traffic with, so a
device that's present on the LAN but has never talked to this host won't
show up. `sweep_local_subnets()` addresses that by pinging every host in
the (small) locally-attached subnets first, which prompts the OS to
populate ARP entries for them — a light, capped, active step rather than
a full passive/active split, but still no raw sockets of our own.

ARP reads shell out to the platform's `arp -a` rather than using a
Windows-specific ctypes/GetIpNetTable call, so this module behaves the same
in dev (macOS/Linux) as on the Windows deployment target — only the output
format differs, which `_parse_arp_line` handles per-platform.
"""

import asyncio
import ipaddress
import platform
import re

import psutil

from app.core.logging import get_logger

logger = get_logger(__name__)

_ARP_LINE_UNIX = re.compile(
    r"\((?P<ip>\d{1,3}(?:\.\d{1,3}){3})\)\s+at\s+(?P<mac>[0-9a-fA-F:.-]+)"
)
_ARP_LINE_WINDOWS = re.compile(
    r"^\s*(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+"
    r"(?P<mac>[0-9a-fA-F-]{17})\s+\S+\s*$"
)


class ArpEntry:
    def __init__(self, ip: str, mac: str):
        self.ip = ip
        self.mac = normalize_mac(mac)

    def __repr__(self) -> str:
        return f"ArpEntry(ip={self.ip!r}, mac={self.mac!r})"


def normalize_mac(mac: str) -> str:
    """Normalize aa:bb:.. / aa-bb-.. / aabb.ccdd.eeff into aa:bb:cc:dd:ee:ff.

    Groups are padded individually, not the concatenated string — BSD/macOS
    `arp -a` omits leading zeros per octet (e.g. "1:0:5e:0:0:fb"), so
    padding the whole string first would misalign every byte.
    """
    mac = mac.strip().lower()

    if ":" in mac or "-" in mac:
        groups = re.split(r"[:-]", mac)
        octets = [g.rjust(2, "0") for g in groups]
    elif "." in mac:
        # Cisco dot-notation: 3 groups of 4 hex digits (2 bytes) each
        groups = mac.split(".")
        hex_only = "".join(g.rjust(4, "0") for g in groups)
        octets = [hex_only[i : i + 2] for i in range(0, len(hex_only), 2)]
    else:
        hex_only = re.sub(r"[^0-9a-f]", "", mac).rjust(12, "0")
        octets = [hex_only[i : i + 2] for i in range(0, 12, 2)]

    while len(octets) < 6:
        octets.insert(0, "00")
    return ":".join(octets[-6:])


def get_local_subnets() -> list[ipaddress.IPv4Network]:
    """Return the IPv4 subnets this device is directly attached to."""
    subnets: list[ipaddress.IPv4Network] = []
    for addrs in psutil.net_if_addrs().values():
        for addr in addrs:
            if addr.family.name != "AF_INET" or not addr.netmask:
                continue
            if addr.address.startswith("127."):
                continue
            try:
                network = ipaddress.IPv4Network(
                    f"{addr.address}/{addr.netmask}", strict=False
                )
            except ValueError:
                continue
            subnets.append(network)
    return subnets


def get_local_ips() -> set[str]:
    """Return this device's own IPv4 addresses.

    macOS (and likely other OSes) adds a "permanent" ARP entry mapping an
    interface's own IP to its own MAC as part of normal bookkeeping — not
    a real neighbor learned via the ARP protocol, just formatted
    identically to one. Left unfiltered, the tablet ends up listed as a
    phantom second device alongside the synthetic root node.
    """
    ips: set[str] = set()
    for addrs in psutil.net_if_addrs().values():
        for addr in addrs:
            if addr.family.name == "AF_INET" and not addr.address.startswith("127."):
                ips.add(addr.address)
    return ips


def _is_unicast_device(ip: str, mac: str) -> bool:
    """Exclude broadcast/multicast entries — not real, individually-queryable devices."""
    if set(mac) <= {"0", ".", ":", "-"}:
        return False  # incomplete/placeholder entries, e.g. "(incomplete)"
    if mac == "ff:ff:ff:ff:ff:ff":
        return False  # broadcast
    if int(mac.split(":")[0], 16) & 0x01:
        return False  # multicast MAC: I/G bit set on the first octet
    try:
        if ipaddress.IPv4Address(ip).is_multicast:
            return False
    except ValueError:
        return False
    return True


def _parse_arp_output(output: str) -> list[ArpEntry]:
    entries: list[ArpEntry] = []
    for line in output.splitlines():
        match = _ARP_LINE_UNIX.search(line) or _ARP_LINE_WINDOWS.search(line)
        if not match:
            continue
        ip, mac = match.group("ip"), normalize_mac(match.group("mac"))
        if not _is_unicast_device(ip, mac):
            continue
        entries.append(ArpEntry(ip=ip, mac=mac))
    return entries


async def read_arp_table() -> list[ArpEntry]:
    """Read the OS ARP cache via `arp -a` (no raw sockets, no admin privilege)."""
    command = ["arp", "-a"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
    except (OSError, TimeoutError) as exc:
        logger.warning("arp_read_failed", error=str(exc), platform=platform.system())
        return []

    if proc.returncode != 0:
        logger.warning(
            "arp_command_nonzero",
            returncode=proc.returncode,
            stderr=stderr.decode(errors="replace"),
        )
        return []

    entries = _parse_arp_output(stdout.decode(errors="replace"))
    local_ips = get_local_ips()
    return [entry for entry in entries if entry.ip not in local_ips]


_MAX_SWEEP_HOSTS_PER_SUBNET = 256  # skip sweeping if a subnet is bigger than this
_PING_TIMEOUT_SECONDS = 1


async def _ping_host(ip: str) -> None:
    """Fire-and-forget ping via the OS ping command. The point isn't the
    liveness result (unreachable/firewalled hosts are simply skipped) —
    it's the side effect of prompting the OS to populate an ARP entry for
    this host so a subsequent read_arp_table() call can see it."""
    if platform.system() == "Windows":
        command = ["ping", "-n", "1", "-w", str(_PING_TIMEOUT_SECONDS * 1000), ip]
    else:
        command = ["ping", "-c", "1", "-W", str(_PING_TIMEOUT_SECONDS), ip]
    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=_PING_TIMEOUT_SECONDS + 1)
    except (OSError, TimeoutError):
        pass


async def sweep_local_subnets() -> None:
    """Ping every host in the locally-attached subnets (capped, to avoid
    sweeping a misconfigured huge subnet) so devices this machine has
    never talked to still show up in the ARP cache afterward. Firewalled
    hosts that don't respond to ICMP won't be found this way — that's a
    known limitation, not a bug: this is a best-effort nudge, not a
    guaranteed-complete scan."""
    subnets = [s for s in get_local_subnets() if s.num_addresses <= _MAX_SWEEP_HOSTS_PER_SUBNET]
    hosts = [str(ip) for subnet in subnets for ip in subnet.hosts()]
    if not hosts:
        return
    await asyncio.gather(*(_ping_host(ip) for ip in hosts), return_exceptions=True)
