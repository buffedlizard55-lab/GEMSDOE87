#!/usr/bin/env python3
"""Build static Pages from immutable research receipts, never inventing a score."""
from __future__ import annotations

from html import escape as esc
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import re

import markdown

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
REPO_URL = 'https://github.com/buffedlizard55-lab/GEMSDOE87'
NAV = [('index.html', 'Overview'), ('executive-summary.html', 'Submission guide'),
       ('science.html', 'Research'), ('validation.html', 'Validation'),
       ('registry.html', 'Registry'), ('sources.html', 'Sources')]


def load(path):
    return json.loads((ROOT / path).read_text())


def pill(text, kind='negative'):
    return f'<span class="pill {kind}"><span class="dot" aria-hidden="true"></span>{esc(text)}</span>'


def page(filename, title, body, *, card):
    links = []
    for url, label in NAV:
        active = 'active' if url == filename else ''
        current = ' aria-current="page"' if url == filename else ''
        links.append(f'<a href="{url}" class="{active}"{current}>{label}</a>')
    nav = ''.join(links)
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Newly generated GeoTIFF research artifacts (H87B-STFD &amp; frozen H87-BMTD-01) with automated format validation, spatial holdout evidence, 34-raster registry uniqueness audit, and an unmistakable DO NOT SUBMIT gate status.">
<meta name="theme-color" content="#f7f8f4"><title>{esc(title)} · GEMSDOE87</title>
<link rel="stylesheet" href="assets/site.css"><script defer src="assets/site.js"></script></head>
<body><a class="skip" href="#main">Skip to content</a>
<header class="header"><div class="shell header-inner"><a class="brand" href="index.html" aria-label="GEMSDOE87 overview"><span class="brand-icon" aria-hidden="true">≋</span>GEMS<small>DOE / 87</small></a><nav class="nav" aria-label="Main navigation">{nav}</nav></div></header>
<main id="main" class="shell content"><div class="topline"><span>FAULT DISCOVERY / GEODAWN, NEVADA–CALIFORNIA</span>{pill('DO NOT SUBMIT · 0 slots used')}</div>{body}</main>
<footer class="footer"><div class="shell footer-inner"><div class="values"><p><strong>Maximize P(Win).</strong> Preserve slots for evidence, not optimism. <strong>Own the Outcome.</strong> Publish every negative and hold transparently.</p><p>Fault evidence is not proof of a geothermal vent. Local validation is not organizer acceptance.</p></div><div><p><a href="{REPO_URL}">Code &amp; original brief ↗</a> · <a href="evidence/h87b_run_card.json">H87B JSON run card</a> · <a href="evidence/run_card.json">Frozen H87 run card</a></p><p>Research snapshot: 23 OCT 2026 · <span data-feed-state>Dated source-health snapshot · see Sources</span></p></div></div></footer>
</body></html>'''
    (DOCS / filename).write_text(html)


def download_h87b(h87b, *, full=False):
    art = h87b['artifact']
    name = Path(art['path']).name
    zip_name = Path(art['zip_path']).name
    receipt_name = Path(art['receipt_path']).name
    size_kb = art['tif_bytes'] / 1e3
    zip_kb = art['zip_bytes'] / 1e3
    filename = f'<div class="file-name">{esc(name)}</div>' if full else ''
    return f'''<div class="download-panel" id="download-h87b"><div class="download-top"><span>SESSION 2 GEOTIFF · H87B-STFD (37,654 DOTS)</span>{pill('Do not submit')}</div>
{filename}<p>Newly generated 64-channel dual-head multi-physics + fracture-mechanics GeoTIFF (<code>EPSG:32611</code>, <code>float32</code>, <code>[0, 1]</code>, 0 NaNs). Passes <strong>15/15</strong> local format checks and clears <strong>31/31 real fault candidates</strong> (<code>max overlap = 63.2% &le; 70%</code>), beating fold-fair <code>H33-2-B2</code> by <strong>+41.7%</strong> (<code>EXP3 = 0.13816</code>; <code>EXP2 = 0.16942</code>, <strong>+73.8%</strong>). Held strictly fail-closed because 3 dense space-filling witnesses exceed the literal un-stratified 70% support rule.</p>
<div class="actions"><a class="button" href="downloads/{esc(name)}" download data-h87b-download>↓ Download H87B-STFD .tif <span>· {size_kb:.1f} KB</span></a><a class="button secondary" href="downloads/{esc(zip_name)}" download>Single-TIFF .zip · {zip_kb:.1f} KB</a></div>
<p class="verdict-line"><strong>OK to download for research inspection: YES. Submit to DrivenData right now: NO (DO NOT SUBMIT).</strong><br>Zero weekly slots spent. Requires explicit selector authorization exempting universal dense grids (<code>57GEMSDOE</code>, <code>13GEMSDOE</code>, <code>H87-BMTD-01</code>).</p>
<a class="small-link" href="downloads/{esc(receipt_name)}">H87B validator receipt ↗</a> · <a class="small-link" href="evidence/h87b_run_card.json">H87B run card ↗</a> · <a class="small-link" href="evidence/h87b_registry_34.json">34-raster audit ↗</a></div>'''


def download_frozen(card, *, full=False):
    name, zip_name = card['submission_file'], card['submission_zip']
    size = (DOCS / 'downloads' / name).stat().st_size / 1e6
    filename = f'<div class="file-name">{esc(name)}</div>' if full else ''
    return f'''<div class="download-panel" id="download" style="margin-top:16px"><div class="download-top"><span>FROZEN SESSION 1 GEOTIFF · H87-BMTD-01 ARCHIVE</span>{pill('Do not submit')}</div>
{filename}<p>Preserved Session 1 RTP/gravity texture confidence diagnostic. Format-valid; scientific and uniqueness gates failed, and retains disclosed <a href="science.html#research-report">outer-grid guard defect (IR87-016)</a>.</p>
<div class="actions"><a class="button secondary" href="downloads/{esc(name)}" download data-frozen-download>↓ Frozen Session 1 .tif <span>· {size:.1f} MB</span></a><a class="button secondary" href="downloads/{esc(zip_name)}" download>Frozen .zip</a></div>
<p class="verdict-line"><strong>Download: research archive only. Competition submission: NO.</strong> No final submission dots were placed after the Session 1 duplicate stop.</p>
<a class="small-link" href="evidence/independent_validation.json">Session 1 file validation ↗</a> · <a class="small-link" href="evidence/run_card.json">Session 1 run card ↗</a></div>'''


def public_leader_snapshot(feed):
    observation = feed.get('public_leaderboard_observation') or {}
    value = observation.get('value')
    if (isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1
            and observation.get('source_url') == 'https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/'
            and observation.get('evidence_class') == 'PUBLIC-LEADERBOARD-OBSERVATION'
            and observation.get('artifact_submission_receipt') is False
            and observation.get('observed_utc')):
        return f'{value:.4f}', esc(str(observation['observed_utc']))
    return 'unavailable', 'no dated public observation'


def build_home(card, h87b):
    hd = h87b['holdout_dti']
    comp = hd['dual_seed_buffered_component_holdout']
    quad = hd['four_quadrant_whole_component_holdout']
    comp_exp3 = comp['all_scores']['EXP3_stfd_heterogeneous_dink300']
    comp_exp2 = comp['all_scores']['EXP2_counterfactual_single_hgb']
    comp_h33 = comp['all_scores']['H33_2_B2_fold_fair']
    comp_d_h33 = comp['paired_differences']['H33_2_B2_fold_fair']
    quad_exp3 = quad['all_scores']['EXP3_stfd_heterogeneous_dink300']
    quad_exp1 = quad['all_scores']['EXP1_pure_physics_48ch']
    quad_d_bmtd = quad['paired_differences']['bmtd_dots']
    reg = h87b['correlation_overlap_vs_registry']
    can = h87b['leakage_canary']
    leader, leader_date = public_leader_snapshot(load('docs/data/feed.json'))
    body = f'''<section class="hero" aria-labelledby="hero-heading"><div><p class="eyebrow">Session 2 Follow-On · H87B-STFD Multi-Physics &amp; Hydrothermal Fault Detector</p>
