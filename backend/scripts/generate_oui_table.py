"""Regenerates app/data/oui_vendors.json from IEEE's public MA-L registry.

Usage:
    uv run --directory backend python scripts/generate_oui_table.py

Downloads https://standards-oui.ieee.org/oui/oui.csv (IEEE's official
24-bit OUI assignment list — the "MA-L" registry, which covers the vast
majority of vendor MAC prefixes in practice) and compacts it to a
{OUI_HEX: vendor_name} JSON map, dropping the address column this app has
no use for. Re-run this occasionally to pick up newly assigned OUIs; it's
a manual/offline step rather than a runtime fetch since the tablets this
app runs on aren't guaranteed internet access and the registry doesn't
change fast enough to need a live lookup.

Does not cover IEEE's smaller MA-M (28-bit) / MA-S (36-bit) registries,
used for organizations that have exhausted a full MA-L block — a
reasonable gap for a first pass, not attempted here.
"""

import csv
import json
import subprocess
from pathlib import Path

OUI_CSV_URL = "https://standards-oui.ieee.org/oui/oui.csv"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "oui_vendors.json"


def main() -> None:
    # IEEE's server 418s Python's urllib (bot-mitigation on something
    # beyond just the User-Agent header) but not curl, so shell out
    # instead of fighting it with request headers.
    text = subprocess.run(
        ["curl", "-sS", "--max-time", "30", OUI_CSV_URL],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    reader = csv.DictReader(text.splitlines())
    table = {
        row["Assignment"].strip().upper(): row["Organization Name"].strip()
        for row in reader
        if row["Assignment"] and row["Organization Name"]
    }

    OUTPUT_PATH.write_text(json.dumps(table, sort_keys=True, separators=(",", ":")))
    print(f"Wrote {len(table)} OUI entries to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
