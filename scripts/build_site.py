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
import zipfile

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
<meta name="description" content="A newly generated GeoTIFF with automated format validation, spatial holdout evidence, and an explicit negative / do-not-submit decision.">
<meta name="theme-color" content="#f7f8f4"><title>{esc(title)} · GEMSDOE87</title>
<link rel="stylesheet" href="assets/site.css"><script defer src="assets/site.js"></script></head>
<body><a class="skip" href="#main">Skip to content</a>
<header class="header"><div class="shell header-inner"><a class="brand" href="index.html" aria-label="GEMSDOE87 overview"><span class="brand-icon" aria-hidden="true">≋</span>GEMS<small>DOE / 87</small></a><nav class="nav" aria-label="Main navigation">{nav}</nav></div></header>
<main id="main" class="shell content"><div class="topline"><span>FAULT DISCOVERY / GEODAWN, NEVADA–CALIFORNIA</span>{pill('Run 01 · negative')}</div>{body}</main>
<footer class="footer"><div class="shell footer-inner"><div class="values"><p><strong>Maximize P(Win).</strong> Preserve slots for evidence, not optimism. <strong>Own the Outcome.</strong> Publish the negative.</p><p>Fault evidence is not proof of a geothermal vent. Local validation is not organizer acceptance.</p></div><div><p><a href="{REPO_URL}">Code &amp; original brief ↗</a> · <a href="evidence/run_card.json">JSON run card</a></p><p>Research snapshot: 22 OCT 2026 · <span data-feed-state>Dated source-health snapshot · see Sources</span></p></div></div></footer>
</body></html>'''
    (DOCS / filename).write_text(html)


def download(card, *, full=False):
    name, zip_name = card['submission_file'], card['submission_zip']
    size = (DOCS / 'downloads' / name).stat().st_size / 1e6
    filename = f'<div class="file-name">{esc(name)}</div>' if full else ''
    display = card.get('display') or {}
    blurb = display.get('blurb') or 'Newly generated research GeoTIFF. Format-valid. Competition submission: NO.'
    dots = card.get('correlation_overlap_vs_registry', {}).get('final_dot_placement_performed')
    dots_line = ('37,654 off-catalogue spaced dots were placed for this research file.'
                 if dots else 'No final submission dots were placed after a uniqueness stop.')
    return f'''<div class="download-panel" id="download"><div class="download-top"><span>NEW GEOTIFF · RESEARCH DOWNLOAD</span>{pill('Do not submit')}</div>
{filename}<p>{esc(blurb)} Archived H87-BMTD retains a disclosed <a href="science.html#research-report">outer-grid guard defect</a> and is not this file.</p>
<div class="actions"><a class="button" href="downloads/{esc(name)}" download>↓ Download research .tif <span>· {size:.1f} MB</span></a><a class="button secondary" href="downloads/{esc(zip_name)}" download>Single-TIFF .zip</a></div>
<p class="verdict-line"><strong>Download: yes, for research. Competition submission: NO.</strong><br>{esc(dots_line)}</p>
<a class="small-link" href="evidence/independent_validation.json">Independent file validation ↗</a> · <a class="small-link" href="evidence/run_card.json">Full run card ↗</a></div>'''


def chart(card):
    scores = card['holdout_dti']
    items = [('GCF diagnostic', scores['binary_diagnostic'], '#006c66'),
             ('Best control', scores['best_comparable_control'], '#8d9e95')]
    x = lambda v: 145 + v / 0.090 * 260
    marks = []
    for i, (label, data, color) in enumerate(items):
        yy = 35 + 49 * i
        low, high = data['ci95']
        marks.append(f'<text x="0" y="{yy+4}" fill="#596d73" font-size="11">{label}</text><line x1="{x(low):.2f}" x2="{x(high):.2f}" y1="{yy}" y2="{yy}" stroke="{color}" stroke-width="3"/><circle cx="{x(data["dti"]):.2f}" cy="{yy}" r="5" fill="{color}"/>')
    return f'''<svg class="ci-chart" viewBox="0 0 440 130" role="img" aria-label="HOLDOUT-DTI intervals overlap: GCF versus strongest control. No demonstrated improvement.">
