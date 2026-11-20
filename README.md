# AppLocker — Modern Windows Application Access Control

**v2.0.0** · Windows 10 / 11 · [MIT License](LICENSE.md)

AppLocker password-protects the applications you choose. When a locked app is
launched it is closed immediately and a lock screen appears; the app only runs
again when the correct password is entered (or a temporary unlock expires).

It is a full re-design of the original C++/Qt AppLocker into a modern,
dependency-light Windows application built with **Python + tkinter** and
packaged as a single portable `AppLocker.exe`.

> **Scope disclaimer.** AppLocker is a *user-space* utility for privacy and
> light parental control on a shared or personal computer. It is **not** a
> substitute for account isolation, OS-level security, or enterprise
> application control. See [Security model](#security-model).

---

## Features

| Capability | Details |
|---|---|
| **Master password** | Memory-hard hashing (scrypt) — never stored in plain text |
| **Per-app passwords** | Optional, stronger per-app PIN; falls back to master |
| **Recovery key** | A one-time friendly key resets a forgotten master password |
| **Policies** | `Always` · `Allowed time window` · `Weekly schedule` (per-day hours) · `None` |
| **Groups** | Bundle apps with a shared policy (e.g. “Games — only on weekends”) |
| **Temporary unlock** | Unlock one app for 5–60 min without disabling protection |
| **Pause protection** | 5 min / 15 min / 30 min / 1 h / until resumed |
| **Quick Lock** | Reassert every policy immediately, clears all temp unlocks |
| **Process monitor** | Low-CPU Win32 Toolhelp32 snapshot (no per-poll subprocesses) |
| **Lock screen** | Shows app icon, reason, brut-force feedback, temp-unlock button |
| **Discovery** | Installed-app scan (registry + Start Menu shortcuts) with real icons |
| **Activity log** | Blocked / auth / policy events with search + filtering |
| **Themes** | Light / Dark / follow Windows, 5 accent colors |
| **System tray** | Open · Protected Apps · Pause · Quick Lock · Settings · Exit |
| **Run at login** | User-level startup entry (no admin rights) |
| **Audit path** | SQLite + DPAPI protected keys + rotating redacted logs |

## Screenshots / quick tour

- **Dashboard** — protection status, stat tiles, protected-app quick list, lock-all.
- **Applications** — searchable list with app icons; manage policy, password, favorite, remove.
- **Groups** — color-coded groups sharing one policy; add members from discovered apps.
- **Activity** — Event log with type filter + search; CSV-exportable diagnostics.
- **Settings** — general, security (master / recovery), protection defaults,
  notifications, appearance, and advanced incl. integrity check + import/export.
- **About** — version, license, credentials.

## Getting started

1. Download the latest `AppLocker.exe` and its `AppLocker.exe.sha256`
   checksum from **Releases**, or build it yourself (below).
2. Run the app — a 6-step **setup wizard** walks you through:
   create master password → write down your **recovery key** → choose
   run-at-login → optionally pick your first protected app.
3. From the **Applications** page, add apps (browse, auto-discover from
   installed software, or pick a running process) and set a policy.
4. Keep AppLocker in the **system tray**. Closing the window hides to tray;
   protection only stops when you choose **Exit** (and confirm knowing
   protection is disabled).

> First launch of a freshly built EXE may take a few seconds while
> one-file bundles unpack — subsequent launches are near-instant.

## Building from source

Requires **Python 3.11+** on Windows and the packages in `requirements.txt`.

```powershell
pip install -r requirements.txt

# Run directly from source (dev):
python app.py

# One-file, windowed EXE + SHA-256 checksum:
.\build.ps1
# → dist\AppLocker.exe  and  release\AppLocker.exe(.sha256)
```

### Install (portable, no admin)

```powershell
# installs to %LOCALAPPDATA%\Programs\AppLocker + uninstall entry:
.\install.ps1 -Startup

# remove installed copy + uninstall entry:
.\install.ps1 -Uninstall
```

## Tests

```powershell
python -m unittest discover tests
python tests\ui_smoke.py        # headless-ish UI tree smoke test
```

Coverage: crypto primitives, policy/schedule engine, SQLite data layer,
controller workflows (auth, recovery, app passwords, pause/lock-all,
block routing).

## Architecture

```
applocker/
  core/        crypto (scrypt verifier, DPAPI+Fernet), security services
               (AuthStore, brute-force guard, recovery keys), policy engine,
               process monitor, app discovery, AppController (single owner
               of state)
  data/        SQLite storage: apps, groups, events, settings (schema v3),
               integrity check, export/import
  ui/          theme engine, widgets (Card/Toggle/EmptyState/Toast…),
               dialogs, pages, lock screen, setup wizard, main window
  tray/        pystray system-tray controller
  util/        paths, logging (redacting, rotating), win32 helpers, brand
  assets/      generated multi-res PNG + .ico brand assets
app.py              bootstrap / entry point
tests/              unittest suite + UI smoke test
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full audit, threat
model and rationale for every security decision.

### Security model

- **Master password** is verified with **scrypt** (`scrypt$v1$n$…`), a
  memory-hard KDF tuned to ~50 ms per check; no plaintext or fast-hash
  material is ever stored.
- **Encrypted-at-rest secrets**: passphrases are wrapped with
  **DPAPI + AES (Fernet)** under a key that never leaves the user profile.
- **Recovery** uses an unambiguous alphabet key (no look-alike characters);
  the key itself is stored only in DPAPI-protected form.
- **Brute-force guard**: 5 failed attempts → lockout with configurable
  cooldown, logged as audit events.
- **Honest boundary**: any per-user, user-space tool can be defeated by
  admin rights, Safe Mode, or booting another OS. AppLocker detects and logs
  tampering where it can, but does not pretend to be a kernel/anti-cheat
  product.

### Known limitations

- Requires the AppLocker process to be running for enforcement (see tray).
- Renamed executables or launchers that spawn a differently-named child may
  evade path-based matching.
- No kernel-mode enforcement; no protection in Safe Mode / by administrators.

## Troubleshooting

- **App won't detect my app** — the monitor matches the *resolved exe path*;
  add the app by its exact path via **Browse / Discover**.
- **Lock screen is slow to appear** — detection polls on a 1.1 s UI timer by
  design (low CPU). Allow up to ~2 s.
- **Forgot the master password** — use your recovery key, or (if lost) reset
  via **Settings → Security → Reset / Recovery** after the recovery-key check
  where possible. Otherwise remove `%LOCALAPPDATA%\AppLocker\Data\secrets.bin`
  to start fresh (this also removes per-app vault entries).
- **Logs** live in `%LOCALAPPDATA%\AppLocker\Data\logs` (rotated, redacted).

## License & credits

MIT — see [LICENSE.md](LICENSE.md). Original AppLocker by Hachiki © 2025;
modern v2 re-design and implementation by Pratham. App icons generated with
Pillow; icons for installed apps are extracted from the executables themselves.