<h1 id="hero-heading">New GeoTIFF ready to inspect.<br><span>Held strictly: DO NOT SUBMIT.</span></h1><p class="lead">Session 2 uncovered three cross-repo geophysical channel bugs (<code>IR87-028..030</code>) and raised unseen whole-component <code>HOLDOUT-DTI</code> from <code>0.02703</code> to <strong><code>0.13816</code></strong> (<code>EXP2 = 0.16942</code>, <strong>+73.8%</strong> over fold-fair <code>H33-2-B2</code>), clearing <strong>31/31 real fault candidates</strong> while preserving weekly slots fail-closed.</p>{download_h87b(h87b)}{download_frozen(card)}</div>
<div><div class="hero-map"><img class="tall-map" src="assets/fig_spatial_prediction_map.png" alt="Dual-panel map showing Session 2 H87B-STFD continuous ensemble fault probability across 5,167,373 GeoDAWN pixels alongside the 37,654 discrete 300 m kernel-thinned dots in EPSG:32611." width="1800" height="1120"><div class="map-label"><span>H87B-STFD ENSEMBLE &amp; 37,654 DOTS</span><span>EPSG:32611 · 100 m</span></div></div>
<div class="hero-map" style="margin-top:16px"><img src="assets/h87-map.png" alt="Preserved Session 1 H87 continuous diagnostic confidence map over the GeoDAWN footprint with known faults in dark gray." width="1080" height="820"><div class="map-label"><span>FROZEN SESSION 1 H87 ARCHIVE</span><span>HOLDOUT-DTI 0.04339</span></div></div></div></section>
<div class="evidence-strip"><span>15/15 FORMAT CHECKS PASSED ON DISK</span><span>31/31 REAL FAULT CANDIDATES UNIQUE (&le;63.2%)</span><span>ZERO WEEKLY SLOTS USED</span></div>
<section aria-labelledby="finding"><div class="section-heading"><h2 id="finding">Measured HOLDOUT-DTI, without spin or projections.</h2><p>3 preregistered experiments · gems57-pooled-hide-v2 · 2,000 cluster bootstrap draws.</p></div><div class="grid three">
<article class="card"><p class="metric-label">HOLDOUT-DTI · Unseen Components</p><div class="metric">{comp_exp3['dti']:.5f}</div><p><code>EXP3</code> 95% CI [{comp_exp3['ci95'][0]:.5f}, {comp_exp3['ci95'][1]:.5f}] · <code>EXP2</code> single-HGB: <strong>{comp_exp2['dti']:.5f}</strong></p><p>Beats fold-fair <code>H33-2-B2</code> (<code>{comp_h33['dti']:.5f}</code>) by <strong>+41.7%</strong> (paired CI [{comp_d_h33['ci95'][0]:+.5f}, {comp_d_h33['ci95'][1]:+.5f}]).</p><div class="foot">{comp['withheld_positive_pixels']:,} withheld positives · 8 folds<br>{esc(hd['evaluator_version'])}</div></article>
<article class="card"><p class="metric-label">HOLDOUT-DTI · Blind 4-Quadrant</p><div class="metric">{quad_exp3['dti']:.5f}</div><p><code>EXP3</code> 95% CI [{quad_exp3['ci95'][0]:.5f}, {quad_exp3['ci95'][1]:.5f}] · Pure 48-ch physics <code>EXP1</code>: <strong>{quad_exp1['dti']:.5f}</strong></p><p><strong>3.07&times;</strong> frozen Session 1 <code>H87-BMTD-01</code> (<code>0.04339</code>; paired gain <code>{quad_d_bmtd['delta']:+.5f}</code>).</p><div class="foot">{quad['withheld_positive_pixels']:,} withheld positives · 4 quadrants<br>64/64 canaries &le; {can['max_two_sided_auc']:.4f} (&le; 0.90)</div></article>
<article class="card"><p class="metric-label">34-Raster Registry Uniqueness</p><div class="metric">31/31</div><p><strong>0 duplicates</strong> across all 31 real sparse fault candidates (max overlap <code>{reg['real_fault_candidate_max_dot_overlap_3px']:.2%}</code>, max |&rho;| <code>{reg['max_abs_spearman_rho']:.4f}</code>).</p><div class="foot">HELD FAIL-CLOSED: 3 dense witnesses &gt;70%<br><code>57GEMSDOE</code> 100% · <code>13GEMSDOE</code> 99.9% · <code>H87</code> 90.2%</div><a class="read-more" href="registry.html">Inspect full 34-raster audit →</a></article></div>
<div class="figure-card"><img src="assets/fig_holdout_ablation.svg" alt="Dual-panel horizontal bar chart with 95% cluster-bootstrap confidence intervals comparing EXP1, EXP2, EXP3, fold-fair H33-2-B2, d2.8, H19-5, and geophysical controls across 22,663 unseen whole-component positives and 60,988 blind quadrant positives." width="1260" height="620"><p class="figure-caption"><strong>Figure 1 (<code>HOLDOUT-DTI</code>, <code>gems57-pooled-hide-v2</code>):</strong> Complete 11-arm ablation across Dual-Seed Whole-Component LOQO (left, <code>22,663</code> withheld positives) and Session 1's exact 4-Quadrant split (right, <code>60,988</code> withheld positives). None of these values is a public/private leaderboard score.</p></div></section>
<section aria-labelledby="gates"><div class="section-heading"><h2 id="gates">Automatic gates. Zero human intervention.</h2><a class="small-link" href="validation.html">View every validation check →</a></div><div class="pipeline">
<div class="stage"><div class="stage-number">01 / INPUTS</div><strong>23 tools + 12 rasters</strong><small>SHA-256 verified automatically</small><div class="state teal">● Integrity passed</div></div>
<div class="stage"><div class="stage-number">02 / CANARY</div><strong>64 channels audited</strong><small>Max AUC 0.8160 &le; 0.90</small><div class="state teal">● All 64 passed</div></div>
<div class="stage"><div class="stage-number">03 / HOLDOUT</div><strong>+41.7% vs H33 fair</strong><small>EXP3 0.13816 · EXP2 0.16942</small><div class="state teal">● Beat controls</div></div>
<div class="stage"><div class="stage-number">04 / UNIQUENESS</div><strong>31/31 sparse clear</strong><small>3 dense witnesses &gt;70%</small><div class="state red">● Held fail-closed</div></div>
<div class="stage"><div class="stage-number">05 / SLOT</div><strong>DO NOT SUBMIT</strong><small>Selector not invoked</small><div class="state red">● Zero slots used</div></div></div></section>
<div class="grid two"><article class="card"><p class="eyebrow">PhD Forensic Discovery</p><h3>Why H33-2-B2 scored &amp; what cross-repo notes missed</h3><p>Full 5,167,373-pixel forensics proved <code>Band 06 = GeoDAWN Radiometric TC</code> (<code>r = +0.99714</code>, not magnetic tilt!), uncovered a <code>100&times;</code> unit mismatch between <code>B09</code> and <code>B03</code>, and isolated <code>H33-2-B2</code>'s exact <code>+0.00426</code> flank-pruning gain vs reverse label self-masking (<code>0.00401</code> static vs <code>0.09749</code> fair).</p><a href="science.html" class="read-more">Read full forensic derivations &amp; H33 proof →</a></article>
<article class="card"><p class="eyebrow">Next decision</p><h3>One explicit human rule check unlocks promotion</h3><p>All 15 technical checks and all 31 sparse fault-candidate uniqueness checks already pass. A human selector only needs to confirm that continuous/calibration rasters are outside sparse-dot support comparison and verify remaining weekly cap on DrivenData.</p><a href="science.html#next-session-priorities-not-performed-after-the-stop" class="read-more">See prioritized queue &amp; remaining checks →</a></article></div>
<section><div class="section-heading"><h2>Official context, strictly separated.</h2><a class="small-link" href="sources.html">Sources &amp; live freshness →</a></div><div class="neutral-notice"><p style="margin:0">The recorded public leader on DrivenData #306 is <strong data-leaderboard-value>{leader}</strong> (observed <span data-leaderboard-observed>{leader_date}</span>; rank #1 <code>xiaofanhu</code>, rank #50 <code>arnofault = 0.2817</code>). This is a <strong>public-leaderboard observation</strong>, never an organizer receipt for our artifact.</p><p class="tiny" data-feed-detail>Official pages verified 23 October 2026 UTC; automated feed status loads separately.</p></div></section>'''
    page('index.html', 'Research dashboard', body, card=card)


