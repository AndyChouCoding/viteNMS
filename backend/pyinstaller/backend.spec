# PyInstaller spec for freezing the FastAPI backend into a Tauri sidecar
# binary. PyInstaller does not cross-compile: this must be run on the
# target OS (Windows for the deployed tablet). Not yet executed as part
# of the scaffold — see project plan "Risks" section.
#
# Usage (on a Windows build machine/CI):
#   uv run pyinstaller pyinstaller/backend.spec
#
# pysnmp loads ASN.1/MIB modules dynamically, which PyInstaller's static
# analysis can miss. Expect to grow `hiddenimports` once real SNMP polling
# code is written; this list is a starting point, not exhaustive.

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("pysnmp")

a = Analysis(
    ["../app/main.py"],
    pathex=[".."],
    # The bundled MAC OUI vendor table (app/services/oui_lookup.py reads
    # it via importlib.resources) — PyInstaller's static analysis only
    # follows code, not package data, so it has to be listed explicitly.
    datas=[("../app/data/oui_vendors.json", "app/data")],
    hiddenimports=hiddenimports,
    hookspath=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="open-vision-backend",
    console=False,
)
