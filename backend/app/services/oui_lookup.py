"""MAC OUI (first 3 bytes) to vendor name lookup.

Backed by a bundled snapshot of IEEE's public MA-L registry
(app/data/oui_vendors.json — see scripts/generate_oui_table.py for how
it's built) rather than a live lookup: tablets running this app aren't
guaranteed internet access, and the registry doesn't change fast enough
to justify a network round-trip per device anyway.
"""

import json
from functools import lru_cache
from importlib import resources

_OUI_LENGTH = 6  # hex chars — the 24-bit MA-L prefix


@lru_cache(maxsize=1)
def _table() -> dict[str, str]:
    data = resources.files("app.data").joinpath("oui_vendors.json").read_text()
    return json.loads(data)


def lookup_vendor(mac: str) -> str | None:
    oui = mac.replace(":", "").replace("-", "").upper()[:_OUI_LENGTH]
    if len(oui) != _OUI_LENGTH:
        return None
    return _table().get(oui)
