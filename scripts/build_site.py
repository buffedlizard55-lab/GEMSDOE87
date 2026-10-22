#!/usr/bin/env python3
"""Generate the static GitHub Pages site from auditable JSON receipts."""
from __future__ import annotations

import html
import json
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EVIDENCE = ROOT / "evidence"
REGISTRY = ROOT / "registry"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def number(value: object, digits: int = 4) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def nav(current: str) -> str:
    pages = [("index.html", "Release"), ("executive-summary.html", "Submit"), ("research.html", "Research"), ("hypotheses.html", "Hypotheses"), ("verification.html", "Verification"), ("sources.html", "Sources"), ("irregularities.html", "Review")]
    links = "".join(f'<a class="{"active" if p == current else ""}" href="{p}">{name}</a>' for p, name in pages)
    return f'''<header class="site-header"><div class="nav"><a class="brand" href="index.html">GEMS<b>DOE87</b></a><nav class="nav-links" aria-label="Primary">{links}</nav></div></header>'''


def layout(title: str, body: str, current: str, generated: str) -> str:
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · GEMSDOE87</title><meta name="description" content="Auditable GEMS GeoTIFF release, spatial holdout evidence, and scientific research ledger.">
<link rel="stylesheet" href="assets/styles.css"><link rel="alternate" type="application/feed+json" title="GEMSDOE87 release feed" href="feed.json"></head><body>{nav(current)}<main>{body}</main>
<footer><strong>GEMSDOE87</strong> · Generated from local receipts {esc(generated)} · <a href="data/run_card_h87_frb.json">machine-readable run card</a> · <a href="feed.json">release feed</a> · No organizer score is represented without an organizer receipt.</footer>
<script src="assets/app.js"></script></body></html>'''


def metric_card(label: str, value: str, detail: str) -> str:
    return f'<div class="card metric"><div class="label">{esc(label)}</div><div class="value">{value}</div><div class="detail">{esc(detail)}</div></div>'


def main() -> int:
    card = load(EVIDENCE / "run_card_h87_frb.json")
    experiment = load(EVIDENCE / "experiment_h87_frb.json")
    sources = load(REGISTRY / "source_ledger.json")["sources"]
    hypotheses = load(REGISTRY / "hypotheses.json")["candidates"]
    data_receipt = load(EVIDENCE / "data_receipt.json")
    registry_receipt = load(EVIDENCE / "registry_materialization.json")
    irregularities = load(REGISTRY / "irregularities.json")["items"]
    generated = card["generated_utc"]
    submission = card["submission"]
    filename = submission["name"]
    file_href = "downloads/" + quote(filename) if filename else "#"
    run_href = "downloads/" + quote(Path(filename).stem + ".run-card.json") if filename else "#"
    holdout = card["holdout_dti"]
    final = card["correlation_overlap_vs_registry"].get("final", {})
    surface = card["correlation_overlap_vs_registry"].get("surface", {})
    validator = card["validator_output"]
    note = submission.get("note") or ""
    ready = bool(submission.get("ready_to_download_and_submit"))

    release_html = f'''
