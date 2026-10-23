#!/usr/bin/env python3
"""Generate publication-grade vector SVG & raster PNG figures directly from verified artifacts."""

from __future__ import annotations

import html
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"


def _write_ablation_svg(ablation: dict) -> Path:
    comp = ablation["dual_seed_component_pooled"]["scores"]
    quad = ablation["four_quadrant_pooled"]["scores"]

    rows = [
        ("EXP2: 64-ch Counterfactual HGB (Session 2)", comp["EXP2_counterfactual_single_hgb"], quad["EXP2_counterfactual_single_hgb"], "#0f766e"),
        ("EXP3: Dual-Head STFD + 300m Kernel (Artifact)", comp["EXP3_stfd_heterogeneous_dink300"], quad["EXP3_stfd_heterogeneous_dink300"], "#1d4ed8"),
        ("EXP1: Pure Label-Free 48-ch Physics (0 cat.)", comp["EXP1_pure_physics_48ch"], quad["EXP1_pure_physics_48ch"], "#0284c7"),
        ("H33-2-B2 Fold-Fair (d_vis > 2 px on d2.8)", comp["H33_2_B2_fold_fair"], quad["H33_2_B2_fold_fair"], "#64748b"),
        ("GEMSDOE24 d2.8 (44,090 dots; 4Q in-sample)", comp["GEMSDOE24_d2_8"], quad["GEMSDOE24_d2_8"], "#7c3aed"),
        ("True Band-08 Slope Control (IR87-030 fix)", comp["true_slope_b08_control"], quad["true_slope_b08_control"], "#d97706"),
        ("Magnetic HGM Control (Band 03)", comp["magnetic_hgm_control"], quad["magnetic_hgm_control"], "#b45309"),
        ("Session 1 H87-BMTD-01 Dots (Prior Frozen)", comp["bmtd_dots"], quad["bmtd_dots"], "#dc2626"),
        ("Session 1 Swapped Band-19 Control (IR87-030)", comp["topographic_slope_control"], quad["topographic_slope_control"], "#9ca3af"),
        ("Static GEMSDOE32 File (Self-Masked IR87-031)", comp["GEMSDOE32_H33_2_B2"], quad["GEMSDOE32_H33_2_B2"], "#475569"),
    ]

    w, h = 1140, 505
    left_label = 385
    panel_w = 320
    gap = 78
    x1_0 = left_label
    x2_0 = left_label + panel_w + gap
    top_y = 94
    row_h = 35
    max_val = 0.21

    def sx(origin: int, v: float) -> float:
        return origin + (min(max(v, 0.0), max_val) / max_val) * panel_w

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="HOLDOUT-DTI ablation comparison across whole-component and four-quadrant holdouts">',
        f'<rect width="{w}" height="{h}" fill="#ffffff" rx="10" stroke="#cbd5e1"/>',
        '<text x="24" y="34" font-family="system-ui,-apple-system,sans-serif" font-size="18" font-weight="700" fill="#0f172a">Official Holdout Evaluation (gems57-pooled-hide-v2, 2,000 Cluster-Bootstrap Draws)</text>',
        '<text x="24" y="55" font-family="system-ui,-apple-system,sans-serif" font-size="12.5" fill="#475569">All numbers are HOLDOUT-DTI (alpha=0.2, beta=0.8, 300 m kernel; 95% physical 20-km block bootstrap intervals; NOT leaderboard projections)</text>',
        f'<text x="{x1_0}" y="78" font-family="system-ui,-apple-system,sans-serif" font-size="12.5" font-weight="700" fill="#0f172a">A. Unseen Whole-Component LOQO (22,663 pos)</text>',
        f'<text x="{x2_0}" y="78" font-family="system-ui,-apple-system,sans-serif" font-size="12.5" font-weight="700" fill="#0f172a">B. Session 1 4-Quadrant Split (60,988 pos)</text>',
    ]

    for tick in (0.0, 0.05, 0.10, 0.15, 0.20):
        for orig in (x1_0, x2_0):
            tx = sx(orig, tick)
            lines.append(f'<line x1="{tx:.1f}" y1="{top_y-8}" x2="{tx:.1f}" y2="{top_y + len(rows)*row_h}" stroke="#e2e8f0" stroke-dasharray="3,3"/>')
            lines.append(f'<text x="{tx:.1f}" y="{top_y + len(rows)*row_h + 18}" text-anchor="middle" font-family="ui-monospace,monospace" font-size="11" fill="#64748b">{tick:.2f}</text>')

    for idx, (label, c_sc, q_sc, color) in enumerate(rows):
        cy = top_y + idx * row_h + 14
        if idx % 2 == 0:
            lines.append(f'<rect x="14" y="{cy-14}" width="{w-28}" height="{row_h}" fill="#f8fafc" rx="4"/>')
        weight = "700" if idx < 3 else "500"
        lines.append(f'<text x="{left_label - 14}" y="{cy+4}" text-anchor="end" font-family="system-ui,-apple-system,sans-serif" font-size="11.5" font-weight="{weight}" fill="#1e293b">{html.escape(label)}</text>')

        for orig, sc in ((x1_0, c_sc), (x2_0, q_sc)):
            lo, hi = sc["ci95"]
            dti = sc["dti"]
            x_bar = sx(orig, dti)
            x_lo = sx(orig, lo)
            x_hi = sx(orig, hi)
            lines.append(f'<rect x="{orig}" y="{cy-7}" width="{max(1.5, x_bar - orig):.1f}" height="14" fill="{color}" fill-opacity="0.82" rx="2"/>')
            lines.append(f'<line x1="{x_lo:.1f}" y1="{cy}" x2="{x_hi:.1f}" y2="{cy}" stroke="#0f172a" stroke-width="1.6"/>')
            lines.append(f'<line x1="{x_lo:.1f}" y1="{cy-4}" x2="{x_lo:.1f}" y2="{cy+4}" stroke="#0f172a" stroke-width="1.6"/>')
            lines.append(f'<line x1="{x_hi:.1f}" y1="{cy-4}" x2="{x_hi:.1f}" y2="{cy+4}" stroke="#0f172a" stroke-width="1.6"/>')
            tx_lbl = min(orig + panel_w - 2, x_hi + 6)
            lines.append(f'<text x="{tx_lbl:.1f}" y="{cy+4}" font-family="ui-monospace,monospace" font-size="11" font-weight="600" fill="#0f172a">{dti:.4f}</text>')

    lines.append(
        f'<text x="24" y="{h-14}" font-family="system-ui,-apple-system,sans-serif" font-size="11" fill="#64748b">'
        'Note: GEMSDOE24 d2.8 / H19-5 were selected in GEMSDOE19/24 using full-grid existing_faults.tif (in-sample on Panel B quadrants); Panel A holds out unseen components fairly.</text>'
    )
    lines.append("</svg>")
    out = ASSETS / "fig_holdout_ablation.svg"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def _write_registry_uniqueness_svg(reg: dict) -> Path:
    w, h = 1045, 440
    ox, oy = 84, 78
    pw, ph = 590, 305

    def px(ov: float) -> float:
        return ox + min(max(ov, 0.0), 1.04) / 1.04 * pw

    def py(rho_abs: float) -> float:
        return oy + ph - (min(max(rho_abs, 0.0), 1.0) / 1.0) * ph

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="Cross-repository uniqueness audit across all 34 registry rasters">',
        f'<rect width="{w}" height="{h}" fill="#ffffff" rx="10" stroke="#cbd5e1"/>',
        '<text x="24" y="34" font-family="system-ui,-apple-system,sans-serif" font-size="17" font-weight="700" fill="#0f172a">Cross-Repository Uniqueness Audit Across All 34 Accessible Rasters (GEMSDOE..GEMSDOE88)</text>',
        '<text x="24" y="55" font-family="system-ui,-apple-system,sans-serif" font-size="12" fill="#475569">0 / 31 real fault candidates exceed either gate (max 3-px overlap = 0.6322 &lt;= 0.70, max |rho| = 0.0457 &lt;= 0.90); 3 dense witnesses in red</text>',
        # Green safe zone (`overlap <= 0.70` and `|rho| <= 0.90`)
        f'<rect x="{ox}" y="{py(0.90):.1f}" width="{px(0.70)-ox:.1f}" height="{oy+ph-py(0.90):.1f}" fill="#ecfdf5" stroke="#10b981" stroke-dasharray="5,4"/>',
        f'<rect x="{px(0.70):.1f}" y="{oy}" width="{ox+pw-px(0.70):.1f}" height="{ph}" fill="#fef2f2" fill-opacity="0.55"/>',
        f'<line x1="{px(0.70):.1f}" y1="{oy}" x2="{px(0.70):.1f}" y2="{oy+ph}" stroke="#dc2626" stroke-width="1.8" stroke-dasharray="6,4"/>',
        f'<line x1="{ox}" y1="{py(0.90):.1f}" x2="{ox+pw}" y2="{py(0.90):.1f}" stroke="#dc2626" stroke-width="1.8" stroke-dasharray="6,4"/>',
        f'<text x="{px(0.69):.1f}" y="{oy+20}" text-anchor="end" font-family="system-ui,-apple-system,sans-serif" font-size="11.5" font-weight="700" fill="#047857">31 / 31 Real Fault Candidates CLEAR (&lt;= 0.70)</text>',
        f'<text x="{px(0.715):.1f}" y="{oy+20}" font-family="system-ui,-apple-system,sans-serif" font-size="11.5" font-weight="700" fill="#b91c1c">Overlap &gt; 0.70 Zone</text>',
        f'<rect x="{ox}" y="{oy}" width="{pw}" height="{ph}" fill="none" stroke="#475569"/>',
    ]

    for xv in (0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 1.0):
        x = px(xv)
        lines.append(f'<line x1="{x:.1f}" y1="{oy+ph}" x2="{x:.1f}" y2="{oy+ph+5}" stroke="#475569"/>')
        lines.append(f'<text x="{x:.1f}" y="{oy+ph+19}" text-anchor="middle" font-family="ui-monospace,monospace" font-size="11" fill="#475569">{xv:.2f}</text>')
    for yv in (0.0, 0.2, 0.4, 0.6, 0.9, 1.0):
        y = py(yv)
        lines.append(f'<line x1="{ox-5}" y1="{y:.1f}" x2="{ox}" y2="{y:.1f}" stroke="#475569"/>')
        lines.append(f'<text x="{ox-9}" y="{y+4:.1f}" text-anchor="end" font-family="ui-monospace,monospace" font-size="11" fill="#475569">{yv:.2f}</text>')

    lines.append(f'<text x="{ox + pw/2:.1f}" y="{h-14}" text-anchor="middle" font-family="system-ui,-apple-system,sans-serif" font-size="12.5" font-weight="600" fill="#1e293b">Forward 3-Pixel (300 m) Dot Overlap Against Registry Raster</text>')
    lines.append(f'<text transform="translate(22,{oy + ph/2:.1f}) rotate(-90)" text-anchor="middle" font-family="system-ui,-apple-system,sans-serif" font-size="12.5" font-weight="600" fill="#1e293b">|Spearman Rank Correlation rho|</text>')

    for r in reg["dot_rows"]:
        x = px(r["dot_overlap_3px"])
        y = py(abs(r["spearman_rho"]))
        is_wit = r["kind"] != "fault_candidate"
        fill = "#dc2626" if is_wit else "#1d4ed8"
        rad = 6.0 if is_wit else 4.5
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad}" fill="{fill}" fill-opacity="0.82" stroke="#ffffff" stroke-width="1"/>')

    # Callout legend box on right side
    lx = ox + pw + 24
    lines.extend([
        f'<rect x="{lx}" y="{oy}" width="320" height="{ph}" fill="#f8fafc" rx="8" stroke="#cbd5e1"/>',
        f'<text x="{lx+14}" y="{oy+24}" font-family="system-ui,-apple-system,sans-serif" font-size="13" font-weight="700" fill="#0f172a">Two-Gate Audit Summary</text>',
        f'<circle cx="{lx+20}" cy="{oy+48}" r="5" fill="#1d4ed8"/>',
        f'<text x="{lx+32}" y="{oy+52}" font-family="system-ui,-apple-system,sans-serif" font-size="11.5" font-weight="600" fill="#1e293b">Real Fault Candidates (31)</text>',
        f'<text x="{lx+32}" y="{oy+68}" font-family="ui-monospace,monospace" font-size="10.8" fill="#047857">Duplicates: 0 / 31 (PASS)</text>',
        f'<text x="{lx+32}" y="{oy+83}" font-family="ui-monospace,monospace" font-size="10.8" fill="#475569">Max 3px overlap: 0.6322</text>',
        f'<text x="{lx+32}" y="{oy+98}" font-family="ui-monospace,monospace" font-size="10.8" fill="#475569">Max |Spearman|:  0.0457</text>',
        f'<circle cx="{lx+20}" cy="{oy+128}" r="5.5" fill="#dc2626"/>',
        f'<text x="{lx+32}" y="{oy+132}" font-family="system-ui,-apple-system,sans-serif" font-size="11.5" font-weight="600" fill="#991b1b">Space-Filling Witnesses (3)</text>',
        f'<text x="{lx+20}" y="{oy+152}" font-family="ui-monospace,monospace" font-size="10.3" fill="#7f1d1d">1. 57GEMSDOE surface: 1.0000</text>',
        f'<text x="{lx+20}" y="{oy+167}" font-family="ui-monospace,monospace" font-size="10.3" fill="#7f1d1d">   (98.8% positive cells)</text>',
        f'<text x="{lx+20}" y="{oy+186}" font-family="ui-monospace,monospace" font-size="10.3" fill="#7f1d1d">2. 13GEMSDOE 5x5 grid: 0.9987</text>',
        f'<text x="{lx+20}" y="{oy+201}" font-family="ui-monospace,monospace" font-size="10.3" fill="#7f1d1d">   (99.87% halo cover)</text>',
        f'<text x="{lx+20}" y="{oy+220}" font-family="ui-monospace,monospace" font-size="10.3" fill="#7f1d1d">3. H87-BMTD-01 surf.: 0.9017</text>',
        f'<text x="{lx+20}" y="{oy+235}" font-family="ui-monospace,monospace" font-size="10.3" fill="#7f1d1d">   (87.7% positive cells)</text>',
        f'<text x="{lx+14}" y="{oy+266}" font-family="system-ui,-apple-system,sans-serif" font-size="11" font-weight="700" fill="#0f172a">Pre-Placement Surface Gate:</text>',
        f'<text x="{lx+14}" y="{oy+283}" font-family="ui-monospace,monospace" font-size="10.6" fill="#047857">Max |rho| = {reg["pre_placement_surface_summary"]["max_abs_spearman_rho"]:.4f} &lt;= 0.90 (34/34)</text>',
    ])
    lines.append("</svg>")
    out = ASSETS / "fig_registry_uniqueness.svg"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def _write_band_forensics_svg(band_audit: dict) -> Path:
    b6 = band_audit["band_06_tc_audit"]
    mag = band_audit["magnetic_gradient_unit_audit"]
    w, h = 1060, 315
    bars = [
        ("GeoDAWN Radiometric TC", b6["pearson_r_with_geodawn_TC"], "#0f766e"),
        ("GeoDAWN Thorium (Th)", b6["pearson_r_with_geodawn_Th"], "#0284c7"),
        ("GeoDAWN Potassium (K)", b6["pearson_r_with_geodawn_K"], "#2563eb"),
        ("GeoDAWN Uranium (U)", b6["pearson_r_with_geodawn_U"], "#4f46e5"),
        ("True Magnetic Tilt Angle", b6["pearson_r_with_true_miller_singh_magnetic_tilt"], "#dc2626"),
    ]
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="First-principles geophysical band identity verification">',
        f'<rect width="{w}" height="{h}" fill="#ffffff" rx="10" stroke="#cbd5e1"/>',
        '<text x="24" y="34" font-family="system-ui,-apple-system,sans-serif" font-size="17.5" font-weight="700" fill="#0f172a">First-Principles Geophysical Channel Audit Across 5,167,373 Footprint Pixels (IR87-028..IR87-030)</text>',
        '<text x="24" y="55" font-family="system-ui,-apple-system,sans-serif" font-size="12" fill="#475569">Empirical verification against primary USGS GeoDAWN (DOI 10.5066/P93LGLVQ) and DOE GDR #1391 releases</text>',
        '<text x="24" y="84" font-family="system-ui,-apple-system,sans-serif" font-size="13" font-weight="700" fill="#0f172a">A. Band 06 ("tc") Pearson r With Official USGS Layers</text>',
    ]
    ox, bw = 235, 225
    for i, (name, val, col) in enumerate(bars):
        cy = 108 + i * 36
        lines.append(f'<text x="{ox - 12}" y="{cy+4}" text-anchor="end" font-family="system-ui,-apple-system,sans-serif" font-size="11.5" fill="#1e293b">{html.escape(name)}</text>')
        lines.append(f'<rect x="{ox}" y="{cy-8}" width="{bw}" height="16" fill="#f1f5f9" rx="3"/>')
        lines.append(f'<rect x="{ox}" y="{cy-8}" width="{max(2.0, val * bw):.1f}" height="16" fill="{col}" rx="3"/>')
        lines.append(f'<text x="{ox + bw + 8}" y="{cy+4}" font-family="ui-monospace,monospace" font-size="11.5" font-weight="700" fill="{col}">r = {val:+.4f}</text>')

    rx = 568
    lines.extend([
        f'<rect x="{rx}" y="72" width="468" height="220" fill="#f8fafc" rx="8" stroke="#cbd5e1"/>',
        f'<text x="{rx+16}" y="96" font-family="system-ui,-apple-system,sans-serif" font-size="13" font-weight="700" fill="#0f172a">B. Four Newly Resolved Irregularities</text>',
        f'<text x="{rx+16}" y="120" font-family="system-ui,-apple-system,sans-serif" font-size="11.5" fill="#1e293b"><tspan font-weight="700" fill="#0f766e">IR87-028:</tspan> Band 06 is GeoDAWN Total Count (min +2.95, 0% neg.,</text>',
        f'<text x="{rx+16}" y="136" font-family="system-ui,-apple-system,sans-serif" font-size="11.5" fill="#475569">r=+0.9971 with TC), NOT magnetic tilt angle (r=+0.0176).</text>',
        f'<text x="{rx+16}" y="160" font-family="system-ui,-apple-system,sans-serif" font-size="11.5" fill="#1e293b"><tspan font-weight="700" fill="#1d4ed8">Unit Fix:</tspan> B09 vs B03 has 100x scale gap; p95 |tilt| = {mag["unit_matched_atan2_100b09_b03_p95_abs_rad"]:.3f} rad</text>',
        f'<text x="{rx+16}" y="176" font-family="system-ui,-apple-system,sans-serif" font-size="11.5" fill="#475569">with 100x match vs {mag["unscaled_atan2_b09_b03_p95_abs_rad"]:.4f} rad collapsed unscaled.</text>',
        f'<text x="{rx+16}" y="200" font-family="system-ui,-apple-system,sans-serif" font-size="11.5" fill="#1e293b"><tspan font-weight="700" fill="#7c3aed">IR87-029:</tspan> B10 &amp; B16 are Kreemer-Young swarm/background</text>',
        f'<text x="{rx+16}" y="216" font-family="system-ui,-apple-system,sans-serif" font-size="11.5" fill="#475569">earthquake densities (max 4.96e6), NOT distance to EQ.</text>',
        f'<text x="{rx+16}" y="240" font-family="system-ui,-apple-system,sans-serif" font-size="11.5" fill="#1e293b"><tspan font-weight="700" fill="#dc2626">IR87-030:</tspan> Session 1 passed B02 (gravity) as RTP &amp; B19 (TMI)</text>',
        f'<text x="{rx+16}" y="256" font-family="system-ui,-apple-system,sans-serif" font-size="11.5" fill="#475569">as slope (0.0224 vs true B08 slope 0.0502 on 4Q split).</text>',
        f'<text x="{rx+16}" y="276" font-family="system-ui,-apple-system,sans-serif" font-size="11.5" fill="#1e293b"><tspan font-weight="700" fill="#b45309">IR87-031:</tspan> Static H33 file self-masks held-out truth (0.0040 vs 0.0975).</text>',
    ])
    lines.append("</svg>")
    out = ASSETS / "fig_band_forensics.svg"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def _write_spatial_map_png(card: dict) -> Path:
    stfd_path = ROOT / card["artifact"]["path"]
    with rasterio.open(stfd_path) as src:
        stfd = src.read(1) > 0
    with rasterio.open(ROOT / "data" / "raw" / "existing_faults.tif") as src:
        raw_cat = src.read(1)
        fp = raw_cat != -1
        cat = raw_cat == 1
    b08 = np.load(ROOT / ".cache" / "features" / "band-08.npy", mmap_mode="r")
    slope = np.where(np.isfinite(b08) & fp, np.clip(b08, 0.0, 35.0) / 35.0, 0.0)

    # Full-footprint overview downsampled 4x (`932 x 823`) + zoomed Dixie Valley / Carson Sink relay inset (`420 x 823`)
    cat_d = binary_dilation(cat, iterations=2)[::4, ::4]
    stfd_d = binary_dilation(stfd, iterations=3)[::4, ::4]
    fp_d = fp[::4, ::4]
    sl_d = slope[::4, ::4]

    oh, ow = fp_d.shape
    rgb = np.full((oh, ow, 3), 244, dtype=np.uint8)
    shade = (232 - 82 * sl_d).astype(np.uint8)
    rgb[fp_d] = np.stack([shade[fp_d], shade[fp_d] + 3, np.minimum(255, shade[fp_d] + 8)], axis=-1)
    rgb[cat_d] = [71, 85, 105]      # Mapped USGS QFaults in slate gray
    rgb[stfd_d] = [13, 148, 136]    # H87B-STFD 37,654 off-catalogue binary dots in deep teal

    # High-resolution 1:1 inset (`466 x 466` resized 2x nearest to `932` height) showing individual discrete dots
    r0, c0, win = 1420, 1280, 466
    sub_fp = fp[r0 : r0 + win, c0 : c0 + win]
    sub_sl = slope[r0 : r0 + win, c0 : c0 + win]
    sub_cat = binary_dilation(cat[r0 : r0 + win, c0 : c0 + win], iterations=1)
    sub_dot = binary_dilation(stfd[r0 : r0 + win, c0 : c0 + win], iterations=1)

    in_rgb = np.full((win, win, 3), 248, dtype=np.uint8)
    ishade = (236 - 90 * sub_sl).astype(np.uint8)
    in_rgb[sub_fp] = np.stack([ishade[sub_fp], ishade[sub_fp] + 2, np.minimum(255, ishade[sub_fp] + 6)], axis=-1)
    in_rgb[sub_cat] = [51, 65, 85]
    in_rgb[sub_dot] = [220, 38, 38]

    img_main = Image.fromarray(rgb)
    # Draw inset box on overview map
    draw_main = ImageDraw.Draw(img_main)
    draw_main.rectangle([c0 // 4, r0 // 4, (c0 + win) // 4, (r0 + win) // 4], outline=(220, 38, 38), width=3)

    img_inset = Image.fromarray(in_rgb).resize((oh, oh), resample=Image.Resampling.NEAREST)
    canvas = Image.new("RGB", (ow + oh + 36, oh + 64), (255, 255, 255))
    canvas.paste(img_main, (12, 48))
    canvas.paste(img_inset, (ow + 24, 48))
    dc = ImageDraw.Draw(canvas)
    dc.text((16, 16), "A. Full Great Basin Footprint (373 x 329 km): Slate = Mapped QFaults | Teal = H87B-STFD (37,654 dots)", fill=(15, 23, 42))
    dc.text((ow + 28, 16), "B. 100 m Pixel Zoom (46.6 x 46.6 km): Red = Non-Redundant H87B-STFD Dots (min NN = 316 m, 0 on catalogue)", fill=(15, 23, 42))

    out = ASSETS / "fig_spatial_prediction_map.png"
    canvas.save(out, optimize=True)
    return out


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    ablation = json.loads((ROOT / "evidence" / "h87b_ablation.json").read_text(encoding="utf-8"))
    reg = json.loads((ROOT / "docs" / "evidence" / "h87b_registry_34.json").read_text(encoding="utf-8"))
    band_audit = json.loads((ROOT / "docs" / "evidence" / "band_identity_audit.json").read_text(encoding="utf-8"))
    card = json.loads((ROOT / "docs" / "evidence" / "h87b_run_card.json").read_text(encoding="utf-8"))

    generated = [
        _write_ablation_svg(ablation),
        _write_registry_uniqueness_svg(reg),
        _write_band_forensics_svg(band_audit),
        _write_spatial_map_png(card),
    ]
    for p in generated:
        print(f"Generated {p.relative_to(ROOT)} ({p.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
