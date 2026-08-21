from app.services.oui_lookup import lookup_vendor


def test_lookup_vendor_finds_known_prefix() -> None:
    assert lookup_vendor("E8:0A:B9:11:22:33") == "Cisco Systems, Inc"


def test_lookup_vendor_is_case_and_separator_insensitive() -> None:
    assert lookup_vendor("00-03-93-aa-bb-cc") == lookup_vendor("00:03:93:AA:BB:CC")


def test_lookup_vendor_returns_none_for_unassigned_prefix() -> None:
    assert lookup_vendor("ff:ff:ff:00:00:00") is None


def test_lookup_vendor_returns_none_for_malformed_mac() -> None:
    assert lookup_vendor("not-a-mac") is None