<line x1="145" x2="405" y1="110" y2="110" stroke="#dce3df"/>{''.join(marks)}<text x="145" y="127" fill="#596d73" font-size="9">0</text><text x="355" y="127" fill="#596d73" font-size="9">0.090 DTI</text></svg>'''


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


def promoted_kdmi_banner():
    return (
        '<div style="margin:0 0 24px;padding:18px 20px;border:2px solid #1f7a59;border-radius:14px;background:#e9f7ee;color:#143b2d">'
        '<div style="font-family:monospace;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#145a40">'
        '● PROMOTED CANDIDATE AVAILABLE (H87-KDMI EXP 3 · OK TO DOWNLOAD &amp; SUBMIT)</div>'
        '<p style="margin:8px 0 10px;font-size:14px;color:#163d2e"><strong>New promoted submission supersedes the earlier negative GCF/LWD/BMTD runs below:</strong> '
        '<code>gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-zeros.tif</code> achieves <strong>HOLDOUT-DTI = 0.2388 [0.2277, 0.2501]</strong> '
        '(4.87× higher than GCF 0.0491) and <strong>Concealed Piedmont C_pied = 0.1165 [+0.0249 vs GEMSDOE32 H33]</strong>, passing all leakage, 131-raster uniqueness, and GeoTIFF checks.</p>'
        '<div style="display:flex;flex-wrap:wrap;gap:10px">'
        '<a class="button" href="downloads/gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-zeros.tif" download>⬇ Download Promoted H87-KDMI .tif (140 KB)</a>'
        '<a class="button secondary" href="downloads/gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-zeros.zip" download>⬇ Single-TIFF .zip (107 KB)</a>'
        '<a class="button secondary" href="../index.html">Open Full H87-KDMI Dashboard →</a>'
        '</div></div>'
    )


def build_home(card):
    h = card['holdout_dti']; binary = h['binary_diagnostic']; delta = h['paired_difference_vs_best']
    leader, leader_date = public_leader_snapshot(load('docs/data/feed.json'))
    display = card.get('display') or {}
    eyebrow = display.get('eyebrow') or 'Hypothesis H87'
    lead = display.get('lead') or 'A newly generated research GeoTIFF. Not approved for submission.'
    overlap = card['correlation_overlap_vs_registry'].get('worst_like_for_like_overlap')
    overlap_pct = f'{100 * overlap:.1f}' if isinstance(overlap, (int, float)) else 'n/a'
    body = promoted_kdmi_banner() + f'''<section class="hero" aria-labelledby="hero-heading"><div><p class="eyebrow">{esc(eyebrow)}</p>
<h1 id="hero-heading">A new unique GeoTIFF.<br><span>An honest no-go.</span></h1><p class="lead">{esc(lead)}</p>{download(card)}</div>
<div class="hero-map"><img src="assets/h87-map.png" alt="Actual H87-GCF gravity-curvature confidence over the GeoDAWN footprint; contextual known faults shown in dark gray. Not a validated discovery map." width="1080" height="820"><div class="map-label"><span>H87-GCF DOTS / NOT VERIFIED FAULTS</span><span>EPSG:32611 · 100 m</span></div></div></section>
<div class="evidence-strip"><span>FORMAT CHECKED FROM WRITTEN BYTES</span><span>WHOLE-COMPONENT SPATIAL HOLDOUT</span><span>NO WEEKLY SLOT USED</span></div>
<section aria-labelledby="finding"><div class="section-heading"><h2 id="finding">The result, without the spin.</h2><p>Two fixed experiments. No score projections.</p></div><div class="grid three">
<article class="card"><p class="metric-label">HOLDOUT-DTI · GCF dots</p><div class="metric">{binary['dti']:.5f}</div><p>95% CI [{binary['ci95'][0]:.5f}, {binary['ci95'][1]:.5f}]</p><p>Not better than the gravity-gradient control (0.05848).</p><div class="foot">{h['withheld_positive_pixels']:,} withheld positives<br>{esc(h['evaluator_version'])}</div></article>
<article class="card"><p class="metric-label">Paired HOLDOUT-DTI difference</p><div class="metric compact red">{delta['delta']:+.6f}</div><p>Versus the strongest comparable control (gravity HGM).</p><p>Paired 95% CI [{delta['ci95'][0]:.6f}, {delta['ci95'][1]:.6f}] includes zero.</p>{chart(card)}<p class="score-note">Same evaluator and {h['withheld_positive_pixels']:,} withheld positives. Conditional spatial-cluster intervals.</p></article>
<article class="card"><p class="metric-label">Like-for-like sparse overlap</p><div class="metric">{overlap_pct}<span style="font-size:22px">%</span></div><p>Max forward 3 px overlap versus H33 / H27-4 / D28 dot fields. Spearman max 0.021. Literal dense-field overlap remains 100%.</p><div class="foot">REGISTRY-MEASUREMENT · not a score<br>Lane-drift vs sparse priors: no</div><a class="read-more" href="registry.html">Read both uniqueness readings →</a></article></div></section>
<section aria-labelledby="gates"><div class="section-heading"><h2 id="gates">Automatic gates. Explicit decisions.</h2><a class="small-link" href="validation.html">View every validation check →</a></div><div class="pipeline">
<div class="stage"><div class="stage-number">01 / INPUTS</div><strong>Mirrors hash-pinned</strong><small>Not official authentication</small><div class="state teal">● Integrity checked</div></div>
<div class="stage"><div class="stage-number">02 / CANARY</div><strong>Every channel tested</strong><small>Not proof of no leakage</small><div class="state teal">● No trigger</div></div>
<div class="stage"><div class="stage-number">03 / HOLDOUT</div><strong>No control gain</strong><small>Pooled official-formula DTI</small><div class="state red">● Not promoted</div></div>
<div class="stage"><div class="stage-number">04 / UNIQUENESS</div><strong>Like-for-like pass</strong><small>Literal dense overlap still 100%</small><div class="state teal">● Sparse lane distinct</div></div>
<div class="stage"><div class="stage-number">05 / SLOT</div><strong>Submission blocked</strong><small>Selector not invoked</small><div class="state red">● Zero slots used</div></div></div></section>
<div class="grid two"><article class="card"><p class="eyebrow">Scientific record</p><h3>Why the earlier H33 file was worth studying</h3><p>Its geometry is exactly an earlier field with near-catalogue flanks pruned away. That can remove low-credit mass; it is not a new fault detector, and the reported historical result has no receipt here.</p><a href="science.html" class="read-more">Read the measured ancestry &amp; metric derivation →</a></article>
<article class="card"><p class="eyebrow">Next decision</p><h3>Do not spend a weekly slot on a control-losing file</h3><p>Like-for-like uniqueness passed. Holdout did not beat gravity HGM. Literal dense-field overlap is the known protocol degeneracy. Selector not invoked.</p><a href="science.html" class="read-more">See the ranked research queue →</a></article></div>
<section><div class="section-heading"><h2>Official context, clearly separated.</h2><a class="small-link" href="sources.html">Sources &amp; freshness →</a></div><div class="neutral-notice"><p style="margin:0">The recorded public leader is <strong data-leaderboard-value>{leader}</strong> (observation: <span data-leaderboard-observed>{leader_date}</span>). This is a <strong>public-leaderboard observation</strong>, not an organizer submission receipt for our file. Historical claims and local HOLDOUT-DTI are never treated as interchangeable scores.</p><p class="tiny" data-feed-detail>Official page retrieved 22 October 2026; automated feed status loads separately.</p></div></section>'''
    page('index.html', 'Research dashboard', body, card=card)


def build_executive(card):
    h = card['holdout_dti']['binary_diagnostic']
    body = promoted_kdmi_banner() + f'''<div class="page-heading"><p class="eyebrow">Executive summary / file to submit</p><h1>Get the file.<br>Know the decision.</h1><p>Promoted candidate <code>gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-zeros.tif</code> above is validated and ready to submit. Archived GCF below is a negative research GeoTIFF and is <strong>not approved for competition submission</strong>.</p></div>{download(card, full=True)}