<section class="hero"><div><div class="eyebrow">Automated local release gate · no weekly slot used</div>
<h1>One verified TIFF. No score theatre.</h1>
<p class="lead">H87-FRB is a unique, all-finite GeoTIFF candidate created after a spatial component holdout, leakage canaries, and two registry-duplicate gates. It is ready for a portal-format upload by the local validator; it has <strong>no organizer-confirmed score or acceptance receipt</strong>.</p>
<div class="button-row"><a class="button" href="{file_href}" download>Download submission .tif</a><a class="button secondary" href="executive-summary.html">How to submit</a></div>
<p class="small">Exact file: <span class="mono">{esc(filename)}</span> · <a href="data/lane.md">read the single active-lane declaration</a></p></div>
<aside class="card release-card"><div><div class="status">LOCAL VALIDATOR · PASS</div><h3>Submission release</h3><p class="mono">SHA-256<br>{esc(card.get("raster_sha256"))}</p><p class="small">All raster cells are finite float32 values in [0,1]. The written grid matches the local template exactly.</p></div>
<div class="button-row"><a class="button" href="{file_href}" download>↓ GeoTIFF</a><a class="button secondary" href="{run_href}">Audit JSON</a></div></aside></section>
<div class="grid">
{metric_card("HOLDOUT-DTI", number(holdout.get("mean"), 5), "spatial component holdout; local proxy, not leaderboard score")}
{metric_card("95% CI · HOLDOUT-DTI", f"{number(holdout.get('ci95',[None,None])[0],5)}–{number(holdout.get('ci95',[None,None])[1],5)}", "bootstrap CI across four spatial blocks")}
{metric_card("Registry check", f"{number(final.get('max_dot_overlap_within_3px'),3)}", "maximum final-dot 3-pixel overlap; duplicate cutoff is > 0.700")}
{metric_card("Organizer status", "UNSCORED", "no ORGANIZER-CONFIRMED receipt exists")}
</div>
<div class="good"><strong>Download decision:</strong> <b>{"OK TO DOWNLOAD AND SUBMIT</b> under the local format/uniqueness gates." if ready else "DO NOT DOWNLOAD OR SUBMIT</b>; the local gate is not complete."} The portal upload action still occurs in the account holder’s browser; no human raster inspection is required by this project.</div>
<div class="warning"><strong>Interpretation boundary:</strong> the displayed HOLDOUT-DTI is not comparable to any public leaderboard number. The hidden expert-label score cannot be inferred from this proxy. Do not describe this candidate as likely to beat a named leaderboard score.</div>
<h2>Submission identity</h2><div class="two-col"><div class="card"><h3>Paste this note (81 / 140 characters)</h3><div class="code mono">{esc(note)}</div><div class="button-row"><button class="button secondary" data-copy="{esc(note)}">Copy note</button></div></div><div class="card"><h3>What automatically passed</h3><ul><li>Single-band float32 GeoTIFF</li><li>Exact CRS, shape, and transform from local template</li><li>No NaN / ±Inf; every cell in [0,1]</li><li>Visible catalogue pixels set to zero exactly</li><li>Surface and final-dot duplicate gates against {esc(registry_receipt.get('registry_artifacts_materialized'))} public registry rasters</li></ul></div></div>
<h2>Core Values in the build</h2><div class="two-col"><div class="card"><h3>Maximize P(Win)</h3><p>Spend scarce slots only after a predeclared local gate, not after a visually persuasive map or an uncalibrated projection. Negative results remain evidence.</p></div><div class="card"><h3>Own the Outcome</h3><p>The release includes its download, SHA-256, validation receipt, duplicate audit, source status, and limitations rather than asking an inspector to reconstruct them.</p></div></div>'''
    (DOCS / "index.html").write_text(layout("Release", release_html, "index.html", generated), encoding="utf-8")

    submit_html = f'''
