"""
Generate a stats card PNG using Pillow.
"""

from __future__ import annotations
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BG_TOP  = (8, 8, 24)
BG_BOT  = (4, 16, 42)
ACCENT  = (114, 88, 255)
WHITE   = (255, 255, 255)
MUTED   = (150, 150, 195)
GREEN   = (72, 210, 120)
RED     = (235, 75, 95)
GOLD    = (255, 195, 60)
DIM     = (90, 90, 130)

WIDTH, HEIGHT, PAD = 1200, 740, 52
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "data"))

DAPP_ORDER = ["Helix", "Mito", "Hydro", "DojoSwap", "Black Panther", "Neptune", "Choice"]


def _gradient(draw: ImageDraw.ImageDraw) -> None:
    for y in range(HEIGHT):
        t = y / HEIGHT
        draw.line(
            [(0, y), (WIDTH, y)],
            fill=(
                int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t),
                int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t),
                int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t),
            ),
        )


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


def _pct(cur: float | None, prv: float | None) -> tuple[str, tuple]:
    if cur is None or prv is None or prv == 0:
        return "", DIM
    p = round((cur - prv) / abs(prv) * 100, 1)
    return (f"▲ {abs(p):.1f}%", GREEN) if p >= 0 else (f"▼ {abs(p):.1f}%", RED)


def generate_card(metrics: dict, prev: dict | None, week_label: str) -> Path:
    img  = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    _gradient(draw)

    draw.rectangle([(0, 0), (6, HEIGHT)], fill=ACCENT)

    # ── Header ──────────────────────────────────────────────────────────────
    draw.text((PAD, 30), "Injective Ecosystem", font=_font(48), fill=WHITE)
    draw.text((PAD, 92), f"Weekly Stats  ·  {week_label}", font=_font(22), fill=MUTED)
    draw.rectangle([(PAD, 128), (WIDTH - PAD, 130)], fill=ACCENT)

    p = prev or {}

    # ── INJ Price (top right) ────────────────────────────────────────────────
    price      = metrics.get("inj_price")
    ps, pc     = _pct(price, p.get("inj_price"))
    rx = WIDTH - PAD - 200
    draw.text((rx, 140), "INJ Price", font=_font(20), fill=MUTED)
    draw.text((rx, 164), f"${price:.2f}" if price else "N/A", font=_font(40), fill=WHITE)
    draw.text((rx + 4, 212), ps, font=_font(20), fill=pc)

    # ── Top stats row ────────────────────────────────────────────────────────
    top_stats = [
        ("TVL",          _fmt(metrics.get("tvl_usd")),          metrics.get("tvl_usd"),         p.get("tvl_usd")),
        ("DEX Vol 7D",   _fmt(metrics.get("dex_volume_7d")),    metrics.get("dex_volume_7d"),   p.get("dex_volume_7d")),
        ("Chain Fees 7D",_fmt(metrics.get("chain_fees_7d")),    metrics.get("chain_fees_7d"),   p.get("chain_fees_7d")),
        ("Revenue 7D",   _fmt(metrics.get("chain_revenue_7d")), metrics.get("chain_revenue_7d"),p.get("chain_revenue_7d")),
    ]

    col_w = (WIDTH - 2 * PAD) // len(top_stats)
    for i, (label, val_str, cur, prv2) in enumerate(top_stats):
        x = PAD + i * col_w
        draw.text((x, 248), label, font=_font(17), fill=MUTED)
        draw.text((x, 270), val_str, font=_font(32), fill=WHITE)
        pl, plc = _pct(cur, prv2)
        draw.text((x + 2, 308), pl, font=_font(17), fill=plc)

    # Divider
    draw.rectangle([(PAD, 342), (WIDTH - PAD, 344)], fill=(45, 45, 85))

    # ── Dapp leaderboard (ranked by TVL) ──────────────────────────────────────
    draw.text((PAD, 354), "Top Dapps by TVL", font=_font(20), fill=MUTED)

    dapp_stats = metrics.get("dapp_stats") or {}
    prev_dapps = p.get("dapp_stats") or {}

    ranked = sorted(
        DAPP_ORDER,
        key=lambda n: (dapp_stats.get(n) or {}).get("tvl", 0),
        reverse=True,
    )
    bar_max    = max(((dapp_stats.get(n) or {}).get("tvl", 0) for n in ranked), default=1) or 1
    bar_area_w = WIDTH - 2 * PAD - 320
    row_h      = 50
    y0         = 384

    medals = ["①", "②", "③", "④", "⑤", "⑥", "⑦"]
    for i, name in enumerate(ranked):
        s        = dapp_stats.get(name) or {}
        tvl_v    = s.get("tvl", 0)
        vol_v    = s.get("volume_7d", 0)
        y        = y0 + i * row_h
        rank_col = GOLD if i == 0 else WHITE
        draw.text((PAD, y + 6), medals[i], font=_font(18), fill=rank_col)
        draw.text((PAD + 28, y + 6), name, font=_font(19), fill=WHITE)

        bar_x   = PAD + 210
        bar_len = max(4, int((tvl_v / bar_max) * bar_area_w)) if tvl_v > 0 else 0
        if bar_len:
            bar_col = ACCENT if i == 0 else (70, 55, 160)
            draw.rectangle([(bar_x, y + 10), (bar_x + bar_len, y + 30)], fill=bar_col)

        # TVL label, plus volume in muted text when present
        label = _fmt(tvl_v) if tvl_v else "–"
        draw.text((bar_x + bar_len + 10, y + 6), label, font=_font(19), fill=WHITE)
        if vol_v:
            draw.text((bar_x + bar_len + 10, y + 28), f"vol {_fmt(vol_v)}", font=_font(13), fill=MUTED)

        prev_v  = (prev_dapps.get(name) or {}).get("tvl")
        pl, plc = _pct(tvl_v if tvl_v else None, prev_v if prev_v else None)
        if pl:
            draw.text((WIDTH - PAD - 90, y + 6), pl, font=_font(17), fill=plc)

    # ── Footer ───────────────────────────────────────────────────────────────
    draw.rectangle([(0, HEIGHT - 42), (WIDTH, HEIGHT)], fill=(16, 16, 40))
    draw.text(
        (PAD, HEIGHT - 28),
        "Data: Injective Explorer · DefiLlama · CoinGecko · Talis  |  @xINJ_bot",
        font=_font(17),
        fill=MUTED,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"stats_card_{week_label.replace(' ', '_')}.png"
    img.save(out, "PNG")
    return out