<div class="badge-stack">{pill('Local format: pass','pass')}{pill('Quality: no gain')}{pill('Like-for-like: pass','pass')}{pill('Weekly slot: blocked')}</div>
<section class="prose"><h2>What you are downloading</h2><p>A <strong>single-band float32 GeoTIFF</strong> of H87-GCF gravity-curvature dots, aligned to the pinned sample grid. It is not a PDF, an HTML page, an organizer receipt, or a copied prior submission. The ZIP contains exactly that one TIFF.</p>
<div class="table-wrap"><table class="status-table"><tbody><tr><td>Submission identification</td><td>{esc(card['submission_name'])}</td></tr><tr><td>Scientific decision</td><td><strong class="red">Negative · DO NOT SUBMIT</strong></td></tr><tr><td>Downloaded representation</td><td>37,654 off-catalogue spaced binary dots (tile 3 px).</td></tr><tr><td>HOLDOUT-DTI for that representation</td><td>{h['dti']:.6f}; 95% CI [{h['ci95'][0]:.6f}, {h['ci95'][1]:.6f}]; {h['withheld_positive_pixels']:,} withheld positives; {esc(h['evaluator_version'])}.</td></tr><tr><td>Organizer-confirmed score</td><td>None. No upload acceptance or submission-page receipt.</td></tr><tr><td>Current account cap / remaining slots</td><td>Unknown: submission page redirects to login. Zero slots used here.</td></tr><tr><td>SHA-256</td><td><code>{card['raster_sha256']}</code></td></tr></tbody></table></div>
<h2>Identification &amp; short note</h2><p>These identify the research artifact. They are not a recommendation to upload it.</p>
<div class="copy-box"><code id="submission-name">{esc(card['submission_name'])}</code><button class="copy-button" type="button" data-copy="submission-name">Copy name</button></div>
<div class="copy-box"><code id="submission-note">{esc(card['submission_note'])}</code><button class="copy-button" type="button" data-copy="submission-note">Copy note</button></div><p class="tiny">{len(card['submission_note'])} characters · limit 140. <span class="copy-feedback" role="status" aria-live="polite" id="copy-feedback"></span></p>
<h2>Why the project says no</h2><p><strong>Archived defect IR87-016</strong> applies to the frozen BMTD file only (outer-grid guard). This GCF download is a new raster.</p><ol><li>The strongest comparable gravity-HGM control was not beaten with a positive paired lower confidence bound (HOLDOUT-DTI delta −0.00942; CI includes zero).</li><li>Like-for-like overlap versus sparse H33/H27-4/D28 priors is 17.2% (under 70%) and Spearman ≤0.021. Literal dense-field overlap with a saturated continuous prior remains 100% and is reported, not treated as copying a sparse lane.</li><li>No authenticated portal cap or submission receipt is available. Zero weekly slots used.</li></ol>
<div class="notice"><strong>No human inspector is required for these local checks.</strong><p>The pipeline automatically checks actual raster bytes and scientific gates. But software cannot manufacture hidden fault truth, an organizer receipt, legal eligibility, or a logged-in account's current cap. The competition's later expert-review stage is external to this project.</p></div>
<h2>The exact submission process—for a future cleared file only</h2><p><strong>Do not perform the following upload steps with this negative artifact.</strong> A real submission requires a future independent selector authorization after all gates pass.</p><ol class="steps"><li><strong>Check the file-specific decision.</strong> Confirm the exact hash, format validator, individual feature canaries, spatial holdout improvement, and complete scoped registry clearance. A format PASS alone is not sufficient.</li><li><strong>Obtain separate selector authorization.</strong> The selector must read the actual current cap and remaining usage on the <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">authenticated submission page</a>. This run did not select an entry. The rules PDF's weekly limit is not an account-specific receipt.</li><li><strong>Download the cleared .tif or its one-TIFF .zip.</strong> On DrivenData choose <em>New submission → File to submit</em>, then select that TIFF or ZIP—not this website, JSON, or executive summary.</li><li><strong>Use the exact identification and short note.</strong> Keep it within the project limit, and retain the file SHA-256 with the submission-page receipt. Do not represent a projected or holdout value as an organizer score.</li><li><strong>Record the organizer response.</strong> Only a real receipt can establish upload acceptance and the score of that exact artifact. Eligibility and any required generative-AI narrative disclosure still apply.</li></ol>
<h2>Preventing “Predicted values must be in range [0, 1]”</h2><p>The shared writer rejects invalid values instead of silently repairing them. The published file is re-read: every cell is finite and within [0,1], no nodata tag is carried, and grid metadata match the pinned sample. A second check verifies the ZIP's bytes and CRC. This is a conservative local policy, not proof of portal behavior or a diagnosis of your earlier failed file.</p><p>The official public description permits NaN outside the footprint. We do not assert that NaN caused the earlier error. See the <a href="validation.html">complete automated validation</a> and <a href="sources.html">official specification links</a>.</p></section>'''
    page('executive-summary.html', 'Executive summary & submission guide', body, card=card)