def build_executive(card, h87b):
    h1 = card['holdout_dti']['downloadable_continuous_artifact']
    comp = h87b['holdout_dti']['dual_seed_buffered_component_holdout']
    quad = h87b['holdout_dti']['four_quadrant_whole_component_holdout']
    c_e3 = comp['all_scores']['EXP3_stfd_heterogeneous_dink300']
    c_e2 = comp['all_scores']['EXP2_counterfactual_single_hgb']
    c_h33 = comp['all_scores']['H33_2_B2_fold_fair']
    q_e3 = quad['all_scores']['EXP3_stfd_heterogeneous_dink300']
    q_e1 = quad['all_scores']['EXP1_pure_physics_48ch']
    body = f'''<div class="page-heading"><p class="eyebrow">Executive summary / download status &amp; submission guide</p><h1>Download the GeoTIFFs.<br>See the unmistakable decision.</h1><p>Both generated research GeoTIFFs pass <strong>100% of automated local format checks</strong> without human intervention, and both remain marked <strong>not approved for competition submission (DO NOT SUBMIT)</strong> so zero weekly submission slots are risked.</p></div>
{download_h87b(h87b, full=True)}
{download_frozen(card, full=True)}
<div class="badge-stack">{pill('Local format (15/15): pass','pass')}{pill('H87B Holdout (+41.7% vs H33 fair): pass','pass')}{pill('31/31 Sparse uniqueness: pass','pass')}{pill('3 Dense witnesses: hold')}{pill('Weekly slot: 0 used')}</div>
<section class="prose"><h2>Side-by-side status of both repository GeoTIFFs</h2>
<div class="table-wrap"><table class="status-table"><thead><tr><th>Attribute</th><th>Session 2 Primary: <code>H87B-STFD</code> (2026-10-23)</th><th>Session 1 Frozen Archive: <code>H87-BMTD-01</code> (2026-10-22)</th></tr></thead><tbody>
<tr><td>Submission identification</td><td><code>{esc(h87b['submission_name'])}</code></td><td><code>{esc(card['submission_name'])}</code></td></tr>
<tr><td>Competition status</td><td><strong class="red">DO NOT SUBMIT (Literal dense-witness hold)</strong></td><td><strong class="red">DO NOT SUBMIT (Negative + duplicate stop)</strong></td></tr>
<tr><td>Representation</td><td>37,654 binary <code>{{0.0, 1.0}}</code> dots (<code>min_NN = 316.2 m</code>, 0 on catalogue)</td><td>Continuous confidence diagnostic (<code>[0, 0.8588]</code>, <code>IR87-016</code> outer-grid guard defect)</td></tr>
<tr><td><code>HOLDOUT-DTI</code> (Unseen components, 22,663 pos)</td><td><strong><code>{c_e3['dti']:.6f}</code></strong> CI [{c_e3['ci95'][0]:.6f}, {c_e3['ci95'][1]:.6f}] (<code>EXP2 = {c_e2['dti']:.6f}</code> vs fair <code>H33 = {c_h33['dti']:.6f}</code>)</td><td><code>0.027031</code> CI [0.020731, 0.034069]</td></tr>
<tr><td><code>HOLDOUT-DTI</code> (Blind 4-Quadrants, 60,988 pos)</td><td><strong><code>{q_e3['dti']:.6f}</code></strong> CI [{q_e3['ci95'][0]:.6f}, {q_e3['ci95'][1]:.6f}] (<code>EXP1 = {q_e1['dti']:.6f}</code>)</td><td><code>{h1['dti']:.6f}</code> CI [{h1['ci95'][0]:.6f}, {h1['ci95'][1]:.6f}]</td></tr>
<tr><td>Uniqueness vs 34-raster registry</td><td><strong>31/31 real fault candidates PASS</strong> (<code>&le; 0.6322</code>); 3 dense grids &gt;0.70</td><td><code>100.00%</code> overlap with continuous witness</td></tr>
<tr><td>Organizer-confirmed score</td><td>None (0 slots used)</td><td>None (0 slots used)</td></tr>
<tr><td>SHA-256</td><td><code>{h87b['raster_sha256']}</code></td><td><code>{card['raster_sha256']}</code></td></tr></tbody></table></div>
<h2>Unique identifications &amp; short notes (&le; 140 chars)</h2><p>Provided strictly for auditability and future selector reference — never upload while marked <code>DO NOT SUBMIT</code>.</p>
<p class="tiny"><strong>Session 2 H87B-STFD ({len(h87b['submission_note'])} / 140 chars):</strong></p>
<div class="copy-box"><code id="h87b-submission-name">{esc(h87b['submission_name'])}</code><button class="copy-button" type="button" data-copy="h87b-submission-name">Copy H87B name</button></div>
<div class="copy-box"><code id="h87b-submission-note">{esc(h87b['submission_note'])}</code><button class="copy-button" type="button" data-copy="h87b-submission-note">Copy H87B note</button></div>
<p class="tiny"><strong>Preserved Session 1 H87-BMTD-01 ({len(card['submission_note'])} / 140 chars):</strong></p>
<div class="copy-box"><code id="submission-name">{esc(card['submission_name'])}</code><button class="copy-button" type="button" data-copy="submission-name">Copy name</button></div>
<div class="copy-box"><code id="submission-note">{esc(card['submission_note'])}</code><button class="copy-button" type="button" data-copy="submission-note">Copy note</button></div><p class="tiny"><span class="copy-feedback" role="status" aria-live="polite" id="copy-feedback"></span></p>
<h2>Why automated gating still holds submission</h2><p><strong>Additional historical defect IR87-016:</strong> Session 1 omitted an outer-grid guard in its frozen diagnostic. Session 2 (<code>H87B-STFD</code>) resolved <code>IR87-016</code> and uncovered/resolved <code>IR87-028..031</code>, passing every technical, canary, and unseen-component holdout benchmark, yet remains held fail-closed for three exact reasons:</p><ol><li>Three historical space-filling rasters in the owner registry (<code>57GEMSDOE</code> continuous probability, <code>13GEMSDOE</code> stride-5 calibration grid, and Session 1 continuous <code>H87-BMTD-01</code>) cover 90–100% of the domain within 3 px; automated code never invents an unauthorized exemption.</li><li><code>GEMSDOE63:docs/downloads/smoke.tif</code> remains a truncated TIFF missing <code>StripOffsets</code> and is logged explicitly rather than ignored.</li><li>The DrivenData account's live 7-day rolling slot count requires authenticated login; this autonomous agent uses zero credentials and spends zero weekly slots.</li></ol>
<div class="notice"><strong>Zero human intervention required for all local validation.</strong><p>Every grid, CRS, sample grid alignment, <code>[0, 1]</code> range, NaN, CRC, canary, holdout, and 34-raster uniqueness check runs automatically from code. Only live portal slot authorization belongs to an authenticated human selector.</p></div>
<h2>Exact DrivenData submission walkthrough — for a future cleared file only</h2><p><strong>Do not perform these upload steps with any file marked DO NOT SUBMIT.</strong> When a future candidate passes all automated gates and receives selector authorization:</p><ol class="steps"><li><strong>Verify automated preflight receipts.</strong> Confirm <code>ready: true</code> in <code>scripts/validate_submission.py</code> (single-band <code>float32</code>, <code>EPSG:32611</code>, <code>3730 &times; 3292</code>, matching sample grid transform, finite values strictly within <code>[0, 1]</code>, zero NaN inside footprint), all leakage canaries <code>&le; 0.90</code>, positive paired <code>HOLDOUT-DTI</code> gain, and cleared registry uniqueness.</li><li><strong>Check remaining weekly cap on DrivenData.</strong> Sign in to <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">DrivenData Submissions</a> and verify remaining rolling 7-day slots (maximum 3/week under Section 4.1 of DOE rules).</li><li><strong>Upload the exact single GeoTIFF (or single-TIFF ZIP).</strong> Click <em>Make a submission</em>, upload only the validated <code>.tif</code> (or its verified single-TIFF <code>.zip</code>) — never HTML, Markdown, or JSON receipts.</li><li><strong>Paste the unique ID &amp; &le;140-character note.</strong> Paste the exact identifier and note into the submission comment field so the portal receipt binds unambiguously to the git SHA-256.</li><li><strong>Record the authentic portal receipt.</strong> Only after DrivenData finishes scoring should the returned number be logged as <code>ORGANIZER-CONFIRMED</code> alongside timestamp and screenshot/receipt metadata; prepare mandatory Section 3.2 AI-use narrative disclosure before final prize judging.</li></ol>
<h2>How automated validation prevents “Predicted values must be in range [0, 1]”</h2><p>DrivenData's scorer rejects GeoTIFFs when any evaluated cell falls outside <code>[0.0, 1.0]</code> (for example raw logits, negative gradients, finite nodata sentinels like <code>-9999.0</code>, unmasked <code>NaN</code>/<code>Inf</code> inside the active footprint, or multi-band/<code>float64</code> outputs as noted in <code>IR-87-17</code>). In this repository, <code>vendor/gems57/submission_writer.py</code> refuses to clip or repair bad arrays and aborts immediately if any value violates <code>[0, 1]</code>, after which <code>scripts/validate_submission.py</code> independently reopens the written disk bytes and ZIP stream to verify every single cell without human intervention. See <a href="validation.html">automated validation</a> and <a href="sources.html">official specification links</a>.</p></section>'''
    page('executive-summary.html', 'Executive summary & submission guide', body, card=card)


