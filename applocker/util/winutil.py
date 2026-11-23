"""Windows-specific helpers: startup entry, DPI awareness, icon extraction
from installed executables, and process path resolution.

All code here is defensive: on non-Windows platforms it degrades gracefully
so tests can run everywhere.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

try:
    import winreg
    import ctypes
    import ctypes.wintypes as wt
    _HAS_WIN = True
except Exception:  # noqa: BLE001
    winreg = None
    ctypes = None
    wt = None
    _HAS_WIN = False

if _HAS_WIN:
    try:
        from PIL import Image
    except Exception:  # noqa: BLE001
        Image = None


APP_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_VALUE_NAME = "Aegis"

_ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]


def set_dpi_awareness() -> None:
    if not _HAS_WIN:
        return
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------- #
# Startup entry (HKCU Run, user-level — no elevation)
# --------------------------------------------------------------------------- #
def is_startup_enabled() -> bool:
    if not _HAS_WIN or not winreg:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_RUN_KEY) as key:
            winreg.QueryValueEx(key, STARTUP_VALUE_NAME)
            return True
    except (FileNotFoundError, OSError):
        return False


def set_startup_enabled(enabled: bool, exe_path: Optional[str] = None) -> bool:
    """Enable/disable the HKCU Run entry (user-level, no admin required)."""
    if not _HAS_WIN or not winreg:
        return False
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, APP_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                cmd = f'"{exe_path or sys.executable}" --startup'
                winreg.SetValueEx(key, STARTUP_VALUE_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, STARTUP_VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------- #
# Process helpers
# --------------------------------------------------------------------------- #
def get_process_path(pid: int) -> str:
    if not _HAS_WIN:
        return ""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, wt.DWORD(pid))
    if not handle:
        return ""
    try:
        size = wt.DWORD(32768)
        buf = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def terminate_pid(pid: int) -> bool:
    if not _HAS_WIN:
        return False
    PROCESS_TERMINATE = 0x0001
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, wt.DWORD(pid))
    if not handle:
        return False
    try:
        return bool(ctypes.windll.kernel32.TerminateProcess(handle, 0))
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def launch_path(path: str, args: Optional[list] = None) -> bool:
    if not path or not os.path.isfile(path):
        return False
    try:
        import subprocess
        subprocess.Popen([path] + (args or []), cwd=os.path.dirname(path) or None, start_new_session=True)
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------- #
# Icon extraction
# --------------------------------------------------------------------------- #
class IconExtractor:
    """Extract and cache an executable's real icon using ``ExtractIconExW``.

    Cache key = lowercase path + requested size + file mtime so icons are
    re-extracted only when the binary actually changes.
    """

    def __init__(self, cache_dir: str, size: int = 48):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.size = size

    def _cache_file(self, exe_path: str) -> Optional[str]:
        if not exe_path:
            return None
        try:
            mtime = int(os.path.getmtime(exe_path))
        except OSError:
            mtime = 0
        import hashlib
        key = f"{exe_path.lower()}|{self.size}|{mtime}"
        return os.path.join(self.cache_dir, hashlib.sha256(key.encode()).hexdigest()[:24] + ".png")

    def get(self, exe_path: str) -> Optional[str]:
        if not _HAS_WIN or not Image or not exe_path or not os.path.isfile(exe_path):
            return None
        cache = self._cache_file(exe_path)
        if cache and os.path.exists(cache):
            return cache
        im = self._extract_image(exe_path)
        if im is None:
            return None
        im = im.resize((self.size, self.size), Image.LANCZOS)
        if cache:
            im.save(cache, "PNG")
            return cache
        tmp = os.path.join(self.cache_dir, "current.png")
        im.save(tmp, "PNG")
        return tmp

    def _extract_image(self, exe_path: str):
        """Return a PIL RGBA image of the executable's main icon, or None."""
        phicon_large = wt.HICON()
        phicon_small = wt.HICON()
        try:
            count = ctypes.windll.shell32.ExtractIconExW(exe_path, 0, ctypes.byref(phicon_large), ctypes.byref(phicon_small), 1)
        except Exception:  # noqa: BLE001
            return None
        if phicon_large:
            try:
                return self._hicon_to_image(phicon_large)
            finally:
                ctypes.windll.user32.DestroyIcon(phicon_large)
        if phicon_small:
            try:
                return self._hicon_to_image(phicon_small)
            finally:
                ctypes.windll.user32.DestroyIcon(phicon_small)
        return None

    def _hicon_to_image(self, hicon):
        """Draw an HICON into a 32-bit DIB and return RGBA PIL image."""
        SRCCOPY = 0x00CC0020
        hdc_screen = ctypes.windll.user32.GetDC(0)
        try:
            hdc_mem = ctypes.windll.gdi32.CreateCompatibleDC(hdc_screen)
            bmp = ctypes.windll.gdi32.CreateCompatibleBitmap(hdc_screen, self.size, self.size)
            old = ctypes.windll.user32.SelectObject(hdc_mem, bmp)
            try:
                ctypes.windll.user32.DrawIconEx(hdc_mem, 0, 0, hicon, self.size, self.size, 0, None, 0x0003)
            finally:
                ctypes.windll.user32.SelectObject(hdc_mem, old)

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                    ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                    ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                    ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                    ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                    ("biClrImportant", ctypes.c_uint32),
                ]

            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = self.size
            bmi.biHeight = -self.size
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0
            buf = (ctypes.c_ubyte * (self.size * self.size * 4))()
            ctypes.windll.gdi32.GetDIBits(hdc_mem, bmp, 0, self.size, buf, ctypes.byref(bmi), 0)
            arr = bytes(buf)
            im = Image.frombytes("RGBA", (self.size, self.size), arr)
            return im.transpose(Image.FLIP_TOP_BOTTOM)
        finally:
            ctypes.windll.gdi32.DeleteObject(bmp)
            ctypes.windll.gdi32.DeleteDC(hdc_mem)
            ctypes.windll.user32.ReleaseDC(0, hdc_screen)