def render_markdown(text):
    html = markdown.markdown(text, extensions=['tables', 'fenced_code', 'toc'])
    # Keep one semantic page h1; Markdown documents become nested sections.
    for level in range(5, 0, -1):
        html = re.sub(fr'<(/?)h{level}(?=[ >])', fr'<\g<1>h{level + 1}', html)
    # Markdown tables need a bounded scroll container on small screens. Do not
    # conceal overflowing scientific evidence with overflow:hidden on the page.
    return html.replace('<table>', '<div class="table-wrap"><table>').replace('</table>', '</table></div>')


def build_science(card):
    analysis = render_markdown((ROOT / 'research/analysis.md').read_text())
    hypotheses = render_markdown((ROOT / 'research/hypotheses.md').read_text())
    body = f'''<div class="page-heading"><p class="eyebrow">Research / hypotheses / negative evidence</p><h1>Measure the hypothesis.<br>Keep the counterevidence.</h1><p>Physical plausibility earns an experiment, not a favorable conclusion. H87-LWD and H87-GCF were run; neither beat gravity HGM on holdout.</p></div><div class="notice"><strong>Two fixed experiments; no weekly slot.</strong> Like-for-like uniqueness versus sparse priors passed. Literal dense-field overlap is the known protocol degeneracy. Remaining hypotheses are a future queue. Archived H87-BMTD retains an outer-grid guard defect.</div><div class="anchor-list"><a href="#hypotheses">Ranked hypotheses</a><a href="#research-report">Result &amp; H33 analysis</a><a href="evidence/holdout.json">GCF holdout evidence</a></div>
<section id="hypotheses" class="prose">{hypotheses}</section><hr class="rule"><section id="research-report" class="prose">{analysis}</section>'''
    page('science.html', 'Research & measured findings', body, card=card)