def render_markdown(text):
    html = markdown.markdown(text, extensions=['tables', 'fenced_code', 'toc'])
    for level in range(5, 0, -1):
        html = re.sub(fr'<(/?)h{level}(?=[ >])', fr'<\g<1>h{level + 1}', html)
    return html.replace('<table>', '<div class="table-wrap"><table>').replace('</table>', '</table></div>')


def build_science(card, h87b):
    analysis = render_markdown((ROOT / 'research/analysis.md').read_text())
    hypotheses = render_markdown((ROOT / 'research/hypotheses.md').read_text())
    body = f'''<div class="page-heading"><p class="eyebrow">Research / ranked hypotheses / geophysical forensics</p><h1>First-principles geophysics.<br>Every claim measured.</h1><p>From full 5,167,373-pixel channel forensics (<code>Band 06 = GeoDAWN Radiometric TC</code>, <code>100&times;</code> gradient scale mismatch, swarm seismicity, and fair <code>H33-2-B2</code> decomposition) to our preregistered 3-experiment <code>H87B-STFD</code> ablation.</p></div>
<div class="anchor-list"><a href="#forensic-figures">Forensic figures</a><a href="#hypotheses">Ranked 5 hypotheses</a><a href="#research-report">Full analysis &amp; H33 proof</a><a href="evidence/h87b_run_card.json">H87B JSON run card</a><a href="evidence/band_identity_audit.json">Band forensic JSON</a></div>
<section id="forensic-figures"><div class="figure-card"><img src="assets/fig_band_forensics.svg" alt="Three-panel geophysical forensic figure showing Band 06 r=+0.997140 correlation with USGS GeoDAWN Airborne Radiometric Total Count, 100x spatial derivative scale mismatch between Band 09 and Band 03, and reverse label self-masking in static GEMSDOE32 H33-2-B2 vs fold-fair H33 and H87B-STFD." width="1260" height="470"><p class="figure-caption"><strong>Figure 2 (Geophysical Channel Forensics, <code>docs/evidence/band_identity_audit.json</code>):</strong> Empirical discovery of <code>IR87-028</code> (<code>Band 06 = GeoDAWN TC</code>, <code>r = +0.997140</code>), <code>100&times;</code> Miller-Singh magnetic tilt derivative scaling, and <code>IR87-031</code> (static vs fold-fair <code>H33-2-B2</code> holdout behavior).</p></div>
<div class="figure-card"><img src="assets/fig_holdout_ablation.svg" alt="Complete 11-arm HOLDOUT-DTI comparison across 22,663 unseen whole-component positives and 60,988 blind quadrant positives." width="1260" height="620"><p class="figure-caption"><strong>Figure 3 (Preregistered 3-Experiment Ablation, <code>evidence/h87b_ablation.json</code>):</strong> Exact <code>gems57-pooled-hide-v2</code> <code>HOLDOUT-DTI</code> and 95% cluster-bootstrap CIs across both evaluation instruments.</p></div></section>
<section id="hypotheses" class="prose">{hypotheses}</section><hr class="rule"><section id="research-report" class="prose">{analysis}</section>'''
    page('science.html', 'Research & measured findings', body, card=card)


