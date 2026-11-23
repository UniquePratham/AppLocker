"""Icon loading for the Aegis UI.

Returns ``CTkImage`` objects so CustomTkinter can scale them for HighDPI
displays. Falls back to a generated brand glyph when no real icon exists.
"""

from __future__ import annotations

import os
from typing import Optional

import customtkinter as ctk
from PIL import Image

from applocker.util.brand import render_icon


def _load(path: str, size: int) -> Optional[Image.Image]:
    try:
        return Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
    except Exception:  # noqa: BLE001
        return None


class IconCache:
    """Caches ``CTkImage`` objects per (path, size)."""

    def __init__(self, root=None):
        self.root = root
        self._cache: dict[tuple, ctk.CTkImage] = {}

    def get(self, path: str, size: int = 40, fallback: bool = True) -> Optional[ctk.CTkImage]:
        key = (path or "", size)
        if key in self._cache:
            return self._cache[key]

        image = None
        if path and os.path.isfile(path):
            image = _load(path, size)
        if image is None and fallback:
            image = render_icon(size)
        if image is None:
            return None

        ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
        self._cache[key] = ctk_image
        return ctk_image