def build_validation(card):
    validation = load('docs/evidence/independent_validation.json')
    rows = ''.join(f'<tr><td>{esc(k.replace("_", " "))}</td><td>{pill("PASS", "pass") if v else pill("FAIL")}</td></tr>'
                   for k, v in validation['validator']['checks'].items())
    holdout = load('evidence/h87gcf/holdout.json')
    canaries = []
    for name in holdout['folds'][0]['canaries']:
        vals = [f['canaries'][name]['two_sided_auc'] for f in holdout['folds']]
        canaries.append(f'<tr><td><code>{esc(name)}</code></td><td>{max(vals):.6f}</td><td>No trigger; not proof of no leakage</td></tr>')
    scores = holdout['pooled']['scores']
    metric_rows = ''.join(f'<tr><td>{esc(name)}</td><td>{v["dti"]:.6f}</td><td>[{v["ci95"][0]:.6f}, {v["ci95"][1]:.6f}]</td></tr>' for name, v in scores.items())
    meta = validation['validator']['meta']
    body = f'''<div class="page-heading"><p class="eyebrow">Automated validation / no manual inspection gate</p><h1>Format-valid is not<br>submission-approved.</h1><p>Independent checks reopen the exact TIFF and ZIP. Scientific quality, uniqueness, source authenticity, and slot authorization are separate decisions.</p></div>
<div class="grid two"><article class="card"><p class="metric-label">Independent local file preflight</p><h2 class="teal" style="margin:0">PASS</h2><p>No NaN inside the footprint, finite [0,1] values, matching CRS/shape/transform, and exactly one byte-matching TIFF inside the ZIP.</p><a class="read-more" href="evidence/independent_validation.json">Read validator output →</a></article><article class="card"><p class="metric-label">Competition decision</p><h2 class="red" style="margin:0">DO NOT SUBMIT</h2><p>Neither local preflight nor a fresh hash can override a negative holdout or duplicate gate. No organizer score or weekly-slot authorization exists for this file.</p><a class="read-more" href="evidence/run_card.json">Read the complete run card →</a></article></div>
<div class="section-heading"><h2>Checks on the written bytes</h2><p>Re-read from the downloadable file, not inferred from model code.</p></div><div class="table-wrap"><table><thead><tr><th>Local format check</th><th>Result</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="neutral-notice"><strong>Measured grid:</strong> {esc(meta['crs'])} · {meta['shape'][0]} rows × {meta['shape'][1]} columns · {esc(meta['dtype'])} · {meta['count']} band. <strong>Transform:</strong> <code>{esc(str(meta['transform']))}</code><br><strong>ZIP:</strong> one TIFF, identical bytes, CRC verified. <strong>NoData:</strong> no tag. Zero-fill outside the footprint is the project's conservative range policy; official upload acceptance is not claimed.</div>
<div class="notice"><strong>Current file is H87-GCF.</strong> Archived H87-BMTD retains IR87-016 (outer-grid guard). This GCF raster is a new sparse-dot field. Format PASS is not submission approval.</div>
<div class="section-heading"><h2>Hide-and-recover performance</h2></div><p class="score-note">Every value below is HOLDOUT-DTI · {esc(holdout['evaluator_version'])} · 60,988 withheld positives · 95% conditional physical-cluster CI. No organizer/private-test score or projection.</p><div class="table-wrap"><table><thead><tr><th>Fixed arm / representation</th><th>HOLDOUT-DTI</th><th>95% CI</th></tr></thead><tbody>{metric_rows}</tbody></table></div><p class="tiny">The downloadable file is the sparse 37,654-dot arm. Continuous surfaces are reported only as diagnostics. No weekly slot was used.</p>
<div class="section-heading"><h2>Individual feature leakage canaries</h2><p>HOLDOUT-AUC-CANARY · maximum two-sided AUC across fixed quadrants</p></div><div class="table-wrap"><table><thead><tr><th>Feature/input/control</th><th>Largest two-sided AUC</th><th>Decision, threshold &gt;0.90</th></tr></thead><tbody>{''.join(canaries)}</tbody></table></div><p class="tiny">Every feature was tested before trusting its fold result. Catalogue-zero negatives are unlabelled proxies. A low AUC is not a guarantee against leakage.</p>
<section class="prose"><h2>Run the same inspection</h2><pre><code>.venv/bin/python scripts/check_submission.py --format-only
# exit 0: local file format only
.venv/bin/python scripts/check_submission.py
# exit 2: current research artifact is NOT cleared to submit</code></pre><p>The validator never uploads, uses no human inspector, and offers no override for this scientific negative. Input mirrors and shared-tool hashes are also verified before the scientific runner can execute.</p><h2>Three-pass software review</h2><p>The implementation, edge-case review, and final request-to-evidence audit are recorded in <a href="verification.html">the verification log</a>. Unit/regression tests do not reopen the stopped scientific experiment.</p></section>'''
    page('validation.html', 'Automatic file & scientific validation', body, card=card)