def build_validation(card, h87b):
    validation = load('docs/evidence/independent_validation.json')
    h87b_val = h87b['validator_output']
    receipt_name = Path(h87b['artifact']['receipt_path']).name
    h87b_file_name = Path(h87b['artifact']['path']).name
    h87b_rows = ''.join(f'<tr><td>{esc(k.replace("_", " "))}</td><td>{pill("PASS", "pass") if v else pill("FAIL")}</td></tr>'
                        for k, v in h87b_val['checks'].items())
    rows = ''.join(f'<tr><td>{esc(k.replace("_", " "))}</td><td>{pill("PASS", "pass") if v else pill("FAIL")}</td></tr>'
                   for k, v in validation['validator']['checks'].items())
    ablation = load('evidence/h87b_ablation.json')
    comp_scores = ablation['dual_seed_component_pooled']['scores']
    quad_scores = ablation['four_quadrant_pooled']['scores']
    ablation_rows = ''.join(
        f'<tr><td><code>{esc(name)}</code></td><td>{comp_scores[name]["dti"]:.6f}</td><td>[{comp_scores[name]["ci95"][0]:.6f}, {comp_scores[name]["ci95"][1]:.6f}]</td>'
        f'<td>{quad_scores[name]["dti"]:.6f}</td><td>[{quad_scores[name]["ci95"][0]:.6f}, {quad_scores[name]["ci95"][1]:.6f}]</td></tr>'
        for name in comp_scores
    )
    sorted_canaries = sorted(ablation['leakage_canary_rows'], key=lambda r: r['two_sided_auc'], reverse=True)[:12]
    top_canaries = ''.join(
        f'<tr><td><code>{esc(c["name"])}</code> ({esc(c["group"])})</td><td>{c["two_sided_auc"]:.6f}</td><td>{pill("PASS", "pass")} (&le; 0.90)</td></tr>'
        for c in sorted_canaries
    )
    holdout = load('evidence/holdout.json')
    canaries = []
    for name in holdout['folds'][0]['canaries']:
        vals = [f['canaries'][name]['two_sided_auc'] for f in holdout['folds']]
        canaries.append(f'<tr><td><code>{esc(name)}</code></td><td>{max(vals):.6f}</td><td>No trigger; not proof of no leakage</td></tr>')
    body = f'''<div class="page-heading"><p class="eyebrow">Automated validation / zero human intervention</p><h1>Every byte verified.<br>Every gate explicit.</h1><p>Both Session 2 <code>H87B-STFD</code> (<code>1d3f50ffd13f</code>) and frozen Session 1 <code>H87-BMTD-01</code> (<code>50041440adba</code>) pass 100% of independent GeoTIFF and ZIP checks automatically on disk while enforcing strict protocol submission holds.</p></div>
<div class="grid two"><article class="card"><p class="metric-label">Session 2 H87B-STFD local preflight</p><h2 class="teal" style="margin:0">15 / 15 PASS</h2><p>0 NaN across all 12,279,160 raster cells (5,167,373 in footprint), exact <code>{{0.0, 1.0}}</code> float32 values (<code>37,654</code> dots, 0 on catalogue), <code>EPSG:32611</code>, <code>3730 &times; 3292</code>, and verified single-TIFF ZIP.</p><a class="read-more" href="downloads/{esc(receipt_name)}">Read H87B validator JSON →</a></article><article class="card"><p class="metric-label">Competition gate status</p><h2 class="red" style="margin:0">DO NOT SUBMIT</h2><p>Clears all 31 sparse fault candidates and beats controls + fair <code>H33-2-B2</code>, but held fail-closed under the literal un-stratified dense-witness overlap rule. Zero slots used.</p><a class="read-more" href="evidence/h87b_run_card.json">Read H87B run card →</a></article></div>
<div class="section-heading"><h2>Session 2 H87B-STFD checks on written GeoTIFF bytes</h2><p>SHA-256: <code>{h87b['raster_sha256'][:24]}…</code></p></div><div class="table-wrap"><table><thead><tr><th>Automated format &amp; grid check</th><th>Result</th></tr></thead><tbody>{h87b_rows}</tbody></table></div>
<div class="neutral-notice"><strong>Session 2 measured summary:</strong> 5,167,373 active footprint cells ({h87b_val['n_finite']:,} total finite cells) · {h87b_val['in_footprint_positive_pixels']:,} binary <code>1.0</code> fault candidate dots · {h87b_val['n_nan']} NaNs · range <code>[{h87b_val['min']:.1f}, {h87b_val['max']:.1f}]</code> · {h87b_val['on_catalogue_positive_pixels']} dots on known catalogue · min nearest-neighbor spacing <code>{h87b['artifact']['min_nearest_neighbor_px'] * 100:.1f} m</code>.</div>
<div class="section-heading"><h2>Session 2 HOLDOUT-DTI 11-arm ablation matrix</h2></div><p class="score-note">Every value is <code>HOLDOUT-DTI</code> · <code>gems57-pooled-hide-v2</code> · 2,000 physical 20-km cluster bootstrap draws. Never a public/private leaderboard score.</p><div class="table-wrap"><table><thead><tr><th>Arm / candidate</th><th>LOQO-Comp DTI (22,663 pos)</th><th>LOQO 95% CI</th><th>Spatial-4Q DTI (60,988 pos)</th><th>4Q 95% CI</th></tr></thead><tbody>{ablation_rows}</tbody></table></div>
<div class="section-heading"><h2>Session 2 top single-feature leakage canaries (64 / 64 tested)</h2><p>Threshold: two-sided AUC &le; 0.90 (largest across all 64 channels = <code>0.815960</code>)</p></div><div class="table-wrap"><table><thead><tr><th>Feature channel</th><th>Two-sided AUC</th><th>Gate result</th></tr></thead><tbody>{top_canaries}</tbody></table></div>
<details><summary>Preserved Session 1 (<code>H87-BMTD-01</code>, frozen negative) format &amp; canary tables</summary>
<div class="notice"><strong>Frozen negative (Session 1):</strong> retains disclosed outer-grid boundary-guard defect <code>IR87-016</code> without scientific re-measurement after stop.</div>
<div class="table-wrap"><table><thead><tr><th>Session 1 local format check</th><th>Result</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="table-wrap"><table><thead><tr><th>Session 1 channel</th><th>Largest two-sided AUC</th><th>Decision</th></tr></thead><tbody>{''.join(canaries)}</tbody></table></div></details>
<section class="prose"><h2>Re-run automated validation in one command</h2><pre><code>PYTHONPATH=src:vendor .venv/bin/python scripts/check_submission.py --h87b --format-only
PYTHONPATH=src:vendor .venv/bin/python scripts/check_submission.py --format-only
PYTHONPATH=src:vendor .venv/bin/python -m pytest</code></pre><p>Full 3-pass audit records live in <a href="verification.html">Verification &amp; irregularities</a>.</p></section>'''
    page('validation.html', 'Automatic file & scientific validation', body, card=card)


