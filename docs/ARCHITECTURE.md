# AppLocker — Internal Architecture Assessment

This document captures the audit of the existing repository and the target
architecture for the modernized product. It is an internal engineering note.

## 1. Audit of existing repository

### Stack (as found)

* **Language / framework:** C++17 + Qt Widgets (Qt 5, `QT += widgets network core`).
* **UI:** Single `QWidget` window with hard-coded `move(x, y)` positioned
  controls, plus several modal "one-off" `QDialog` classes. No layout manager
  for the main window, no styling, no theming.
* **Process monitoring:** A `QTimer` firing every **1000 ms** that snapshots all
  processes via `CreateToolhelp32Snapshot` and calls `TerminateProcess` on any
  locked executable that is running, then shows a modal password dialog.
  This is a busy-loop poll with a hard 1 s latency and heavy per-tick snapshot
  cost.
* **Persistence:** Plaintext files in `QStandardPaths::AppDataLocation`:
  * `master_password.dat` — **unsalted SHA-256** of the master password.
  * `app_passwords.dat` — `name|sha256(password)` per line (unsalted).
  * `locked_apps.txt` — newline list of executable names.
* **Password handling:** Un-salted SHA-256. No salt, no KDF, no pepper, no
  authenticated encryption, no DPAPI. Trivially brute-forced by anyone with
  file access.
* **Privileges:** The installer forces admin install; the app is otherwise a
  normal user-space process that tries to `TerminateProcess` other processes
  (which generally fails unless the target is same-or-lower integrity).
* **Startup:** Handled only in the Inno Setup `.iss` via a `{commonstartup}`
  shortcut task (all-users startup). No in-app control.
* **Tray:** `QSystemTrayIcon` with a simple three-item menu.
* **Installer / build:** Qt `.pro` with qmake; Inno Setup `.iss` (paths are
  hard-coded to another machine's `C:\Users\Hp\...` — broken as shipped).
* **Update:** Fetches the upstream GitHub latest-release JSON.

### Limitations / vulnerabilities found

1. **Unsalted SHA-256** for all secrets — no protection against offline
   dictionary attacks; identical passwords hash identically.
2. **Plaintext secret files** in a predictable, user-writable directory.
3. **Busy-loop process polling** at 1 Hz — poor for power/CPU and 1 s stale.
4. **Race conditions** in monitoring: it snapshots then terminates; a process
   launched and killed within the same tick can evade, and rapid relaunch after
   the modal dialog closes is not tracked on the process identity level.
5. **No brute-force protection** — infinite password attempts, no lockout, no
   delay, no recovery path besides *deleting the password file* (documented).
6. **No threat-model honesty at the code level** — relies on killing processes,
   which legitimate same-user processes can easily defeat.
7. **`Slider/Geometry` UI** — not DPI aware, not resizable.
8. Dead code: `lockwindow.cpp/.h` are compiled but never instantiated.
9. **No tests**, no structured logging, no schema versioning.
10. **No application discovery** — user must type `chrome.exe` by hand.

### What to preserve

* The product concept (background app locking via master + per-app policy).
* The belief in an honest security-boundary README (already partly present).
* The stereotype of a system tray experience and "close to tray" behavior.

### What to replace

* Storage → SQLite (`sqlite3` stdlib) behind a typed repository, schema-versioned.
* Secrets → `scrypt`/`PBKDF2` + HMAC + a key stored via Windows DPAPI
  (`CryptProtectData`); never plaintext; never in logs.
* Monitoring → a cheap periodic scan of a *cached snapshot* with grace handling,
  plus event-driven `CreateProcess` interception where feasible, avoiding
  per-tick full-snapshot cost.
* UI → a reusable design system, Fluent-inspired, light/dark/system themes,
  DPI-aware ttk layout, no absolute positioning.
* Discovery → scan Start Menu, installed programs (Uninstall registry keys),
  running processes, and file picker; extract real icons with caching.
* Installer/build → reproducible packaging scripts producing `AppLocker.exe`,
  an installer, and checksums.

## 2. Target architecture

New product: **AppLocker — Modern Windows Application Access Control**.

Chosen stack for the rebuild (driven by available toolchain on this machine and
a small-footprint, maintainable product):

* **Language:** Python 3 (CPython).
* **GUI:** `tkinter` + `ttk` behind a small design-system layer (dark/light.
* **Secrets:** `cryptography` — `scrypt` KDF for passwords, `Fernet` for
  reversible secrets, Windows DPAPI to protect the key.
* **Storage:** `sqlite3` (stdlib) with schema versioning and migrations.
* **Icons/art:** `Pillow` — vector-like generated app icon with proper rounded
  corners, exported to all standard resolutions and `.ico`.
* **Tray:** `pystray`.
* **Packaging:** `PyInstaller` → `AppLocker.exe`; installer + checksums via
  build scripts.

### Module layout

```
applocker/
  core/         crypto, security, policy, monitoring, discovery
  data/         db, repositories, migrations
  ui/           design system, pages, dialogs, lock screen, setup wizard
  tray/         tray controller
  util/         logging, paths, icons, humanize
  app.py        application bootstrap
tests/
```

### Security boundary (honest)

This is a **user-space convenience/privacy layer**. It is not kernel-level and
cannot resist: Safe Mode, offline editing of the data files by an
administrator, termination of the monitor process, or malicious kernel drivers.
We implement the strongest practical user-space design and document the
boundary.

## 3. Priority order

Security → Reliability → UX → Performance → Maintainability → Polish.