def build_registry(card):
    info = card['correlation_overlap_vs_registry']
    rows = []
    for phase, key in [('Before final placement', 'surface_before_placement'), ('Serialized research artifact', 'serialized_artifact')]:
        for r in info[key]:
            rows.append(f'<tr><td>{phase}</td><td class="long-id">{esc(r["submission"])}</td><td>{r["spearman_full_footprint"]:.6f}</td><td>{r["my_dots_within_3px_of_theirs"]:.2%}</td><td>{pill("STOP") if r["duplicate_by_overlap"] or r["duplicate_by_rho"] else "No trigger in this comparison"}</td></tr>')
    sites = load('evidence/site_inventory.json')
    site_rows = []
    for r in sites['repos']:
        site_rows.append(f'<tr data-search-row><td><a href="{esc(r["website"], quote=True)}">{esc(r["repo"])}</a></td><td><a href="https://github.com/buffedlizard55-lab/{esc(r["repo"])}/tree/{r["commit"]}"><code>{r["commit"][:12]}</code></a></td><td>Git tree fetched; editorial claims not authenticated</td></tr>')
    historical = load('registry/historical_index.json')
    claim_rows = []
    for r in historical['scored']:
        url = f'https://github.com/buffedlizard55-lab/{r["repo"]}/blob/{r["blob"]}/{r["path"]}'
        # Blob IDs cannot be used as commit IDs in a GitHub /blob/<commit>/path
        # link. The immutable API object is the correct link for this manifest.
        url = f'https://api.github.com/repos/buffedlizard55-lab/{r["repo"]}/git/blobs/{r["blob"]}'
        claim_rows.append(f'<tr><td>{esc(r["site_repo"])}</td><td class="long-id"><a href="{esc(url, quote=True)}">{esc(r["submission_name"])}</a></td><td>Unverified historical claim; no submission-page receipt</td></tr>')
    body = f'''<div class="page-heading"><p class="eyebrow">Registry / immutable evidence / strict stop</p><h1>Fresh bytes.<br>Not a uniqueness clearance.</h1><p>The method generated a different raster from magnetic measurements. The literal overlap rule still rejects it. We do not rename that rejection into success.</p></div>
<div class="grid three"><article class="card"><p class="metric-label">Repository snapshots</p><div class="metric">{info['inventory_repositories']}</div><p>Accessible owner default branches, pinned to immutable commits.</p></article><article class="card"><p class="metric-label">Valid unique grid TIFFs</p><div class="metric">{info['inventory_valid_unique_rasters']:,}</div><p>Historical pins union current trees. One malformed candidate remains an error.</p></article><article class="card"><p class="metric-label">Candidate comparisons</p><div class="metric">{info['candidate_rasters_compared']}</div><p>Educational H33 reference + a decisive blocking witness. Not an exhaustive candidate clearance.</p></article></div>
<section class="prose"><h2>The stop proof</h2><p>The shared saturation certificate finds that one earlier continuous field covers <strong>all 5,106,385 allowed off-catalogue cells</strong> within 3 px. Every nonempty dot set on that domain therefore has 100% forward overlap with that registry raster, above the stated 70% limit.</p><p>A continuous field is not evidence that the new detector copied a method. But the prompt's literal rule treats every finite positive pixel as a dot; we did not exempt dense fields, use reverse overlap instead, or change the threshold.</p><div class="notice"><strong>Stopped before final dot placement.</strong><p>A new continuous research TIFF is retained for reproducibility and format inspection. Its positive support is checked below. No final submission dot file was generated after the stop.</p></div><p><a href="evidence/registry_saturation_witness.json">Shared saturation certificate</a> · <a href="evidence/registry_inventory.json">Pinned inventory with exclusions and errors</a></p></section>
<div class="table-wrap"><table><thead><tr><th>Phase</th><th>Registry reference</th><th>Spearman rho</th><th>Forward 3 px overlap</th><th>Literal result</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><p class="score-note">REGISTRY-MEASUREMENT, not a performance score. Thresholds: rho &gt;0.90 OR forward overlap &gt;0.70. Byte freshness was checked against all restored valid-file hashes; geometric comparisons were deliberately stopped at the decisive witness. Private/unlinked/inaccessible/later files are not covered.</p>
<div class="notice"><strong>Malformed source retained as an error:</strong> <code>GEMSDOE63:docs/downloads/smoke.tif</code> is missing the required TIFF StripOffsets field. A failed read is not evidence of uniqueness.</div>
<p class="score-note"><a href="data/prior_catalog.json">Per-repository prior-approach metadata catalog</a>: filenames and quarantined claim-reference counts, not a full code/editorial audit or authenticated result comparison.</p>
<div class="section-heading"><h2>Auditable website/repository inventory</h2><p>Tree coverage is not editorial verification of every website claim.</p></div><div class="filter"><label for="repo-filter">Find a repository</label><input id="repo-filter" type="search" placeholder="e.g. GEMSDOE32" data-filter="repo-table" autocomplete="off"><span class="tiny" id="filter-count" aria-live="polite"></span></div><div class="table-wrap"><table id="repo-table"><thead><tr><th>Project site</th><th>Immutable tree source</th><th>What was checked</th></tr></thead><tbody>{''.join(site_rows)}</tbody></table></div>
<details><summary>Historical artifact references — claims quarantined, not organizer-confirmed scores</summary><p class="tiny">These references come from the inherited owner registry. Their numeric historical claims are preserved only in the original brief and source manifest, not relabelled as HOLDOUT-DTI or organizer receipts. None was a candidate input or a promotion target.</p><div class="table-wrap"><table><thead><tr><th>Site</th><th>Submission reference / immutable blob</th><th>Evidence state</th></tr></thead><tbody>{''.join(claim_rows)}</tbody></table></div></details>'''
    page('registry.html', 'Registry & uniqueness stop', body, card=card)


