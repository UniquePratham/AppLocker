"""Aegis brand mark — rendered raster artwork.

A hexagonal shield with a keyhole cut through it, drawn as a layered raster
image: vertical gradient tile, radial glow, inner shadow, specular highlight
and a soft outer drop shadow. Rendered at 8x and downsampled with Lanczos so
it stays crisp from 16px in the tray to 512px in the installer.

Outputs a multi-resolution .ico, PNGs at every Windows icon size, and runtime
PNGs for the window and tray.
"""

from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageFilter

# Brand palette
TOP = (74, 108, 255)
MID = (44, 62, 200)
BOTTOM = (14, 20, 74)
ACCENT = (72, 232, 255)
WHITE = (255, 255, 255)
INK = (10, 14, 48)

SUPERSAMPLE = 8


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _rounded_mask(size: int, radius: float) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def _hexagon(cx: float, cy: float, r: float, rotation: float = 0.0):
    pts = []
    for i in range(6):
        angle = math.radians(60 * i - 90 + rotation)
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return pts


def _keyhole(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float, colour) -> None:
    head_r = 0.082 * scale
    draw.ellipse(
        [cx - head_r, cy - head_r * 1.30, cx + head_r, cy + head_r * 0.70],
        fill=colour,
    )
    stem_top = cy + head_r * 0.40
    stem_bottom = cy + head_r * 2.45
    draw.polygon(
        [
            (cx - head_r * 0.40, stem_top),
            (cx + head_r * 0.40, stem_top),
            (cx + head_r * 0.76, stem_bottom),
            (cx - head_r * 0.76, stem_bottom),
        ],
        fill=colour,
    )


def _vertical_gradient(size: int, stops) -> Image.Image:
    """Three-stop vertical gradient."""
    grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / max(1, size - 1)
        if t < 0.5:
            colour = _lerp(stops[0], stops[1], t / 0.5)
        else:
            colour = _lerp(stops[1], stops[2], (t - 0.5) / 0.5)
        d.line([(0, y), (size, y)], fill=colour + (255,))
    return grad


def render_icon(size: int, radius: float | None = None) -> Image.Image:
    """Render the Aegis mark at ``size`` px with true rounded corners."""
    if radius is None:
        radius = size * 0.235

    big = size * SUPERSAMPLE
    big_radius = radius * SUPERSAMPLE
    mask = _rounded_mask(big, big_radius)

    # --- Base tile: three-stop gradient ---------------------------------- #
    tile = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    tile.paste(_vertical_gradient(big, (TOP, MID, BOTTOM)), (0, 0), mask)

    # --- Radial glow behind the shield ----------------------------------- #
    glow = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        [big * 0.14, big * 0.06, big * 0.86, big * 0.80],
        fill=ACCENT + (58,),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(big * 0.06))
    tile = Image.alpha_composite(tile, Image.composite(
        glow, Image.new("RGBA", (big, big), (0, 0, 0, 0)), mask
    ))

    # --- Shield with outer drop shadow ----------------------------------- #
    cx = cy = big / 2
    shield_r = big * 0.315

    shadow = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon(
        _hexagon(cx + big * 0.010, cy + big * 0.026, shield_r), fill=(0, 0, 0, 130)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(big * 0.022))
    tile = Image.alpha_composite(tile, Image.composite(
        shadow, Image.new("RGBA", (big, big), (0, 0, 0, 0)), mask
    ))

    d = ImageDraw.Draw(tile)

    # Shield body with a subtle vertical sheen
    shield_pts = _hexagon(cx, cy, shield_r)
    d.polygon(shield_pts, fill=WHITE + (255,))

    sheen = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sheen)
    sd.polygon(_hexagon(cx, cy, shield_r), fill=(226, 236, 255, 255))
    sd.polygon(_hexagon(cx, cy + big * 0.10, shield_r * 0.98), fill=(255, 255, 255, 255))
    sheen = sheen.filter(ImageFilter.GaussianBlur(big * 0.012))
    shield_mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(shield_mask).polygon(shield_pts, fill=255)
    tile = Image.alpha_composite(tile, Image.composite(
        sheen, Image.new("RGBA", (big, big), (0, 0, 0, 0)), shield_mask
    ))

    d = ImageDraw.Draw(tile)

    # Inner accent ring
    d.polygon(
        _hexagon(cx, cy, shield_r * 0.795),
        outline=ACCENT + (255,),
        width=max(1, round(big * 0.011)),
    )

    # Keyhole
    _keyhole(d, cx, cy - big * 0.010, big, INK + (255,))

    # --- Specular highlight across the top of the tile ------------------- #
    gloss = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(gloss).rounded_rectangle(
        [0, 0, big - 1, big * 0.44], radius=big_radius, fill=(255, 255, 255, 30)
    )
    gloss = gloss.filter(ImageFilter.GaussianBlur(big * 0.010))
    tile = Image.alpha_composite(tile, Image.composite(
        gloss, Image.new("RGBA", (big, big), (0, 0, 0, 0)), mask
    ))

    # --- Inner border for definition ------------------------------------- #
    border = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle(
        [0, 0, big - 1, big - 1], radius=big_radius,
        outline=(255, 255, 255, 46), width=max(1, round(big * 0.006)),
    )
    tile = Image.alpha_composite(tile, Image.composite(
        border, Image.new("RGBA", (big, big), (0, 0, 0, 0)), mask
    ))

    return tile.resize((size, size), Image.LANCZOS)