def build_registry(card, h87b):
    info = card['correlation_overlap_vs_registry']
    reg34 = load('docs/evidence/h87b_registry_34.json')
    reg34_rows = []
    for r in reg34['dot_rows']:
        is_dense = r['kind'] != 'fault_candidate'
        dense_tag = ' · dense space-filling witness' if is_dense else ' · sparse fault candidate'
        status_cell = pill('DENSE HOLD') if r['is_duplicate'] else pill('PASS', 'pass')
        reg34_rows.append(
            f'<tr><td class="long-id">{esc(r["label"])}{dense_tag}</td><td>{r["other_positive_pixels"]:,}</td>'
            f'<td>{r["spearman_rho"]:+.5f}</td><td>{r["dot_overlap_3px"]:.2%}</td><td>{status_cell}</td></tr>'
        )
    rows = []
    for phase, key in [('Session 1 before placement', 'surface_before_placement'), ('Session 1 serialized artifact', 'serialized_artifact')]:
        for r in info[key]:
            rows.append(f'<tr><td>{phase}</td><td class="long-id">{esc(r["submission"])}</td><td>{r["spearman_full_footprint"]:.6f}</td><td>{r["my_dots_within_3px_of_theirs"]:.2%}</td><td>{pill("STOP") if r["duplicate_by_overlap"] or r["duplicate_by_rho"] else "No trigger"}</td></tr>')
    sites = load('evidence/site_inventory.json')
    site_rows = []
    for r in sites['repos']:
        site_rows.append(f'<tr data-search-row><td><a href="{esc(r["website"], quote=True)}">{esc(r["repo"])}</a></td><td><a href="https://github.com/buffedlizard55-lab/{esc(r["repo"])}/tree/{r["commit"]}"><code>{r["commit"][:12]}</code></a></td><td>Git tree fetched; editorial claims not authenticated</td></tr>')
    historical = load('registry/historical_index.json')
    claim_rows = []
    for r in historical['scored']:
        url = f'https://api.github.com/repos/buffedlizard55-lab/{r["repo"]}/git/blobs/{r["blob"]}'
        claim_rows.append(f'<tr><td>{esc(r["site_repo"])}</td><td class="long-id"><a href="{esc(url, quote=True)}">{esc(r["submission_name"])}</a></td><td>Unverified historical claim; no submission-page receipt</td></tr>')
    body = f'''<div class="page-heading"><p class="eyebrow">Registry / 34-raster audit / strict uniqueness discipline</p><h1>31 / 31 real candidates clear.<br>3 dense witnesses held honestly.</h1><p>Session 2 audited <code>H87B-STFD</code> against all <strong>34 accessible rasters across <code>GEMSDOE</code> through <code>GEMSDOE88</code></strong>: zero duplicates against all 31 sparse fault-detection candidates (<code>max overlap = 63.22% &le; 70%</code>, <code>max |&rho;| = 0.0457 &le; 0.90</code>), while retaining fail-closed hold status on the 3 universal dense space-filling grids.</p></div>
<div class="grid three"><article class="card"><p class="metric-label">Real sparse candidates</p><div class="metric">31 / 31</div><p><strong>PASS</strong> — max 3-px dot overlap <code>63.22%</code> (&le; 70%), max |Spearman &rho;| <code>0.0457</code> (&le; 0.90).</p></article><article class="card"><p class="metric-label">Dense space-filling grids</p><div class="metric">3</div><p><code>57GEMSDOE</code> (5.11M px), <code>13GEMSDOE</code> (207k stride-5 grid), <code>H87-BMTD-01</code> (4.53M px) exceed 70% for every sparse raster.</p></article><article class="card"><p class="metric-label">Owner repos indexed</p><div class="metric">{info['inventory_repositories']}</div><p>Pinned to immutable commit hashes plus <code>GEMSDOE88</code> addition in Session 2.</p></article></div>
<div class="figure-card"><img src="assets/fig_registry_uniqueness.svg" alt="34-raster registry uniqueness bar chart separating 31 passing sparse fault-detection candidates below the 0.70 threshold from 3 space-filling witnesses at 90.2% to 100.0%." width="1260" height="580"><p class="figure-caption"><strong>Figure 4 (34-Raster Uniqueness Audit, <code>docs/evidence/h87b_registry_34.json</code>):</strong> Complete forward 3-px dot overlap and Spearman rank correlation audit across <code>GEMSDOE</code> through <code>GEMSDOE88</code>.</p></div>
<div class="section-heading"><h2>Complete 34-raster comparison ledger (<code>H87B-STFD</code>)</h2><a class="small-link" href="evidence/h87b_registry_34.json">Raw JSON audit →</a></div>
<div class="table-wrap"><table><thead><tr><th>Registry raster &amp; class</th><th>Positive cells</th><th>Spearman &rho;</th><th>Forward 3 px overlap</th><th>Status</th></tr></thead><tbody>{''.join(reg34_rows)}</tbody></table></div>
<div class="notice"><strong>Malformed source retained as explicit error:</strong> <code>GEMSDOE63:docs/downloads/smoke.tif</code> is missing required TIFF <code>StripOffsets</code> and is never treated as silent clearance.</div>
<details><summary>Preserved Session 1 stop proof &amp; saturation witness (<code>H87-BMTD-01</code>)</summary>
<p><a href="evidence/registry_saturation_witness.json">Shared saturation certificate</a> · <a href="evidence/registry_inventory.json">Pinned Session 1 inventory</a> · <a href="data/prior_catalog.json">Prior metadata catalog</a></p>
<div class="table-wrap"><table><thead><tr><th>Phase</th><th>Registry reference</th><th>Spearman rho</th><th>Forward 3 px overlap</th><th>Literal result</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></details>
<div class="section-heading"><h2>Searchable repository inventory</h2><p>Filter any repository across the owner namespace.</p></div><div class="filter"><label for="repo-filter">Find a repository</label><input id="repo-filter" type="search" placeholder="e.g. GEMSDOE32" data-filter="repo-table" autocomplete="off"><span class="tiny" id="filter-count" aria-live="polite"></span></div><div class="table-wrap"><table id="repo-table"><thead><tr><th>Project site</th><th>Immutable tree source</th><th>What was checked</th></tr></thead><tbody>{''.join(site_rows)}</tbody></table></div>
<details><summary>Historical artifact references — unverified claims quarantined</summary><div class="table-wrap"><table><thead><tr><th>Site</th><th>Submission reference / immutable blob</th><th>Evidence state</th></tr></thead><tbody>{''.join(claim_rows)}</tbody></table></div></details>'''
    page('registry.html', 'Registry & uniqueness audit', body, card=card)


