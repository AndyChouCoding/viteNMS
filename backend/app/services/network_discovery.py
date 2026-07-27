"""Local network detection and ARP cache reading.

Deliberately avoids raw sockets: this only reads state the OS already
maintains (interface config, ARP cache) rather than sending probe packets.
See the IEC 62443 minimal-privilege note in the project README — v1.0.0's
discovery needs no elevated privilege, unlike the future Npcap-based
diagnostic module.

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

    return _parse_arp_output(stdout.decode(errors="replace"))