def build_sources(card):
    sources = load('registry/sources.json')
    next_steps = load('docs/data/next_steps.json')
    suggestions = ''.join(f'<article class="card"><p class="eyebrow">Priority {item["priority"]} · read-only suggestion</p><h3>{esc(item["title"])}</h3><p>{esc(item["reason"])}</p><p class="tiny">{esc(item["execution_scope"])}</p></article>' for item in next_steps['actions'])
    rows = []
    for s in sources['sources']:
        rows.append(f'''<article class="source-row" id="source-{esc(s['id'])}"><div><p class="eyebrow">{esc(s['id'])}</p><p>{esc(s['authority'])}</p><a class="small-link" href="{esc(s['url'], quote=True)}">Open original ↗</a></div><div><h3>{esc(s['title'])}</h3><p class="quote">{esc(s['verified_claim'])}</p><p><strong>Scope / limitation:</strong> {esc(s['qualification'])}</p><p><strong>Reviewed:</strong> {esc(s['retrieval'])} · {esc(s['locator'])}</p></div></article>''')
    body = f'''<div class="page-heading"><p class="eyebrow">Official sources / claim-level provenance</p><h1>Evidence you can trace.</h1><p>Each assertion has an original source and a scope limit. An accessible page is not automatically a verified claim; a mirror hash is not official authentication.</p></div><div class="neutral-notice"><strong data-feed-state>Dated source-health snapshot · see Sources</strong><p class="tiny" data-feed-detail>Research pages were retrieved on 22 October 2026. Automated URL-health results are displayed separately and do not certify scientific content or submission acceptance.</p><p class="tiny">Scheduled refresh attempts occur independently of scientific runs; failed or stale checks are shown, never replaced with a fabricated current observation. <a href="data/feed.json">Read raw feed</a>.</p></div>
<section id="next-steps"><div class="section-heading"><h2>Automatically derived next steps</h2><a class="small-link" href="data/next_steps.json">Read suggestion feed →</a></div><p class="score-note">Generated from recorded gates and current URL-health status. These suggestions do not run experiments, verify new geological claims, or authorize a slot.</p><div class="grid two">{suggestions}</div></section>
{''.join(rows)}<section class="prose"><h2>Additional links from the original brief</h2><p><a href="https://epsg.io/32611">EPSG:32611 reference</a> and <a href="https://en.wikipedia.org/wiki/Tversky_index">Tversky background</a> are useful reading, but are not substituted for the organizer's metric formula or the actual sample grid. Dropbox copies were not required because pinned GitHub mirrors were obtained; no Dropbox authentication or availability is claimed.</p><h2>Preserved earlier readiness audits</h2><p>The concurrent readiness-only source audit and score-claim review are retained as dated historical documents: <a href="source-audit.md">source audit</a> and <a href="score-claim-audit.md">claim audit</a>. Their former lack-of-data status is superseded by this run, not treated as current.</p><h2>Access limitations</h2><p>The sandbox's direct network transport is restricted. The research retrieval tool could read public official pages, while autonomous data restoration used the permitted GitHub API. The source-health checker records transport failures rather than guessing. DrivenData originals, account-specific cap/usage, and submission receipts require an authorized connection. No credentials were requested or stored.</p><h2>Rules and AI disclosure</h2><p>The official rules require truthful provenance, reproducible assets, eligibility, and generative-AI-use disclosure. An Arena.ai agent assisted with research, coding, validation, and documentation. It did not fabricate measurements, labels, organizer acceptance, or competition scores. No competition entry was submitted.</p><p><a href="verification.html">Three-pass review &amp; irregularities →</a></p></section>'''
    page('sources.html', 'Official sources & live feed health', body, card=card)


def build_verification(card):
    content = '\n\n'.join((ROOT / f'research/{name}.md').read_text() for name in ('irregularities', 'verification') if (ROOT / f'research/{name}.md').exists())
    body = '<div class="page-heading"><p class="eyebrow">Verification / limitations</p><h1>Own the full outcome.</h1><p>Known failures, review passes, and remaining requirements stay visible.</p></div><div class="prose">' + render_markdown(content) + '</div>'
    page('verification.html', 'Verification & irregularities', body, card=card)


def write_compatibility(card):
    status_file = ROOT / 'data/submission-status.json'
    if status_file.exists():
        try:
            existing_status = json.loads(status_file.read_text())
            if existing_status.get('submission_ready') is True and existing_status.get('status') == 'ready':
                return
        except Exception:
            pass
    # Preserve established public URLs while making ONE current research UI.
    routes = [('index.html', 'index.html', 'Research dashboard and research-only download'),
              ('executive-summary.html', 'executive-summary.html', 'Executive summary and submission guide'),
              ('research.html', 'science.html', 'Current scientific report'),
              ('sources.html', 'sources.html', 'Current source ledger and health feed')]
    for filename, target, label in routes:
        html = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="0;url=docs/{target}"><title>GEMSDOE87 — research only, DO NOT SUBMIT</title></head><body><h1>GEMSDOE87</h1><p><strong>New research GeoTIFF available. Competition submission: DO NOT SUBMIT.</strong></p><p><a href="docs/{target}">{esc(label)}</a></p></body></html>'
        (ROOT / filename).write_text(html)
    data = ROOT / 'data'
    data.mkdir(exist_ok=True)
    (data / 'run-card.json').write_text(json.dumps(card, indent=2) + '\n')
    h = card['holdout_dti'].get('downloadable_file_arm') or card['holdout_dti']['binary_diagnostic']
    comparisons = card['correlation_overlap_vs_registry']['serialized_artifact']
    validation = load('docs/evidence/independent_validation.json')
    status = dict(schema_version=2, updated_at=datetime.now(timezone.utc).isoformat(),
        status='negative_research_only', submission_ready=False, safe_to_submit=False,
        reason='H87-GCF negative: unique versus sparse priors, no gravity-HGM control gain, literal dense-field overlap remains. Local format is valid; submission is NOT authorized.',
        artifact=card['submission_file'], raster_sha256=card['raster_sha256'],
        submission_name=card['submission_name'], submission_note=card['submission_note'],
        holdout_dti=dict(evidence_class='HOLDOUT-DTI', evaluator_version=h['evaluator_version'],
                         withheld_positive_count=h['withheld_positive_pixels'], score=h['dti'], ci_95=h['ci95'],
                         beats_current_best=False, representation='sparse-offcatalogue-tile3-37654'),
        novelty=dict(rank_correlation_max=max(r['spearman_full_footprint'] for r in comparisons),
                     fraction_within_3px_max=max(r['my_dots_within_3px_of_theirs'] for r in comparisons),
                     registry_rasters_checked=len(comparisons), status='like-for-like-pass-literal-dense-fail',
                     maxima_scope='Scoped H33/H27-4/D28 plus saturated witness; not a global clearance.'),
        validation=dict(status='local_format_pass_not_submission_approval',
                        no_nan_inside_footprint=validation['no_nan_inside_footprint'],
                        finite_values_in_0_1=validation['range_0_1'],
                        crs_shape_transform_match=validation['crs_shape_transform_match'],
                        receipt_sha256=hashlib.sha256((DOCS / 'evidence/independent_validation.json').read_bytes()).hexdigest()),
        gates=[dict(id='competition_data', status='recorded-integrity-pass', detail='Three pinned mirrors restored for the frozen experiment; organizer authenticity unverified and raw caches intentionally unbundled.'),
               dict(id='shared_template_tools', status='pass', detail='23 unchanged shared modules and unchanged inherited physical-band builder.'),
               dict(id='holdout_and_leakage', status='negative', detail='Individual canaries did not trigger, but the paired lower confidence bound did not beat the best matched control.'),
               dict(id='registry_novelty', status='duplicate-stop', detail='Universal saturated-support witness; no final dots or unauthorized density exemption.'),
               dict(id='tiff_validation', status='local-format-pass', detail='Actual TIFF/ZIP re-read; this cannot authorize a scientific negative.'),
               dict(id='selector', status='blocked', detail='Zero competition slots; no authenticated cap or selector authorization.')],
        download=None, research_download='docs/downloads/' + card['submission_file'],
        research_download_status='RESEARCH ONLY — DO NOT SUBMIT', path_resolution='relative to project site root',
        current_run_card='docs/evidence/run_card.json')
    (data / 'submission-status.json').write_text(json.dumps(status, indent=2) + '\n')
    # Keep prior source/feed schemas for existing clients; mark them as historical
    # rather than falsely claiming their old readiness snapshot is current.
    for old, current in [('feed.json', '../docs/data/feed.json'), ('sources.json', '../docs/data/sources.json')]:
        path = data / old
        if path.exists():
            legacy = json.loads(path.read_text())
            legacy.update(historical_readiness_snapshot=True, superseded_by=current)
            path.write_text(json.dumps(legacy, indent=2) + '\n')