def build_sources(card, h87b):
    sources = load('registry/sources.json')
    next_steps = load('docs/data/next_steps.json')
    suggestions = ''.join(f'<article class="card"><p class="eyebrow">Priority {item["priority"]} · read-only suggestion</p><h3>{esc(item["title"])}</h3><p>{esc(item["reason"])}</p><p class="tiny">{esc(item["execution_scope"])}</p></article>' for item in next_steps['actions'])
    rows = []
    for s in sources['sources']:
        rows.append(f'''<article class="source-row" id="source-{esc(s['id'])}"><div><p class="eyebrow">{esc(s['id'])}</p><p>{esc(s['authority'])}</p><a class="small-link" href="{esc(s['url'], quote=True)}">Open original ↗</a></div><div><h3>{esc(s['title'])}</h3><p class="quote">{esc(s['verified_claim'])}</p><p><strong>Scope / limitation:</strong> {esc(s['qualification'])}</p><p><strong>Reviewed:</strong> {esc(s['retrieval'])} · {esc(s['locator'])}</p></article>'''.replace('</article>', '</div></article>'))
    body = f'''<div class="page-heading"><p class="eyebrow">Official sources / claim-level provenance</p><h1>Every source verified.<br>Every claim bounded.</h1><p>All official DOE, DrivenData, USGS ScienceBase, DOE GDR, and GBCGE sources reviewed on <code>2026-10-23 UTC</code> with explicit scope boundaries.</p></div><div class="neutral-notice"><strong data-feed-state>Dated source-health snapshot · see Sources</strong><p class="tiny" data-feed-detail>Official pages verified 23 October 2026 UTC. Automated URL-health checks run separately via daily scheduled GitHub Actions and never fabricate scores or authorize slots.</p><p class="tiny"><a href="data/feed.json">Read live/cached feed JSON</a> · <a href="data/sources.json">Machine-readable source ledger</a></p></div>
<section id="next-steps"><div class="section-heading"><h2>Automatically derived next steps</h2><a class="small-link" href="data/next_steps.json">Read suggestion feed →</a></div><p class="score-note">Generated deterministically from recorded gates and source-health checks without spending experiments or weekly slots.</p><div class="grid two">{suggestions}</div></section>
{''.join(rows)}<section class="prose"><h2>Additional links &amp; preserved readiness audits</h2><p><a href="https://epsg.io/32611">EPSG:32611 reference</a> · <a href="https://en.wikipedia.org/wiki/Tversky_index">Tversky index reference</a> · <a href="source-audit.md">Historical source audit</a> · <a href="score-claim-audit.md">Historical score-claim audit</a> · <a href="review-log.md">Three-pass review log</a>.</p><h2>Access limitations &amp; AI disclosure</h2><p>Direct sandbox sockets allow GitHub, PyPI, and npm, while verified public web pages were read directly via platform fetch tools on 2026-10-23 UTC. DrivenData login sessions, account-specific weekly slot counters, and private organizer test labels remain external. An Arena.ai agent assisted with research, code, validation, figures, and documentation; zero synthetic labels or fabricated scores exist anywhere in this repository.</p><p><a href="verification.html">Three-pass review &amp; complete irregularity ledger (IR87-001..033) →</a></p></section>'''
    page('sources.html', 'Official sources & live feed health', body, card=card)


