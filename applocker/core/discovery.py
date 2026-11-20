"""Application discovery.

Finds applications on the system through several real sources:

* Uninstall registry keys (HKLM + HKCU) → DisplayName + DisplayIcon/InstallLocation.
* Start Menu shortcuts (*.lnk) → resolved executable paths.
* Running processes → currently executing images.
* File picker (UI layer) → any executable the user chooses.

Produced ``DiscoveredApp`` records carry name, path, publisher and version
where the source provides them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

try:
    import winreg
    _HAS_WINREG = True
except Exception:  # noqa: BLE001
    winreg = None
    _HAS_WINREG = False


@dataclass
class DiscoveredApp:
    name: str
    path: str
    publisher: str = ""
    version: str = ""
    source: str = "registry"
    icon_path: str = ""


def _normalize_icon_entry(icon_value: str) -> Optional[str]:
    """DisplayIcon is often ``C:\\path\\app.exe,0`` or quoted + index. Handles env vars."""
    if not icon_value:
        return None
    part = icon_value.split(",")[0].strip().strip('"').strip("'")
    part = os.path.expandvars(part)
    if part.lower().endswith(".exe") and os.path.isfile(part):
        return os.path.normpath(part)
    return None


def _product_version(path: str) -> str:
    try:
        import win32api
        info = win32api.GetFileVersionInfo(path, "\\")
        trans = (info["Translation"][0][0], info["Translation"][0][1]) if "Translation" in info else (0, 0)
        try:
            key = f"\\StringFileInfo\\{trans[0]:04X}{trans[1]:04X}\\FileVersion"
            return win32api.GetFileVersionInfo(path, key) or ""
        except Exception:  # noqa: BLE001
            return ""
    except Exception:  # noqa: BLE001
        return ""


def scan_registry() -> list[DiscoveredApp]:
    """Scan uninstall keys for installed applications with real executables."""
    results: dict[str, DiscoveredApp] = {}
    if not _HAS_WINREG:
        return []
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for root, key_path in roots:
        try:
            with winreg.OpenKey(root, key_path) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sub = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, sub) as subkey:
                            name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                            display_icon = ""
                            install_loc = ""
                            version = ""
                            publisher = ""
                            for val_name in ("DisplayIcon", "InstallLocation", "DisplayVersion", "Publisher"):
                                try:
                                    v = winreg.QueryValueEx(subkey, val_name)[0]
                                    if val_name == "DisplayIcon":
                                        display_icon = v or ""
                                    elif val_name == "InstallLocation":
                                        install_loc = v or ""
                                    elif val_name == "DisplayVersion":
                                        version = v or ""
                                    elif val_name == "Publisher":
                                        publisher = v or ""
                                except FileNotFoundError:
                                    continue
                            exe = _normalize_icon_entry(display_icon)
                            if not exe and install_loc:
                                loc = os.path.expandvars(install_loc)
                                if os.path.isdir(loc):
                                    try:
                                        cands = [f for f in os.listdir(loc) if f.lower().endswith(".exe")]
                                    except OSError:
                                        cands = []
                                    # Avoid uninstall helpers.
                                    filtered = [f for f in cands if "uninstall" not in f.lower() and "unins" not in f.lower()]
                                    if filtered:
                                        cands = filtered
                                    # Prefer largest file (likely the main binary).
                                    def _sz(fn: str) -> int:
                                        try:
                                            return os.path.getsize(os.path.join(loc, fn))
                                        except OSError:
                                            return 0
                                    cands.sort(key=_sz, reverse=True)
                                    if cands:
                                        exe = os.path.join(loc, cands[0])
                            if not exe:
                                continue
                            key = exe.lower()
                            if key not in results:
                                results[key] = DiscoveredApp(
                                    name=name, path=exe, publisher=publisher or "",
                                    version=version or _product_version(exe), source="registry",
                                )
                    except (OSError, FileNotFoundError):
                        continue
        except OSError:
            continue
    return list(results.values())


def scan_start_menu() -> list[DiscoveredApp]:
    """Resolve .lnk files in the user + common Start Menu folders.

    Uses the Windows Script Host Shell link resolution. Tolerates failures.
    """
    results: list[DiscoveredApp] = []
    seen: set[str] = set()
    appdata = os.environ.get("APPDATA", "")
    programdata = os.environ.get("PROGRAMDATA", "")
    roots = []
    if appdata:
        roots.append(os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs"))
    if programdata:
        roots.append(os.path.join(programdata, r"Microsoft\Windows\Start Menu\Programs"))
    try:
        import pythoncom
        import win32com.client
        try:
            pythoncom.CoInitialize()
        except Exception:  # noqa: BLE001
            pass
        shell = win32com.client.Dispatch("WScript.Shell")
    except Exception:  # noqa: BLE001
        return []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if not fn.lower().endswith(".lnk"):
                    continue
                link_path = os.path.join(dirpath, fn)
                try:
                    shortcut = shell.CreateShortcut(link_path)
                    target = shortcut.TargetPath
                except Exception:  # noqa: BLE001
                    continue
                if not target or not target.lower().endswith(".exe") or not os.path.isfile(target):
                    continue
                if target.lower() in seen:
                    continue
                seen.add(target.lower())
                results.append(
                    DiscoveredApp(
                        name=os.path.splitext(fn)[0],
                        path=target,
                        publisher="",
                        version=_product_version(target),
                        source="startmenu",
                    )
                )
    return results


def scan_running() -> list[DiscoveredApp]:
    """Return a snapshot of currently running applications (executable images).

    Uses the Windows Toolhelp32 process snapshot (the same approach as the
    process monitor) — takes a few milliseconds and never spawns a subprocess.
    """
    results: list[DiscoveredApp] = []
    seen: set[str] = set()
    try:
        import ctypes
        import ctypes.wintypes as wt
        from applocker.util.winutil import get_process_path

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

        TH32CS_SNAPPROCESS = 0x00000002
        snapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == ctypes.c_void_p(-1).value or snapshot == 0:
            return []
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = ctypes.windll.kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
            while ok:
                path = get_process_path(int(entry.th32ProcessID))
                if path and path.lower().endswith(".exe") and os.path.isfile(path):
                    key = path.lower()
                    if key not in seen:
                        seen.add(key)
                        results.append(DiscoveredApp(
                            name=os.path.splitext(os.path.basename(path))[0],
                            path=path,
                            publisher="",
                            version=_product_version(path),
                            source="running",
                        ))
                ok = ctypes.windll.kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            ctypes.windll.kernel32.CloseHandle(snapshot)
    except Exception:  # noqa: BLE001
        return []
    return results


def discover_all() -> list[DiscoveredApp]:
    """Combine all sources, de-duplicated by executable path."""
    merged: dict[str, DiscoveredApp] = {}
    for src in (scan_registry, scan_start_menu, scan_running):
        try:
            for app in src():
                key = app.path.lower()
                if key not in merged:
                    merged[key] = app
        except Exception:  # noqa: BLE001
            continue
    return sorted(merged.values(), key=lambda a: (a.name or "").casefold())