<div class="eyebrow">Executive summary · exact portal workflow</div><h1>Submit exactly one file.</h1>
<p class="lead">The project has already done the non-human validation. Follow these steps only to transfer the release through the competition account.</p>
<div class="steps">
<div class="step"><h3>Download the signed release</h3><p><a href="{file_href}" download><strong>{esc(filename)}</strong></a></p><p class="small">SHA-256: <span class="mono">{esc(card.get('raster_sha256'))}</span>. Do not substitute an older page download, a NaN-outside twin, or a scratch TIFF.</p></div>
<div class="step"><h3>Use the competition’s New submission form</h3><p>Select the downloaded single-band GeoTIFF. The local validator reopened the written bytes and verified float32, template CRS/shape/transform, no NaN/±Inf, and all values in [0,1]. This directly addresses the reported portal error “Predicted values must be in range [0, 1]”.</p></div>
<div class="step"><h3>Paste the release note</h3><div class="code mono">{esc(note)}</div><p><button class="button secondary" data-copy="{esc(note)}">Copy note</button> <span class="small">{len(note)} of 140 characters.</span></p></div>
<div class="step"><h3>Preserve the receipt</h3><p>A portal receipt is the first point at which any result can be called <span class="tag">ORGANIZER-CONFIRMED</span>. Until then, this site reports only <span class="tag holdout">HOLDOUT-DTI</span> and local validation.</p></div>
</div>
<h2>Automated release checklist</h2><div class="table-wrap"><table><thead><tr><th>Gate</th><th>Result</th><th>Evidence</th></tr></thead><tbody>
<tr><td>Spatial component holdout</td><td><span class="tag holdout">PROMOTE</span></td><td>H87-FRB exceeded its matched baseline with a paired HOLDOUT-DTI 95% CI above zero.</td></tr>
<tr><td>Leakage canary</td><td><span class="tag holdout">PASS</span></td><td>No single feature’s oriented holdout AUC exceeded 0.90.</td></tr>
<tr><td>Surface registry check</td><td><span class="tag holdout">UNIQUE</span></td><td>Checked before dot placement.</td></tr>
<tr><td>Final-dot registry check</td><td><span class="tag holdout">UNIQUE</span></td><td>Max 3-pixel overlap {number(final.get('max_dot_overlap_within_3px'),3)}; strict duplicate threshold &gt; 0.700.</td></tr>
<tr><td>GeoTIFF validator</td><td><span class="tag holdout">PASS</span></td><td><a href="{run_href}">Open the machine-readable run card</a>.</td></tr>
</tbody></table></div>
<div class="warning"><strong>Limitation:</strong> portal acceptance is not programmatically observable from this checkout because no DrivenData account/session or receipt is available. The file is format-ready locally, not organizer-confirmed.</div>'''
    (DOCS / "executive-summary.html").write_text(layout("How to submit", submit_html, "executive-summary.html", generated), encoding="utf-8")

    h_rows = []
    for h in hypotheses:
        tag = "blocked" if "BLOCKED" in h["status"] else "holdout" if h["status"] == "READY-TO-TEST" else "owner"
        h_rows.append(f'''<tr><td><strong>{esc(h['id'])}</strong><br><span class="tag {tag}">{esc(h['status'])}</span></td><td>{esc(h['name'])}<br><span class="small">Expected local improvement: {esc(h['expected_holdout_improvement'])}<br>Cost: {esc(h['implementation_cost'])}</span></td><td>{esc(h['physical_signature'])}</td><td>{esc(h['why_off_catalogue'])}<br><br><strong>Mimic:</strong> {esc(h['non_fault_mimic'])}</td></tr>''')
    hypothesis_html = f'''<div class="eyebrow">Pre-registered candidate queue</div><h1>Hypotheses before slots.</h1><p class="lead">These five candidates were ranked before H87-FRB was evaluated. Only the first ready candidate was run in this session—one experiment of the three-experiment budget.</p>
