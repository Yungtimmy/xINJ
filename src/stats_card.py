"""
Generate a stats card PNG using Pillow.
"""

from __future__ import annotations
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BG_TOP  = (10, 10, 30)
BG_BOT  = (5, 20, 50)
ACCENT  = (114, 88, 255)
WHITE   = (255, 255, 255)
MUTED   = (160, 160, 200)
GREEN   = (80, 220, 130)
RED     = (240, 80, 100)
GOLD    = (255, 200, 80)

WIDTH, HEIGHT, PADDING = 1200, 720, 56
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "data"))


def _gradient_bg(draw: ImageDraw.ImageDraw) -> None:
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fmt(v: float | None, prefix: str = "$") -> str:
    if v is None:
        return "N/A"
    if v >= 1_000_000_000:
        return f"{prefix}{v / 1e9:.2f}B"
    if v >= 1_000_000:
        return f"{prefix}{v / 1e6:.2f}M"
    if v >= 1_000:
        return f"{prefix}{v / 1e3:.1f}K"
    return f"{prefix}{v:,.0f}"


def _pct_label(cur: float | None, prv: float | None) -> tuple[str, tuple]:
    if cur is None or prv is None or prv == 0:
        return "", MUTED
    p = round((cur - prv) / abs(prv) * 100, 1)
    return (f"▲ {abs(p):.1f}%", GREEN) if p >= 0 else (f"▼ {abs(p):.1f}%", RED)


def generate_card(metrics: dict, prev: dict | None, week_label: str) -> Path:
    img  = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    _gradient_bg(draw)

    # Left accent bar
    draw.rectangle([(0, 0), (7, HEIGHT)], fill=ACCENT)

    # ── Header ──────────────────────────────────────────────────────────────
    draw.text((PADDING, 36), "Injective Ecosystem", font=_font(50), fill=WHITE)
    draw.text((PADDING, 100), f"Weekly Stats  ·  {week_label}", font=_font(24), fill=MUTED)
    draw.rectangle([(PADDING, 138), (WIDTH - PADDING, 141)], fill=ACCENT)

    # ── INJ Price (top-right) ────────────────────────────────────────────────
    price     = metrics.get("inj_price")
    prev_price = (prev or {}).get("inj_price")
    ps, pc    = _pct_label(price, prev_price)
    px = WIDTH - PADDING - 210
    draw.text((px, 152), "INJ Price", font=_font(22), fill=MUTED)
    draw.text((px, 178), f"${price:.2f}" if price else "N/A", font=_font(42), fill=WHITE)
    draw.text((px + 6, 228), ps, font=_font(22), fill=pc)

    # ── Top stat row: TVL · Txns · Active Addrs · NFT Vol ───────────────────
    p = prev or {}
    top_stats = [
        ("Total Value Locked",  _fmt(metrics.get("tvl_usd")),         metrics.get("tvl_usd"),          p.get("tvl_usd")),
        ("7D Transactions",     _fmt(metrics.get("weekly_txns"), ""),  metrics.get("weekly_txns"),      p.get("weekly_txns")),
        ("Active Addresses",    _fmt(metrics.get("active_addresses"), ""), metrics.get("active_addresses"), p.get("active_addresses")),
        ("NFT Vol (Talis)",     _fmt(metrics.get("nft_volume_talis")), metrics.get("nft_volume_talis"), p.get("nft_volume_talis")),
    ]

    col_w = (WIDTH - 2 * PADDING) // 4
    for i, (label, val_str, cur, prv2) in enumerate(top_stats):
        x = PADDING + i * col_w
        y = 270
        draw.text((x, y), label, font=_font(19), fill=MUTED)
        draw.text((x, y + 28), val_str, font=_font(36), fill=WHITE)
        pl, plc = _pct_label(cur, prv2)
        draw.text((x + 4, y + 72), pl, font=_font(19), fill=plc)

    # Divider
    draw.rectangle([(PADDING, 380), (WIDTH - PADDING, 382)], fill=(50, 50, 90))

    # ── Dapp leaderboard ─────────────────────────────────────────────────────
    draw.text((PADDING, 394), "Top Dapps — 7D Volume", font=_font(22), fill=MUTED)

    dapp_vols: dict = metrics.get("dapp_volumes") or {}
    prev_vols: dict = (prev or {}).get("dapp_volumes") or {}
    sorted_dapps = sorted(dapp_vols.items(), key=lambda x: x[1], reverse=True)

    bar_max   = sorted_dapps[0][1] if sorted_dapps and sorted_dapps[0][1] > 0 else 1
    bar_area_w = WIDTH - 2 * PADDING - 340
    row_h      = 46
    y0         = 428

    for i, (name, vol) in enumerate(sorted_dapps[:6]):
        y = y0 + i * row_h
        rank_col = GOLD if i == 0 else WHITE
        draw.text((PADDING, y), f"{i+1}.", font=_font(20), fill=rank_col)
        draw.text((PADDING + 32, y), name, font=_font(20), fill=WHITE)

        # Volume bar
        bar_x   = PADDING + 220
        bar_len  = int((vol / bar_max) * bar_area_w) if bar_max > 0 else 0
        draw.rectangle([(bar_x, y + 6), (bar_x + bar_len, y + 26)], fill=ACCENT)

        # Volume label
        vol_str = _fmt(vol)
        draw.text((bar_x + bar_len + 10, y + 4), vol_str, font=_font(20), fill=WHITE)

        # WoW change
        prev_vol = prev_vols.get(name)
        pl, plc  = _pct_label(vol if vol else None, prev_vol if prev_vol else None)
        draw.text((WIDTH - PADDING - 100, y + 4), pl, font=_font(18), fill=plc)

    # ── Footer ───────────────────────────────────────────────────────────────
    draw.rectangle([(0, HEIGHT - 44), (WIDTH, HEIGHT)], fill=(18, 18, 42))
    draw.text(
        (PADDING, HEIGHT - 30),
        "Data: Injective Explorer · DefiLlama · CoinGecko · Talis  |  @xINJ_bot",
        font=_font(18),
        fill=MUTED,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"stats_card_{week_label.replace(' ', '_')}.png"
    img.save(out, "PNG")
    return out
