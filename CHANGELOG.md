# Changelog

## [Unreleased]
### Added
### Fixed
- Topology discovery only ever finding this tablet itself: non-Windows `arp -a` was resolving each entry's hostname via reverse DNS before printing, which routinely took longer than the ARP read's 5s timeout on networks without local reverse DNS, silently returning zero entries every poll. Now uses `arp -an` to skip the lookup, with the timeout bumped to 8s as a buffer.
### Changed

## [v1.1.0] - 2026-08-06
### Added
- FastAPI backend scaffold with localhost-only binding, structured logging, and encrypted-credential-storage pattern
- Frontend scaffold with touch-friendly Cytoscape.js topology visualization
- Tauri desktop shell scaffold wrapping the frontend, with PyInstaller sidecar spec documented (Windows binary build deferred — see README)
- Real SNMP/LLDP (with CDP fallback) topology discovery, replacing the stub: ARP-seeded BFS neighbor walk, background polling cache, 19 unit tests against mocked SNMP responses
- Active ping sweep of small local subnets before ARP read, so devices this tablet hasn't already talked to still get discovered (still no raw sockets — shells out to the OS ping binary)
- Per-user login system with Viewer/Operator/Admin roles: SQLite-backed accounts, argon2id password hashing, opaque bearer-token sessions (not JWT — see auth_service.py for why), one-time first-run admin bootstrap, `/api/topology` now requires authentication
- Source/target port labels on topology edges (e.g. Switch A's Gi0/1 to Switch B's Gi0/24), resolved from LLDP/CDP's local port index via IF-MIB's ifDescr
- Host Monitor tab: lists every discovered device with a per-device Ping button showing reply status and round-trip latency; new `POST /api/devices/{device_id}/ping`, gated at operator role and restricted to already-discovered device IDs
### Fixed
- `npm run dev` backend startup: replaced `fastapi dev` (needs an uninstalled extra) with `uvicorn` directly, and fixed `uv run --project` to `--directory` so the `app` module resolves correctly from the repo root
- Topology discovery no longer lists this machine's own IP as a phantom second device — macOS's self-referential "permanent" ARP entry for the interface's own address was being read as a real neighbor
- Host Monitor's Ping button now reports actual round-trip latency on macOS/BSD instead of "reply received" with no number — ping's `-W` flag is milliseconds there, not seconds like Linux, so the wait window was 1000x too short and suppressed the reply line this parses
### Changed
