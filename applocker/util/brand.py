"""AppLocker brand icon generation.

Creates a distinctive, professional application mark — a rounded square
containing an app-window with a floating lock/shield motif — and renders it at
every resolution the product needs:

* ``.ico`` (multi-res: 16, 20, 24, 32, 48, 64, 128, 256)
* PNGs at 16/32/48/64/128/256
* single "app icon" fallback PNG used by the UI

All artwork is vector-drawn (anti-aliased, rasterized per size) so it stays
crisp at every DPI. The result is written to ``assets/`` at build time and to
the application cache at runtime.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw


def _rounded_mask(size: int, radius: float) -> Image.Image:
    """Return an L-mode mask with the standard rounded-square shape."""
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def render_icon(size: int, radius: float | None = None) -> Image.Image:
    """Render the AppLocker icon at ``size`` with correct outer corners."""
    if radius is None:
        radius = size * 0.22  # Fluent-style squircle radius
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Flat, confident azure background (crisp; deliberately no gradient).
    azure = (10, 90, 169)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=azure + (255,))

    # The protection mark: a clean white shield with a navy keyhole lock.
    # A shield embodies "protection/privacy" without being a generic padlock.
    sw = size * 0.075  # stroke width
    inner = size * 0.30
    shield_top = size * 0.30
    shield_bot = size * 0.76
    cx = size * 0.50
    shield = [
        (cx - inner / 2, shield_top + inner * 0.18),
        (cx + inner / 2, shield_top + inner * 0.18),
        (cx + inner * 0.34, shield_top + inner * 0.42),
        (cx + inner * 0.34, shield_bot - inner * 0.10),
        (cx, shield_bot - inner * 0.04),
        (cx - inner * 0.34, shield_bot - inner * 0.10),
        (cx - inner * 0.34, shield_top + inner * 0.42),
    ]
    d.polygon(shield, fill=(255, 255, 255, 255))
    # Small centered navy lock cutout inside the shield.
    navy = (7, 40, 70)
    lock_w = max(inner * 0.30, 2)
    lock_h = max(inner * 0.26, 2)
    lock_x0 = cx - lock_w / 2
    lock_y0 = shield_top + inner * 0.40
    lock_body = [lock_x0 + sw, lock_y0, lock_x0 + lock_w - sw, lock_y0 + lock_h]
    if lock_body[2] > lock_body[0] and lock_body[3] > lock_body[1]:
        d.rounded_rectangle(lock_body, radius=size * 0.02, fill=navy + (255,))
    shackle_x0 = cx - lock_w * 0.32
    shackle_w = lock_w * 0.64
    shackle_h = lock_h * 0.55
    d.arc(
        [shackle_x0, lock_y0 - shackle_h, shackle_x0 + shackle_w, lock_y0 + shackle_h * 0.35],
        start=180, end=360, fill=navy + (255,), width=max(1, int(sw * 1.2)),
    )
    # Mint check overlay: success/security affordance.
    check_c = (110, 235, 165, 255)
    d.line([(lock_x0 + lock_w * 0.32, lock_y0 + lock_h * 0.55),
            (cx - size * 0.01, lock_y0 + lock_h * 0.80)],
           fill=check_c, width=max(1, int(size * 0.035)))
    d.line([(cx - size * 0.01, lock_y0 + lock_h * 0.80),
            (lock_x0 + lock_w * 0.72, lock_y0 + lock_h * 0.28)],
           fill=check_c, width=max(1, int(size * 0.035)))

    # Apply the rounded-square mask so the corners are truly transparent.
    mask = _rounded_mask(size, radius)
    img.putalpha(mask)
    return img


def build_assets(output_dir: str | None = None) -> dict:
    """Generate all brand assets; returns map of size → path."""
    if output_dir is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(base, "assets")
    os.makedirs(output_dir, exist_ok=True)
    png_dir = os.path.join(output_dir, "png")
    os.makedirs(png_dir, exist_ok=True)

    sizes = [16, 20, 24, 32, 48, 64, 128, 256, 512]
    results: dict[str, str] = {}

    # PNGs
    for size in sizes:
        img = render_icon(size)
        path = os.path.join(png_dir, f"applocker_{size}x{size}.png")
        img.save(path, "PNG")
        results[f"{size}"] = path

    # ICO (multi-res)
    ico_path = os.path.join(output_dir, "applocker.ico")
    ico_sizes = [16, 20, 24, 32, 48, 64, 128, 256]
    imgs = [render_icon(s) for s in ico_sizes]
    imgs[0].save(ico_path, format="ICO", sizes=[(s, s) for s in ico_sizes], append_images=imgs[1:])
    results["ico"] = ico_path
    return results


def write_runtime_icons(cache_dir: str) -> str:
    """Write a small set of runtime PNGs (window/tray) into the cache dir.

    Returns the 256px path used as the window icon.
    """
    os.makedirs(cache_dir, exist_ok=True)
    for size in (16, 32, 48, 256):
        path = os.path.join(cache_dir, f"app_{size}.png")
        render_icon(size).save(path, "PNG")
    return os.path.join(cache_dir, "app_256.png")