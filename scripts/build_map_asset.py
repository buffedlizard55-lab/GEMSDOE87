#!/usr/bin/env python3
"""Render only the already-completed result for the site, not a new experiment."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def main():
    card = json.loads((ROOT / 'docs/evidence/run_card.json').read_text())
    with rasterio.open(ROOT / 'docs/downloads' / card['submission_file']) as src:
        a = src.read(1)
    with rasterio.open(ROOT / 'data/raw/sample_submission.tif') as src:
        fp = np.isfinite(src.read(1))
    with rasterio.open(ROOT / 'data/raw/existing_faults.tif') as src:
        cat = (src.read(1) > 0) & fp
    # Contrast is visual only; the TIFF is neither rescaled nor modified.
    high = max(float(np.quantile(a[a > 0], 0.98)), 1e-8)
    v = np.sqrt(np.clip(a / high, 0, 1))
    lo, hi = np.array([222, 232, 216]), np.array([0, 111, 106])
    rgb = (lo[None, None, :] * (1 - v[:, :, None]) + hi[None, None, :] * v[:, :, None]).astype(np.uint8)
    rgb[~fp] = [237, 239, 231]
    thumb = Image.fromarray(rgb).resize((716, 812), Image.Resampling.LANCZOS)
    fault_thumb = Image.fromarray(cat.astype(np.uint8) * 255).resize((716, 812), Image.Resampling.BOX)
    fault_mask = np.asarray(fault_thumb) > 65
    buf = np.array(thumb)
    buf[fault_mask] = (buf[fault_mask].astype(float) * .35 + np.array([38, 58, 52]) * .65).astype(np.uint8)
    thumb = Image.fromarray(buf)
    image = Image.new('RGB', (1080, 820), '#edf0e8')
    image.paste(thumb, (170, 4))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 16)
        small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 12)
    except OSError:
        font = small = ImageFont.load_default()
    draw.rounded_rectangle((33, 29, 310, 85), radius=9, fill='#f9faf5', outline='#d6ded4')
    draw.text((47, 43), 'H87-GCF / GRAVITY FLANKS', fill='#1c3f39', font=font)
    draw.text((33, 110), 'NEGATIVE RESEARCH RESULT', fill='#7f4337', font=small)
    draw.line((1014, 90, 1014, 41), fill='#34594f', width=2)
    draw.polygon([(1014, 32), (1008, 46), (1020, 46)], fill='#34594f')
    draw.text((1008, 14), 'N', fill='#34594f', font=font)
    for yy in range(120, 790, 110):
        draw.line((24, yy, 32, yy), fill='#adbdaf', width=1)
        draw.line((1048, yy, 1056, yy), fill='#adbdaf', width=1)
    draw.rounded_rectangle((30, 716, 388, 789), radius=9, fill='#f9faf5', outline='#d6ded4')
    draw.line((46, 739, 73, 739), fill='#33594c', width=2)
    draw.text((83, 731), 'known faults: context only', fill='#34594f', font=small)
    draw.text((46, 756), 'contrast-enhanced confidence', fill='#5e7162', font=small)
    dest = ROOT / 'docs/assets/h87-map.png'
    image.save(dest, optimize=True)
    print(dest.relative_to(ROOT))


if __name__ == '__main__':
    main()
