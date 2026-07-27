# Changelog

## [Unreleased]
### Added
- FastAPI backend scaffold with localhost-only binding, structured logging, and encrypted-credential-storage pattern
- Frontend scaffold with touch-friendly Cytoscape.js topology visualization
- Tauri desktop shell scaffold wrapping the frontend, with PyInstaller sidecar spec documented (Windows binary build deferred — see README)
- Real SNMP/LLDP (with CDP fallback) topology discovery, replacing the stub: ARP-seeded BFS neighbor walk, background polling cache, 19 unit tests against mocked SNMP responses
- Active ping sweep of small local subnets before ARP read, so devices this tablet hasn't already talked to still get discovered (still no raw sockets — shells out to the OS ping binary)
### Fixed
- `npm run dev` backend startup: replaced `fastapi dev` (needs an uninstalled extra) with `uvicorn` directly, and fixed `uv run --project` to `--directory` so the `app` module resolves correctly from the repo root
### Changed
