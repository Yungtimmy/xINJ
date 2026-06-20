"""
Generate a stats card PNG using Pillow.
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Colours
BG_TOP = (10, 10, 30)
BG_BOT = (5, 20, 50)
ACCENT = (114, 88, 255)       # Injective purple
WHITE = (255, 255, 255)
MUTED = (160, 160, 200)
GREEN = (80, 220, 130)
RED = (240, 80, 100)

WIDTH, HEIGHT = 1200, 675
PADDING = 60

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "data"))


def _gradient_bg(draw: ImageDraw.ImageDraw) -> None:
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))


def _try_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fmt_large(value: float | None, prefix: str = "$") -> str:
    if value is None:
        return "N/A"
    if value >= 1_000_000_000:
        return f"{prefix}{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{prefix}{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{prefix}{value / 1_000:.1f}K"
    return f"{prefix}{value:,.0f}"


def _fmt_pct(pct: float | None) -> tuple[str, tuple]:
    if pct is None:
        return "", MUTED
    arrow = "▲" if pct >= 0 else "▼"
    colour = GREEN if pct >= 0 else RED
    return f"{arrow} {abs(pct):.1f}%", colour


def generate_card(metrics: dict, prev: dict | None, week_label: str) -> Path:
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    _gradient_bg(draw)

    # Accent bar on left
    draw.rectangle([(0, 0), (8, HEIGHT)], fill=ACCENT)

    font_title = _try_font(52)
    font_label = _try_font(26)
    font_value = _try_font(44)
    font_pct = _try_font(24)
    font_sub = _try_font(20)

    # Header
    draw.text((PADDING, 40), "Injective Ecosystem", font=font_title, fill=WHITE)
    draw.text((PADDING, 106), f"Weekly Stats  ·  {week_label}", font=font_label, fill=MUTED)

    # Horizontal rule
    draw.rectangle([(PADDING, 148), (WIDTH - PADDING, 151)], fill=ACCENT)

    # INJ price
    price = metrics.get("inj_price")
    prev_price = (prev or {}).get("inj_price")
    pct_str, pct_col = _fmt_pct(
        _pct_change(price, prev_price)
    )
    px = WIDTH - PADDING - 220
    draw.text((px, 165), "INJ Price", font=font_label, fill=MUTED)
    draw.text((px, 195), f"${price:.2f}" if price else "N/A", font=font_value, fill=WHITE)
    draw.text((px + 10, 248), pct_str, font=font_pct, fill=pct_col)

    # Stat grid — 2 rows x 2 cols
    stats = [
        ("Total Value Locked", _fmt_large(metrics.get("tvl_usd")), metrics.get("tvl_usd"), (prev or {}).get("tvl_usd")),
        ("Active Addresses", _fmt_large(metrics.get("active_addresses"), prefix=""), metrics.get("active_addresses"), (prev or {}).get("active_addresses")),
        ("Txns (7d)", _fmt_large(_tx_count(metrics), prefix=""), _tx_count(metrics), _tx_count(prev or {})),
        ("New Contracts", _fmt_large(metrics.get("new_contracts"), prefix=""), metrics.get("new_contracts"), (prev or {}).get("new_contracts")),
    ]

    cols = 2
    col_w = (WIDTH - 2 * PADDING) // cols
    row_h = 170
    y0 = 290

    for i, (label, val_str, cur, prv) in enumerate(stats):
        col = i % cols
        row = i // cols
        x = PADDING + col * col_w
        y = y0 + row * row_h

        draw.text((x, y), label, font=font_label, fill=MUTED)
        draw.text((x, y + 34), val_str, font=font_value, fill=WHITE)
        p, pc = _fmt_pct(_pct_change(cur, prv))
        draw.text((x + 10, y + 86), p, font=font_pct, fill=pc)

    # Footer
    draw.rectangle([(0, HEIGHT - 48), (WIDTH, HEIGHT)], fill=(20, 20, 45))
    draw.text(
        (PADDING, HEIGHT - 34),
        "Data: Injective Explorer · DefiLlama · CoinGecko  |  @xINJ_bot",
        font=font_sub,
        fill=MUTED,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"stats_card_{week_label.replace(' ', '_')}.png"
    img.save(out_path, format="PNG")
    return out_path


def _tx_count(metrics: dict | None) -> int | None:
    if not metrics:
        return None
    vol = metrics.get("tx_volume")
    if isinstance(vol, dict):
        return vol.get("count") or vol.get("total")
    return None


def _pct_change(current, previous) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 1)
