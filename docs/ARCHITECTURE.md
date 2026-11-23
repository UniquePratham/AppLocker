# Aegis — Architecture

Aegis is a user-space Windows utility that password-protects the applications
you choose. This note describes how the current code is organised and why.

## Layers

```
app.py                     bootstrap: services, tray, wizard, main window
applocker/
  core/                    domain logic, no UI imports
    app.py                 AppController — the single source of truth
    crypto.py              scrypt hashing, DPAPI secret storage
    security.py            AuthStore, brute-force guard, session state
    policy.py              pure policy evaluation (always / time / schedule)
    monitor.py             Toolhelp32 process snapshot + diff
    discovery.py           registry and Start Menu app discovery
  data/
    database.py            SQLite schema, migrations, CRUD
  ui/                      CustomTkinter presentation only
    tokens.py              spacing, type scale, palettes, accents
    components.py          Card, AppRow, StatusPill, StatTile, Toast, buttons
    screens.py             dashboard, applications, groups, activity, settings
    main_window.py         sidebar shell + page host
    setup_wizard.py        six-step first-run flow
    lockscreen.py          lock screen, master auth, recovery
    icons.py               PhotoImage cache
  tray/tray.py             pystray menu and callbacks
  util/                    paths, logging, Win32 helpers, brand rendering
```

**Rule:** `core/` never imports `ui/`. The UI reads state from
`AppController` and mutates it only through controller methods. There is one
authoritative state, so the dashboard, tray and application list cannot
disagree.

## State ownership

`AppController` owns:

- the SQLite connection (`AppDatabase`)
- the secret store (`AuthStore`)
- the process monitor
- pause state, temporary unlocks, brute-force guards

The UI never keeps its own copy of security state. A toggle calls the
controller, then re-reads. If the monitor dies, `protection_status()` reports
`error` and the UI shows "Monitoring Problem" instead of a stale "Active".

## Process monitoring

`ProcessMonitor.poll()` runs on the Tk timer (1 s). It takes a
`CreateToolhelp32Snapshot` of the process table, resolves each PID's full
executable path, and diffs against the previous snapshot. Only newly-seen PIDs
are evaluated, so cost is proportional to process churn, not process count.

Identity is the **normalised absolute path**, with a basename fallback only
when that basename is unique among protected apps. This stops a protected
`chrome.exe` from blocking an unrelated copy elsewhere on disk.

A blocked launch calls `AppController.handle_block`, which terminates the PID
and queues a lock screen on the UI thread via `root.after`.

## Policy engine

`PolicyEvaluator` is pure: given a `PolicyRecord` and a `datetime`, it returns
block or allow. Kinds:

| Kind | Behaviour |
|---|---|
| `always` | Blocked whenever protection is active |
| `time` | Blocked outside an allowed daily window |
| `schedule` | Blocked per weekday with its own window |
| `none` | Not protected |

Overnight windows (`22:00 → 07:00`) are handled by comparing minute-of-day and
inverting the range. Runtime modifiers (`temporary_until`, `session_unlocked`)
are checked before the policy itself.

## Secrets

- Master password: **scrypt** with a per-install salt, stored as a verifier —
  never the password.
- Per-app passwords: same scheme, separate salt.
- Recovery key: random, shown once, stored as a scrypt verifier.
- DPAPI wraps the key material so the files are useless on another machine or
  user account.

## Database

SQLite in `%LOCALAPPDATA%\Aegis\Data\applocker.db`, WAL mode, one connection
guarded by an `RLock`. Schema version lives in `meta`; migrations run on open.
`integrity_check()` runs `PRAGMA integrity_check` plus a schema-version check.

## UI

CustomTkinter with a design-token layer. Every screen is composed from
`components.py`, so spacing, radius and colour stay consistent and a theme
change is one edit in `tokens.py`.

The root window is parked at `1x1+0+0` and the real surfaces are `Toplevel`s.
This is deliberate: a *withdrawn* root makes Toplevel children report
`winfo_viewable() == 1` while Windows keeps them hidden, and a root with
`-alpha 0` passes that alpha to its children. Keeping the root mapped at 1×1
avoids both.

## Packaging

`AppLocker.spec` builds a one-file windowed EXE. It bundles
`applocker/assets` and `collect_data_files("customtkinter")` — without the
latter the frozen build cannot construct a single widget, because
CustomTkinter loads its theme JSON and fonts from package data at import time.

`installer/AppLocker.iss` produces a per-user Inno Setup installer (no admin
rights) with the Aegis icon on the setup executable, shortcuts and uninstall
entry.

## Testing

`tests/` covers crypto, policy (including midnight boundaries), database CRUD
and migrations, and the controller's add/remove/lock/unlock/pause paths.
`tests/ui_smoke.py` constructs every screen headlessly.

```bash
python -m pytest -q
```