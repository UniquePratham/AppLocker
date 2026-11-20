"""Background monitor for protected applications.

Design goals
------------
* Low CPU: snapshot the process table via the Win32 Toolhelp32 API every
  tick (no PowerShell subprocess per poll), then *diff* against the previous
  snapshot so work is proportional to newly-started processes only.
* Path-based identity: match on the full resolved executable path first, then
  fall back to the basename. Avoids blocking unrelated copies of an exe.
* Race handling: a process is treated as "new" exactly once (seen-set); if we
  can't resolve its path this tick we re-check next tick. We never terminate a
  PID that already exited (defensive OpenProcess) and never kill our own PID.
* Duplicate instance handling: each PID is evaluated independently.
* The monitor never calls the callback from a worker thread in a blocking way;
  ``poll()`` is synchronous and lightweight enough to run on the UI timer.

The default poll is 1.2 s, giving sub-second-average detection latency with a
tiny CPU footprint (a toolhelp snapshot is a few ms).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import time
from dataclasses import dataclass
from typing import Callable, Optional

from applocker.util.logging import get_logger
from applocker.util.winutil import get_process_path, terminate_pid

log = get_logger()

POLL_INTERVAL = 1.0

TH32CS_SNAPPROCESS = 0x00000002


@dataclass
class ProcessInfo:
    pid: int
    path: str


@dataclass
class BlockedEvent:
    app_id: str
    app_name: str
    exe_path: str
    pid: int


class ProcessMonitor:
    """Polls running processes and notifies for protected apps.

    ``app_lookup`` returns ``{lowercased_path: app_row}`` (the caller's DB
    snapshot). ``on_blocked`` receives a ``BlockedEvent`` and is responsible
    for showing the lock screen and terminating the process.
    """

    def __init__(
        self,
        app_lookup: Callable[[], dict[str, dict]],
        on_blocked: Callable[[BlockedEvent], None],
        interval: float = POLL_INTERVAL,
    ):
        self.app_lookup = app_lookup
        self.on_blocked = on_blocked
        self.interval = interval
        self._last_run = 0.0
        self._seen_pids: set[int] = set()
        self._last_snapshot: set[int] = set()
        self._paused = False
        self._running = True
        self.run_count = 0
        self._my_pid = os.getpid()

    # ------------------------------------------------------------------ #
    # Snapshot via Toolhelp32 (lightweight, no subprocess)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _snapshot() -> list[ProcessInfo]:
        """Return (pid, path) for live processes where path is resolvable.

        We only include PIDs whose path resolves; the monitor's identity model
        is path-based. Processes we cannot resolve are re-checked next tick.
        """
        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wt.DWORD),
                ("cntUsage", wt.DWORD),
                ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(wt.ULONG)),
                ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD),
                ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260),
            ]

        snapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == ctypes.c_void_p(-1).value or snapshot == 0:
            return []
        infos: list[ProcessInfo] = []
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = ctypes.windll.kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
            while ok:
                pid = int(entry.th32ProcessID)
                path = get_process_path(pid)
                if path:
                    infos.append(ProcessInfo(pid=pid, path=path))
                ok = ctypes.windll.kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            ctypes.windll.kernel32.CloseHandle(snapshot)
        return infos

    # ------------------------------------------------------------------ #
    # Public control
    # ------------------------------------------------------------------ #
    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        if not paused:
            # Resume with a clean slate so any process that started while
            # paused is re-detected (and blocked if still running).
            self._seen_pids.clear()
            self._last_snapshot.clear()

    def stop(self) -> None:
        self._running = False

    @property
    def paused(self) -> bool:
        return self._paused

    # ------------------------------------------------------------------ #
    # Tick
    # ------------------------------------------------------------------ #
    def poll(self) -> None:
        now = time.time()
        if now - self._last_run < self.interval:
            return
        self._last_run = now
        if self._paused or not self._running:
            return
        self.run_count += 1
        apps = self.app_lookup()
        if not apps:
            self._last_snapshot.clear()
            self._seen_pids.clear()
            return

        infos = self._snapshot()
        current_pids = {i.pid for i in infos}
        # Only freshly-started processes are candidates for blocking.
        for info in infos:
            if info.pid in self._seen_pids or info.pid in self._last_snapshot:
                continue
            if info.pid == self._my_pid:
                continue
            self._seen_pids.add(info.pid)
            app = self._lookup_app(apps, info.path)
            if app:
                log.info("Protected app launched: %s (%s)", app.get("name"), info.path)
                self.on_blocked(BlockedEvent(
                    app_id=app.get("id", ""),
                    app_name=app.get("name", ""),
                    exe_path=info.path,
                    pid=info.pid,
                ))

        self._last_snapshot = current_pids
        self._seen_pids &= current_pids

    @staticmethod
    def _lookup_app(apps: dict[str, dict], exe_path: str) -> Optional[dict]:
        if not exe_path:
            return None
        # Normalise for case + slash variants; store keys are lower-cased.
        norm = os.path.normpath(exe_path).lower()
        if norm in apps:
            return apps[norm]
        # Also try with unified separators for registry vs snapshot differences.
        alt = norm.replace("/", "\\")
        if alt in apps:
            return apps[alt]
        # Basename fallback only when the basename is unique among protected apps.
        base = os.path.basename(norm)
        matches = [app for key, app in apps.items() if os.path.basename(key).lower() == base]
        return matches[0] if len(matches) == 1 else None