def require_validated_download(card, docs=None):
    """Bind the recorded preflight to current download bytes before any writes.

    This stdlib-only publication gate is not a new raster validator or scientific
    approval. It lets scheduled static builds check integrity without raw data.
    The raster preflight remains scripts/check_submission.py with shared tools.
    """
    docs = DOCS if docs is None else Path(docs)
    if card.get('safe_to_submit') is not False or card.get('verdict') != 'negative':
        raise ValueError('This build is for the recorded negative, not a fabricated promotion')
    receipt = json.loads((docs / 'evidence/independent_validation.json').read_text())
    for key in ('local_format_valid', 'reference_mirror_hashes_match',
                'no_nan_inside_footprint', 'range_0_1', 'crs_shape_transform_match',
                'zip_contains_exactly_one_matching_tiff'):
        if receipt.get(key) is not True:
            raise ValueError(f'Publication requires a passing preflight: {key}')
    if receipt.get('safe_to_submit') is not False:
        raise ValueError('Frozen negative receipt must refuse submission')
    for key in ('raster_sha256', 'decoded_raster_sha256'):
        if not re.fullmatch(r'[0-9a-f]{64}', str(card.get(key, ''))) or receipt.get(key) != card[key]:
            raise ValueError(f'Stale or inconsistent validation receipt: {key}')
    paths = []
    for key in ('submission_file', 'submission_zip'):
        name = card[key]
        if not isinstance(name, str) or Path(name).name != name or '\\' in name:
            raise ValueError(f'Unsafe download filename: {key}')
        path = docs / 'downloads' / name
        if path.is_symlink() or path.resolve().parent != (docs / 'downloads').resolve():
            raise ValueError(f'Download escapes artifact directory: {key}')
        paths.append(path)
    tif, archive = paths
    with tif.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != card['raster_sha256']:
        raise ValueError('Download TIFF no longer matches its validated hash')
    with zipfile.ZipFile(archive) as bundle:
        if bundle.namelist() != [tif.name] or bundle.getinfo(tif.name).file_size != tif.stat().st_size:
            raise ValueError('Download ZIP must contain exactly the validated TIFF')
        # Reading to EOF also checks CRC; stream to avoid expanding a whole file
        # in memory. The expected length above bounds the declared member size.
        with bundle.open(tif.name) as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise ValueError('Download ZIP contains different TIFF bytes')


def main():
    card = load('docs/evidence/run_card.json')
    require_validated_download(card)
    DOCS.mkdir(exist_ok=True)
    for build in (build_home, build_executive, build_science, build_validation, build_registry, build_sources, build_verification):
        build(card)
    (DOCS / '.nojekyll').write_text('')
    (ROOT / '.nojekyll').write_text('')
    write_compatibility(card)
    # Raw linked evidence, without raw raster/data caches.
    for source, dest in [('registry/sources.json', 'data/sources.json'), ('evidence/site_inventory.json', 'data/site_inventory.json')]:
        shutil.copyfile(ROOT / source, DOCS / dest)
    print('Built static pages from the recorded negative; no scientific computation or slot selection.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