def build_assets(output_dir: str | None = None) -> dict:
    """Generate every brand asset; returns a map of name -> path."""
    if output_dir is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(base, "assets")
    png_dir = os.path.join(output_dir, "png")
    os.makedirs(png_dir, exist_ok=True)

    sizes = [16, 20, 24, 32, 48, 64, 128, 256, 512]
    results: dict[str, str] = {}

    for size in sizes:
        path = os.path.join(png_dir, f"aegis_{size}x{size}.png")
        render_icon(size).save(path, "PNG")
        results[str(size)] = path

    ico_sizes = [16, 20, 24, 32, 48, 64, 128, 256]
    imgs = [render_icon(s) for s in ico_sizes]
    ico_path = os.path.join(output_dir, "aegis.ico")
    imgs[-1].save(ico_path, format="ICO", sizes=[(s, s) for s in ico_sizes], append_images=imgs[:-1])
    results["ico"] = ico_path
    return results


def write_runtime_icons(cache_dir: str) -> str:
    """Write window/tray PNGs into ``cache_dir``; returns the 256px path."""
    os.makedirs(cache_dir, exist_ok=True)
    for size in (16, 20, 24, 32, 48, 64, 128, 256):
        render_icon(size).save(os.path.join(cache_dir, f"app_{size}.png"), "PNG")
    return os.path.join(cache_dir, "app_256.png")

def set_window_icon(window, cache_dir: str | None = None) -> None:
    """Apply the Aegis icon to a Tk window (frame + taskbar).

    ``iconphoto`` sets the window icon; ``iconbitmap`` with the .ico gives
    Windows a proper taskbar and Alt-Tab image. Both are attempted because
    each covers a different surface.
    """
    import tkinter as tk

    try:
        if cache_dir is None:
            from applocker.util.paths import get_icon_cache_dir

            cache_dir = get_icon_cache_dir()
        os.makedirs(cache_dir, exist_ok=True)

        png_path = os.path.join(cache_dir, "app_256.png")
        if not os.path.exists(png_path):
            render_icon(256).save(png_path, "PNG")

        photo = tk.PhotoImage(file=png_path)
        window.tk.call("wm", "iconphoto", window._w, photo)
        # Keep a reference so Tk does not garbage-collect the image.
        window._aegis_icon = photo  # noqa: SLF001

        ico_path = os.path.join(cache_dir, "aegis.ico")
        if not os.path.exists(ico_path):
            render_icon(256).save(ico_path, format="ICO",
                                  sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
        try:
            window.iconbitmap(ico_path)
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass