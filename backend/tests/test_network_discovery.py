from app.services.network_discovery import _parse_arp_output, normalize_mac

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