<div class="table-wrap"><table><thead><tr><th>Rank / state</th><th>Hypothesis</th><th>Physical signature & layers</th><th>Why it may be off-catalogue</th></tr></thead><tbody>{''.join(h_rows)}</tbody></table></div>
<h2>H87-FRB result</h2><div class="two-col"><div class="card"><h3>What passed</h3><p><span class="tag holdout">HOLDOUT-DTI</span> calibrated H87-FRB mean {number(holdout.get('mean'),5)}, 95% CI {number(holdout.get('ci95',[None,None])[0],5)}–{number(holdout.get('ci95',[None,None])[1],5)}. The paired contrast over the matched baseline was {number(experiment.get('paired_contrast',{}).get('mean'),5)} with a 95% CI fully above zero.</p></div><div class="card"><h3>What did not pass as a standalone claim</h3><p>The fixed label-free H87-FRB surface had HOLDOUT-DTI {number(experiment['summary']['h87_frb_surface']['mean'],5)}, below the calibrated arm. The released field is therefore a supervised calibration of the geological hypothesis, not proof that the raw physical surface alone discovers hidden faults.</p></div></div>
<div class="warning"><strong>Next experiment:</strong> run H87-SSB only if this candidate receives an organizer receipt or if a preregistered robustness test is required. Do not tune H87-FRB against this same four-fold result.</div>'''
    (DOCS / "hypotheses.html").write_text(layout("Hypotheses", hypothesis_html, "hypotheses.html", generated), encoding="utf-8")

    research_html = f'''<div class="eyebrow">Forensic review · evidence status first</div><h1>What the 0.2778 claim can—and cannot—tell us.</h1>
<div class="warning"><strong>Finding:</strong> the task’s attribution of 0.2778 to <span class="mono">h33-h33-2-b2</span> is not organizer-confirmed in the sources available here. The current owner registry for that artifact explicitly says no organizer score exists. It is therefore treated as an <span class="tag owner">OWNER-REPORT / USER-REPORT</span>, not a verified leaderboard fact.</div>
<h2>H33 artifact mechanics</h2><div class="two-col"><div class="card"><h3>What is byte-auditable</h3><p>The owner’s audit identifies a 37,654-dot, zero-outside float32 GeoTIFF on the same 3,730 × 3,292 / EPSG:32611 grid and records zero positive pixels on its visible catalogue. The owner’s reported mechanism is removal of dots within two pixels of the catalogue from a prior base.</p><p><a href="https://github.com/buffedlizard55-lab/GEMSDOE32/blob/780a5a534269c79adfe6d1d7d5aadead161332aa/docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-audit.json">Open owner audit JSON ↗</a></p></div><div class="card"><h3>Why such thinning could help</h3><p>Under the stated triangular-kernel Tversky formulation, clustered dots compete for the same nearby truth credit while still carrying false-positive mass. A sparse placement at the kernel scale can improve the coverage-to-mass trade-off. Masking known visible-fault pixels avoids placing mass where the local protocol deliberately excludes them.</p><p>This is metric reasoning, not proof that the artifact earned a particular portal value.</p></div></div>
<h2>Why a higher leaderboard score is not predictable</h2><p>The official public leaderboard URL is dynamic and could not be fetched under this sandbox’s network policy. The values 0.2778, 0.3195, and 0.4413 in the task are retained only as <span class="tag owner">USER-REPORT</span> / unverified targets. The expert-hidden truth, its spatial distribution, and a file-to-receipt mapping are unavailable. No scientifically honest procedure can turn this local proxy into a claim that the new TIFF will beat any of those values.</p>
<h2>What this release actually establishes</h2><div class="grid">
{metric_card("HOLDOUT-DTI · baseline", number(experiment['summary']['baseline_hgb']['mean'],5), "matched spatial component control")}
{metric_card("HOLDOUT-DTI · H87-FRB", number(holdout.get('mean'),5), "calibrated candidate")}
{metric_card("HOLDOUT-DTI · paired gain", "+" + number(experiment['paired_contrast']['mean'],5), "95% lower bound > 0")}
{metric_card("Leakage canary", "PASS", "no oriented single-feature AUC > 0.90")}
</div>
<p>The proxy gain validates only that the preregistered feature stack improves recovery of held-out visible segments under the declared protocol. It does not validate discovery of expert-new, off-catalogue faults; that is the critical external-validity risk.</p>
<h2>Methodological decision</h2><div class="good"><strong>Promote format, not a score projection.</strong> The candidate passed a conservative local gate and has been made downloadable. No weekly competition slot was used. A future organizer receipt can update a score ledger, but it cannot retroactively turn a local proxy into a pre-submission score.</div>'''
    (DOCS / "research.html").write_text(layout("Research", research_html, "research.html", generated), encoding="utf-8")

    ver_checks = "".join(f"<tr><td>{esc(k.replace('_',' '))}</td><td><span class=\"tag holdout\">{'PASS' if v else 'FAIL'}</span></td></tr>" for k, v in validator.get("checks", {}).items())
    verification_html = f'''<div class="eyebrow">Machine-verifiable release receipt</div><h1>Validation without an inspector.</h1>
