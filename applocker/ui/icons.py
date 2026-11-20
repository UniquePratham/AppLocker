"""UI icon loading helpers.

Loads PNGs (brand icons, extracted app icons) into tk PhotoImages without
leaking handles: small size pool, replaced on demand. Falls back to a
generated app-glyph when no real icon is available.
"""

from __future__ import annotations

import os
import tkinter as tk
from typing import Optional

from PIL import Image, ImageDraw, ImageTk
from applocker.util.brand import render_icon


def _new_photo(path: str, size: int) -> Optional[ImageTk.PhotoImage]:
    try:
        im = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        return ImageTk.PhotoImage(im)
    except Exception:  # noqa: BLE001
        return None


def fallback_app_glyph(size: int = 40) -> Image.Image:
    """A neutral, rounded app-tile glyph used when no real icon exists."""
    img = render_icon(size)
    return img


class IconCache:
    """Caches PhotoImages per (path,size) to keep references alive."""

    def __init__(self, root: tk.Misc):
        self.root = root
        self._cache: dict[tuple, ImageTk.PhotoImage] = {}

    def get(self, path: str, size: int = 40, fallback: bool = True) -> Optional[ImageTk.PhotoImage]:
        key = (path or "", size)
        if key in self._cache:
            return self._cache[key]
        photo = None
        if path and os.path.isfile(path):
            photo = _new_photo(path, size)
        if photo is None and fallback:
            im = fallback_app_glyph(size)
            photo = ImageTk.PhotoImage(im)
        if photo:
            self._cache[key] = photo
        return photo