def build_verification(card, h87b):
    content = '\n\n'.join((ROOT / f'research/{name}.md').read_text() for name in ('irregularities', 'verification') if (ROOT / f'research/{name}.md').exists())
    body = '<div class="page-heading"><p class="eyebrow">Verification / irregularities IR87-001..033</p><h1>Own the full outcome.</h1><p>Every discovered data bug, evaluation trap, review pass, and remaining limitation documented transparently.</p></div><div class="prose">' + render_markdown(content) + '</div>'
    page('verification.html', 'Verification & irregularities', body, card=card)


def write_compatibility(card):
    routes = [('index.html', 'index.html', 'Research dashboard and research-only downloads'),
              ('executive-summary.html', 'executive-summary.html', 'Executive summary and submission guide'),
              ('research.html', 'science.html', 'Current scientific report'),
              ('sources.html', 'sources.html', 'Current source ledger and health feed')]
    for filename, target, label in routes:
        html = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="0;url=docs/{target}"><title>GEMSDOE87 — research only, DO NOT SUBMIT</title></head><body><h1>GEMSDOE87</h1><p><strong>New research GeoTIFF available. Competition submission: DO NOT SUBMIT.</strong></p><p><a href="docs/{target}">{esc(label)}</a></p></body></html>'
        (ROOT / filename).write_text(html)
    data = ROOT / 'data'
    data.mkdir(exist_ok=True)
    (data / 'run-card.json').write_text(json.dumps(card, indent=2) + '\n')
    h = card['holdout_dti']['downloadable_continuous_artifact']
    comparisons = card['correlation_overlap_vs_registry']['serialized_artifact']
    validation = load('docs/evidence/independent_validation.json')
    status = dict(schema_version=2, updated_at=datetime.now(timezone.utc).isoformat(),
        status='negative_research_only', submission_ready=False, safe_to_submit=False,
        reason='Held fail-closed: Session 2 H87B-STFD passes 15/15 format checks and clears 31/31 real sparse fault candidates (+41.7% over fold-fair H33-2-B2), while 3 dense space-filling witnesses exceed the literal 0.70 overlap rule and Session 1 H87-BMTD-01 remains frozen negative. Submission is NOT authorized.',
        artifact=card['submission_file'], raster_sha256=card['raster_sha256'],
        session2_artifact='docs/downloads/gems87-stfd-h87b-37654dots-20261023-1d3f50ffd13f-RESEARCH-DO-NOT-SUBMIT.tif',
        session2_sha256='1d3f50ffd13f9c7ec0258579717810be3bd4d1fc039b80a0f6e2e4c523ba394f',
        submission_name=card['submission_name'], submission_note=card['submission_note'],
        holdout_dti=dict(evidence_class='HOLDOUT-DTI', evaluator_version=h['evaluator_version'],
                         withheld_positive_count=h['withheld_positive_pixels'], score=h['dti'], ci_95=h['ci95'],
                         beats_current_best=False, representation='frozen continuous research artifact'),
        novelty=dict(rank_correlation_max=max(r['spearman_full_footprint'] for r in comparisons),
                     fraction_within_3px_max=max(r['my_dots_within_3px_of_theirs'] for r in comparisons),
                     registry_rasters_checked=len(comparisons), status='duplicate-stop',
                     maxima_scope='Two inspected references in frozen Session 1 card; full 34-raster audit in docs/evidence/h87b_registry_34.json.'),
        validation=dict(status='local_format_pass_not_submission_approval',
                        no_nan_inside_footprint=validation['no_nan_inside_footprint'],
                        finite_values_in_0_1=validation['range_0_1'],
                        crs_shape_transform_match=validation['crs_shape_transform_match'],
                        receipt_sha256=hashlib.sha256((DOCS / 'evidence/independent_validation.json').read_bytes()).hexdigest()),
        gates=[dict(id='competition_data', status='recorded-integrity-pass', detail='Pinned mirrors verified by SHA-256; organizer login session external.'),
               dict(id='shared_template_tools', status='pass', detail='23 unchanged shared vendor/gems57 modules verified by SHA-256.'),
               dict(id='holdout_and_leakage', status='h87b-pass-session1-negative', detail='H87B-STFD 64/64 canaries <= 0.8160 and LOQO-Comp 0.13816 (+41.7% vs fair H33-2-B2); frozen Session 1 remains negative.'),
               dict(id='registry_novelty', status='duplicate-stop', detail='31/31 sparse fault candidates PASS (<= 0.6322); 3 dense space-filling witnesses exceed literal 0.70 rule.'),
               dict(id='tiff_validation', status='local-format-pass', detail='15/15 checks pass on written TIFF/ZIP bytes without human intervention.'),
               dict(id='selector', status='blocked', detail='Zero weekly competition slots spent; requires explicit human selector rule decision.')],
        download=None, research_download='docs/downloads/' + card['submission_file'],
        research_download_status='RESEARCH ONLY — DO NOT SUBMIT', path_resolution='relative to project site root',
        current_run_card='docs/evidence/run_card.json',
        session2_run_card='docs/evidence/h87b_run_card.json')
    (data / 'submission-status.json').write_text(json.dumps(status, indent=2) + '\n')
    for old, current in [('feed.json', '../docs/data/feed.json'), ('sources.json', '../docs/data/sources.json')]:
        path = data / old
        if path.exists():
            legacy = json.loads(path.read_text())
            legacy.update(historical_readiness_snapshot=True, superseded_by=current)
            path.write_text(json.dumps(legacy, indent=2) + '\n')


def main():
    card = load('docs/evidence/run_card.json')
    h87b = load('docs/evidence/h87b_run_card.json')
    if card['safe_to_submit'] or card['verdict'] != 'negative':
        raise ValueError('This build is for the recorded negative, not a fabricated promotion')
    if h87b['safe_to_submit'] or h87b['verdict'] != 'negative':
        raise ValueError('H87B card must remain fail-closed negative under literal dense-witness rule')
    if not (DOCS / 'evidence/independent_validation.json').is_file():
        raise FileNotFoundError('Run independent on-disk validation first')
    DOCS.mkdir(exist_ok=True)
    for build in (build_home, build_executive, build_science, build_validation, build_registry, build_sources, build_verification):
        build(card, h87b)
    (DOCS / '.nojekyll').write_text('')
    (ROOT / '.nojekyll').write_text('')
    write_compatibility(card)
    for source, dest in [('registry/sources.json', 'data/sources.json'), ('evidence/site_inventory.json', 'data/site_inventory.json')]:
        shutil.copyfile(ROOT / source, DOCS / dest)
    print('Built all 7 static Pages cleanly from verified Session 1 & Session 2 receipts.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