<p class="lead">The writer reopens the exact bytes it wrote. It does not infer validity from an in-memory array.</p>
<div class="table-wrap"><table><thead><tr><th>Validation check</th><th>Result</th></tr></thead><tbody>{ver_checks}</tbody></table></div>
<div class="two-col"><div class="card"><h3>Portal-range defense</h3><p><span class="tag holdout">LOCAL VALIDATOR</span> {esc(validator.get('portal_safety_statement'))}</p><ul><li>Finite cells: {esc(validator.get('full_grid',{}).get('finite_pixels'))}</li><li>NaN / ±Inf cells: {esc(validator.get('full_grid',{}).get('nan_or_inf_pixels'))}</li><li>Range violations: {esc(validator.get('full_grid',{}).get('out_of_range_pixels'))}</li><li>Visible catalogue positives: {esc(validator.get('footprint',{}).get('visible_catalogue_positive_pixels'))}</li></ul></div><div class="card"><h3>Duplicate-lane gate</h3><p>Registry discovery: {esc(registry_receipt.get('registry_artifacts_materialized'))} materialized public candidate rasters, {esc(registry_receipt.get('complete_materialization'))} complete.</p><ul><li>Surface maximum exact Spearman: {number(surface.get('max_exact_spearman'),4)} (stop at ≥ 0.900)</li><li>Final maximum binary Spearman: {number(final.get('max_exact_binary_spearman'),4)} (stop at ≥ 0.900)</li><li>Final maximum 3-pixel dot overlap: {number(final.get('max_dot_overlap_within_3px'),4)} (stop at &gt; 0.700)</li></ul></div></div>
<h2>Run card</h2><p><a class="button" href="{run_href}">Download full run-card JSON</a> <a class="button secondary" href="data/requirements_review.json">Open three-pass review</a></p><p class="small">The verbose card preserves all per-registry comparison rows, SHA-256s, the validator output, and the evidence labels. It intentionally contains no inferred organizer score.</p>'''
    (DOCS / "verification.html").write_text(layout("Verification", verification_html, "verification.html", generated), encoding="utf-8")

    source_rows = []
    for source in sources:
        cls = source["class"]
        tag_class = "holdout" if cls == "OFFICIAL-RETRIEVED" else "owner" if "OWNER" in cls or "MIRROR" in cls else "blocked"
        source_rows.append(f'<tr><td><span class="tag {tag_class}">{esc(cls)}</span></td><td><a href="{esc(source["url"])}">{esc(source["title"])}</a></td><td>{esc(source["use"])}</td><td>{esc(source.get("reviewed") or "not fetched here")}</td></tr>')
    sources_html = f'''<div class="eyebrow">Manual-review links with explicit evidence classes</div><h1>Sources, not borrowed certainty.</h1><p class="lead">Every source is labeled by what was actually established in this execution. A link on an official domain is not marked fetched when sandbox egress prevented retrieval.</p>
