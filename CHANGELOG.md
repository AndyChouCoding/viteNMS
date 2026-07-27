# Changelog

## [Unreleased]
### Added
- FastAPI backend scaffold with localhost-only binding, structured logging, and encrypted-credential-storage pattern
- Frontend scaffold with touch-friendly Cytoscape.js topology visualization
- Tauri desktop shell scaffold wrapping the frontend, with PyInstaller sidecar spec documented (Windows binary build deferred — see README)
- Real SNMP/LLDP (with CDP fallback) topology discovery, replacing the stub: ARP-seeded BFS neighbor walk, background polling cache, 19 unit tests against mocked SNMP responses
### Fixed
### Changed
