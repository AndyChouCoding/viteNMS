# Changelog

## [Unreleased]
### Added
### Fixed
- Packaged builds got stuck on "Loading…" and would sometimes crash outright: a `console=False` PyInstaller build has `sys.stdout`/`sys.stderr` set to `None` instead of redirected, so the moment anything logged (uvicorn's own startup messages, our own log handler) it hit an `AttributeError` and took the backend process down with it. Frozen builds now get harmless no-op streams instead, and skip attaching a console log handler entirely (there's no console to see it anyway — the file log already persists, see v1.2.3).
- Packaged builds would flash a burst of console windows (up to one per host in a swept subnet, every discovery poll): spawning `ping`/`arp` from a console-less process makes Windows give each one its own new console window. Now passed `CREATE_NO_WINDOW` on Windows.
### Changed

## [v1.2.3] - 2026-08-18
### Added
- `DELETE /api/auth/users/{id}` (admin-only): removes an account and its sessions. Refuses to delete the last admin while other accounts would be left behind with nobody able to manage them, but allows clearing out the sole remaining account entirely (that just returns the tablet to its first-run "needs setup" state).
### Fixed
- Packaged (Windows) builds only ever showed the login screen, never the first-run "create administrator account" screen, even on a genuinely fresh install: the frontend checked `/api/auth/bootstrap-status` once on load and silently treated any failure as "already has an account", but the frozen backend sidecar (PyInstaller onefile) takes a few seconds to start listening after the window opens, so that first check routinely failed. Now retries until the backend actually responds instead of guessing.
- Auth DB, logs, and the encrypted credential store were computed relative to `__file__`, which in a PyInstaller onefile build resolves inside that run's temp extraction folder — normally deleted after the process exits, so none of them actually persisted between app restarts in production even though they appeared to work. Frozen builds now use the OS per-user local app data directory instead; dev behavior (paths under `backend/`) is unchanged.
- CORS middleware only allowed `GET`/`POST`, so the new `DELETE` endpoint (and any future non-GET/POST route) would have been silently blocked by the browser's preflight before ever reaching the backend.
- Login form applied the "at least 8 characters" password rule to sign-in, not just account creation — an existing account with a shorter password (e.g. one created directly via the API rather than the bootstrap form) couldn't log in through the UI at all even with the correct password.

## [v1.2.2] - 2026-08-18
### Fixed
- Topology view never refreshed after its initial load — it fetched `/api/topology` once on mount with no polling, so the graph could silently go stale while the tab stayed open. Now polls every 5s, matching the pattern already used by System Log. Also fixed a related display bug: a single failed poll used to blank the whole topology view with an error message even when a good graph was already showing; now it only does that when there's no graph yet, otherwise it keeps showing the last-known-good graph.

## [v1.2.1] - 2026-08-18
### Added
- Wired the Tauri backend sidecar: production builds now spawn the frozen FastAPI backend on startup and kill it on app exit, instead of just documenting the intent.
- GitHub Actions workflow (`build-windows.yml`) that builds the Windows installer on `windows-latest`: freezes the backend with PyInstaller, runs `tauri build`, and attaches the resulting `.msi`/`.exe` to a GitHub Release. Triggers on `v*.*.*` tag pushes (same tags used for releases) or manually via `workflow_dispatch`.

## [v1.2.0] - 2026-08-18
### Added
- Host Monitor now shows this tablet's own IP/MAC address and lets you ping it like any other discovered device, instead of showing "—" with a disabled Ping button.
- System Log tab: records login/logout, every ping attempt (success and failure), and device connected/disconnected transitions, each as a Title/Description/Time row. Auto-refreshes every 10s; capped at the last 500 events.
### Fixed
- Topology discovery only ever finding this tablet itself: non-Windows `arp -a` was resolving each entry's hostname via reverse DNS before printing, which routinely took longer than the ARP read's 5s timeout on networks without local reverse DNS, silently returning zero entries every poll. Now uses `arp -an` to skip the lookup, with the timeout bumped to 8s as a buffer.
- ARP-sweep ping (`_ping_host`, used to seed ARP entries before reading the table) had the same BSD/macOS `-W`-is-milliseconds unit mismatch fixed for `ping_once` in v1.1.0 — didn't affect discovery correctness, but is now consistent.
### Changed
- Layout is now responsive for tablet screens: the header wraps instead of overflowing on narrower/portrait widths, the topology view's device panel stacks below the graph instead of squeezing it under the md breakpoint, and all primary buttons/inputs meet the ~44px touch target guideline.

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