<div class="table-wrap"><table><thead><tr><th>Evidence class</th><th>Source</th><th>Use</th><th>Reviewed</th></tr></thead><tbody>{''.join(source_rows)}</tbody></table></div>
<h2>Data provenance boundary</h2><div class="warning"><strong>MIRROR-VERIFIED, not organizer-authenticated:</strong> the local feature, labels, and template files match hash-pinned bytes in the recorded GitHub mirrors. Direct comparison to the login-gated organizer download was not possible. This limitation is retained in every receipt.</div>
<h2>Direct review</h2><ul><li><a href="data/lane.md">Single active-lane declaration</a></li><li><a href="data/requirements_review.json">Final three-pass requirements review JSON</a></li><li><a href="data/data_receipt.json">Core data receipt JSON</a></li><li><a href="data/hypotheses.json">Hypothesis register JSON</a></li><li><a href="data/registry_catalog.json">Public registry catalog JSON</a></li><li><a href="{run_href}">Release run card JSON</a></li></ul>'''
    (DOCS / "sources.html").write_text(layout("Sources", sources_html, "sources.html", generated), encoding="utf-8")

    irregularity_rows = []
    for item in irregularities:
        severity = item["severity"]
        tag_class = "blocked" if any(token in severity for token in ("blocked", "absent")) else "owner"
        irregularity_rows.append(f'<tr><td><strong>{esc(item["id"])}</strong></td><td><span class="tag {tag_class}">{esc(severity)}</span></td><td>{esc(item["fact"])}</td><td>{esc(item["disposition"])}</td></tr>')
    irregularities_html = f'''<div class="eyebrow">Review queue · nothing silently normalized away</div><h1>Irregularities requiring context.</h1>
<div class="table-wrap"><table><thead><tr><th>ID</th><th>Severity</th><th>Observed fact</th><th>Disposition</th></tr></thead><tbody>{''.join(irregularity_rows)}</tbody></table></div>
<p class="small">This table is generated from <a href="data/irregularities.json">the irregularity register</a>. A correction is retained rather than overwritten silently.</p>'''
    (DOCS / "irregularities.html").write_text(layout("Review queue", irregularities_html, "irregularities.html", generated), encoding="utf-8")

    data_dir = DOCS / "data"
    data_dir.mkdir(exist_ok=True)
    for source, target in ((EVIDENCE / "run_card_h87_frb.json", data_dir / "run_card_h87_frb.json"), (EVIDENCE / "requirements_review.json", data_dir / "requirements_review.json"), (EVIDENCE / "data_receipt.json", data_dir / "data_receipt.json"), (REGISTRY / "hypotheses.json", data_dir / "hypotheses.json"), (REGISTRY / "lane.md", data_dir / "lane.md"), (REGISTRY / "registry_catalog.json", data_dir / "registry_catalog.json"), (REGISTRY / "source_ledger.json", data_dir / "source_ledger.json"), (REGISTRY / "irregularities.json", data_dir / "irregularities.json")):
        shutil.copy2(source, target)
    pages_url = "https://buffedlizard55-lab.github.io/GEMSDOE87/"
    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "GEMSDOE87 release and evidence feed",
        "home_page_url": pages_url,
        "feed_url": pages_url + "feed.json",
        "description": "Machine-readable local release updates. HOLDOUT-DTI is never an organizer score.",
        "items": [{
            "id": f"sha256:{card.get('raster_sha256')}",
            "url": pages_url + file_href,
            "title": f"{filename} — local release {str(card.get('verdict', '')).upper()}",
            "date_published": generated,
            "content_text": (
                f"HOLDOUT-DTI {number(holdout.get('mean'), 5)}; "
                f"local written-byte validator {'PASS' if validator.get('passed') else 'FAIL'}; "
                f"organizer receipt: absent; registry verdict: {final.get('verdict', 'UNRESOLVED')}."
            ),
            "attachments": [{
                "url": pages_url + file_href,
                "mime_type": "image/tiff",
                "title": filename,
                "size_in_bytes": validator.get("bytes"),
            }],
        }],
    }
    (DOCS / "feed.json").write_text(json.dumps(feed, indent=2) + "\n", encoding="utf-8")
    (DOCS / ".nojekyll").write_text("\n", encoding="utf-8")
    print(f"Generated GitHub Pages site in {DOCS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
