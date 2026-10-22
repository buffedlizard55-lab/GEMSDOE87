# Three-pass implementation review

Scientific experimentation and software review are separate. H87-BMTD-01 stopped at the literal duplicate gate. Review did **not** run a corrected geophysical experiment, change the original measurements, authorize a selector or consume a competition slot.

## Pass 1 — implement and measure (completed)

- Initial checkout reviewed: only an 11-byte title README, not the assumed previous training pipeline. No prior-session queue or comparable local holdout best existed.
- Official specification, known-pixel masking clarification, rules, public leaderboard, USGS GeoDAWN, displacement literature, and GDR/INGENIOUS context retrieved. Fourteen bounded source/claim records are in `registry/sources.json`.
- All three required mirror rasters restored and SHA-256 checked; all 19 physical bands cached using unchanged inherited code. These are integrity-pinned mirrors, not authenticated organizer originals.
- Four geological hypotheses were recorded before implementing one RTP-only lane. No inherited prediction is a model input.
- Twenty-three shared modules, including evaluator, spatial split, metric, diagnostic emitter, uniqueness gate and writer, are reused byte-for-byte. The inherited physical-band builder is also unchanged.
- Eight individual scalar canaries per fold preceded trust in the fixed whole-component holdout. Pooled official-formula DTI and paired physical-cluster CIs did not establish improvement against the best magnetic control.
- Registry inventory, H33 ancestry forensics, malformed TIFF retention and the universal saturated-support overlap proof completed.
- Stopped before final submission dot placement. The already measured continuous negative surface was serialized, and its positive support was checked literally. No real slot or selector was used.
- The independently reopened TIFF and ZIP pass the conservative local format policy: float32, one band, EPSG:32611, exact sample grid, finite [0,1], no nodata tag, zero outside-footprint/catalogue mass, one matching ZIP member and valid CRC.

## Pass 2 — edge cases, correctness and source review (completed)

**Bugs were found, fixed, and disclosed, not hidden by the passing format check:**

1. **Original scientific defect IR87-016:** the missing-data guard omitted an explicit outer-array pad. The original surface has 101,560 positive pixels within 40 px of the outer boundary. Current feature source pads all four boundaries; synthetic texture/holes/constant-input regressions cover the fix. Exact original source is archived with its measured SHA-256. The old TIFF, original holdout and negative verdict remain unchanged. **There is no corrected geophysical measurement.**
2. The runner refuses the permanent stop before loading data; cached outputs are rejected if the feature implementation hash changed. A regression asserts that neither input loading nor the detector can be invoked through this stopped runner.
3. Restorer now rejects unknown/empty dataset IDs, bounds transport calls, and cleans failed multipart/partial artifacts. Executable download wrapper and root preparation compatibility entry were exercised; all three original data pins rechecked.
4. Public-leader parser requires an explicit rank/score table and one unambiguous leader. Failed streamed bodies reset reachability. HTTPS downgrade or changed leaderboard origin/path cannot create a new leaderboard observation. Dated public observations are retained on transport/parser failure and are never artifact receipts. Static HTML derives the observation from the feed instead of a hardcoded fallback.
5. Browser inspection found and fixed narrow-screen table overflow and an unbreakable heading at 320 px. Markdown evidence now uses bounded scroll containers and exactly one semantic page H1. Browser packages are locked and runtime libraries come from that same pinned package, not an unrecorded browser download.
6. Final request review removed a potential approval-flag trust path: this frozen-negative validator always refuses authorization, even if JSON booleans are edited to claim promotion or verified receipts. A dedicated regression supplies such a falsified card and confirms refusal. Reference mirror hashes are rechecked before footprint use, and idempotent packaging validates the retained bundle without rewriting it. No general-purpose selector authorization is claimed.
7. Repository metadata catalog and scientific scope wording distinguish filename hints, unverified historical references, measured H33 ancestry, byte freshness and actual literal uniqueness. No retrospective claim that all historical implementations/results were independently verified.

**Executed software checks:**

- **95 tests passed, zero failures/errors/skips**, covering exact DTI versus a literal brute-force oracle, max-not-sum coverage, 300 m cutoff, exact known-pixel masking, whole-component tails, physical crop/block alignment, paired pooled terms, deliberate AUC leakage, original source pins, fixed guard fixtures, literal overlap boundary/dense-prior behavior, invalid-file rejection, frozen TIFF/ZIP bytes, authorization refusal, restorer errors, feed parsing/network failures, static evidence and read-only suggestions.
- `compileall`, shell syntax, and root `prepare_data.py --help` passed.
- Format CLI exits **0**; normal authorization CLI exits the expected **2** with `safe_to_submit=false`.
- Offline site audit: **7 pages plus 4 compatibility entry points, 120 local targets/anchors checked**, no duplicate IDs, exactly one page H1, image alternative text, explicit research/no-go wording and no browser-facing localhost API.
- Real Chromium 153: **37 checks**, 1440/768/390/320 px, all seven pages, four established root-route redirects, actual browser TIFF download with exact SHA-256, repository-search zero/one-result states, clipboard success and unavailable fallback, failed-feed fallback, and download/decision without JavaScript. Screenshots were inspected locally; CI retains its own screenshots.
- Actual sandbox source-health attempt: **0/13 transport reachable**, recorded transparently. This does not negate the separate research-tool retrieval or invent current source freshness.

Receipts: [software](../docs/evidence/software_validation.json), [browser](../docs/evidence/browser_validation.json), [site](../docs/evidence/site_validation.json), [independent file](../docs/evidence/independent_validation.json). These are local/software receipts, **not organizer upload acceptance**. GitHub Actions repeats the software checks independently. The 21 earlier readiness/format/feed regressions are retained within the 95-case suite; their standalone workflow still runs them too.

## Pass 3 — original-request reconciliation (completed; outcome is negative)

The complete README brief was reread. The following is a requirement-to-evidence audit, not a claim that the contradictory scientific goal was achieved.

| Original requirement | Outcome / evidence |
|---|---|
| Preserve full prompt, core values and prior-session starting point | README archive and AGENTS retained; initial lack of prior pipeline/queue disclosed. Trailing whitespace only was normalized. |
| Quickly study previous approaches/results, especially H33 | 93 pinned trees and 812 claim references cataloged; H33-to-parent exact 2,545-pixel prune and metric mechanism established. **Partial:** no full editorial/code revalidation or authenticated historical results. |
| Generate/rank 3–5 hypotheses before implementation | Four recorded with exact layers, physical transform, uncatalogued-fault rationale, distinctness/cost and named mimics; one implemented. Expected benefit is qualitative, never a projected score. |
| Deep scientific research and official/free data sources | Fourteen claim-level source records; geophysical literature, licenses, acquisition mimics, rules and reference notebook reviewed. Only obtained stack bands are dependencies; no unacquired external dataset is passed off as ingested. |
| Correct target: faults, not vents/reservoir certification | Explicit throughout site/report; neither permeability nor economic heat is asserted. |
| Complete autonomous data placement and pipeline | Three hash-pinned inputs and 19-band cache prepared; downloader/preparer and shared writer/evaluator are functional. **Limit:** official authenticity unavailable; this is a deterministic CPU detector, not a trained U-Net. |
| Reuse shared tools; no private fork | Per-file template SHA-256 tests and runner checks; 23 modules and inherited cache builder unchanged. Own detector defect is corrected transparently. |
| Buffered whole-segment hide-and-recover, visible-only catalogue features, exact masking, pooled DTI | Shared whole 8-connected components, 80 px buffer, no catalogue-derived model features, exact visible masks, alpha .2/beta .8/300 m triangular support. Original edge defect remains disclosed. |
| Every individual feature leakage canary | Eight scalars per quadrant, largest two-sided HOLDOUT-AUC-CANARY .592483; low AUC is not claimed as proof of no leakage. |
| Correlation >.90 OR overlap >.70 against ANY prior: stop; no dense exception | Universal witness rejects every nonempty legal candidate. Surface and serialized research support both fail. **No final dots exist after the stop**, so no final-dot clearance is fabricated. |
| Stop at 3 experiments or 2 hours; separate selector | One fixed scientific experiment, zero after stop, zero selector calls/competition slots. Software tests are not further geophysical experiments. |
| Unique new TIFF; not a copied/renamed earlier raster | New computed bytes, hash distinct from all restored valid files. **Not achieved:** literal geometric uniqueness; negative is the permitted deliverable. |
| High scoring gates / beat current best before a slot | Strongest matched control not beaten; holdout is a catalogue proxy, not hidden new-fault truth. No inherited comparable best or organizer receipt. **Not promoted; no claimed leaderboard improvement.** |
| Prevent previous [0,1] portal error autonomously | Actual on-disk TIFF/ZIP validate locally and have no NaNs/sentinels/out-of-range cells. Original bad file absent; neither root cause nor portal acceptance is invented. |
| Obvious one-click download and submit status at site top | Research TIFF and one-TIFF ZIP in hero and executive summary; red DO NOT SUBMIT with independent receipts. |
| Unique identification and short note ≤140 chars | `GEMSDOE87-BMTD-01-NEGATIVE`; 126-character note, browser copy tested. |
| Exact executive-summary submission walkthrough | Future-cleared-file procedure only; current file expressly excluded. Actual cap and receipt required; no upload made. |
| Organized user-friendly Pages and auditable knowledge table | Seven responsive static pages, genuine raster-derived visualization, linked evidence and source ledger; accessible no-JS fallback. |
| Current feed and autonomous suggestions | Read-only official transport/leaderboard parser, stale/failure state, deterministic blocker-based suggestions and daily scheduled workflow. **Not** automatic scientific claim verification or a live hosted training service. Deployment success is checked separately. |
| Three review passes, improve correctness and reliability | This record, 95 regressions, 37 browser checks, CLI refusal, source provenance and explicit unfixed-at-measurement limitation. |
| Create PR and merge main if allowed | Publication uses only the fixed session branch. PR, required checks, merge and deployment are authoritative GitHub operations, not inferred from local tests; their live links/outcome are included in final delivery. |
| Finish with run card and honest remaining work | Root/public JSON card, negative verdict, hashes, representation-specific HOLDOUT-DTI/CIs, literal registry comparisons, validator, name/note, source defect and remaining blockers retained. |

## Publication and continuing work

CI is defined in `.github/workflows/ci.yml`. Pages/read-only source refresh is defined in `.github/workflows/pages.yml`, daily at 06:17 UTC and on main pushes. The workflow stages only the public site and compatible root entry points; it does not push main, modify this raster or run/authorize science. A successful deployment is not presumed from the YAML. The PR and Actions run provide externally verifiable publication receipts.

Concurrent main readiness work at `f4f5944` was integrated on this same fixed branch, with exact-byte snapshots and its code/tests preserved. Compatibility root status now distinguishes a research download from competition approval; historical documents are labeled as snapshots. No second scientific lane was executed. Pages settings write was denied to the integration; the already successful upload/deploy pattern is reused without changing those settings.

The original request is **not fully satisfied as a winning or protocol-cleared submission**. Literal universal overlap, lack of control improvement, the frozen experiment's edge defect, unauthenticated originals/cap/receipts, one malformed prior, and incomplete historical mechanism review remain explicit. A separately authorized next run must resolve the protocol contradiction before any new experiment; see the research queue. No user action or human inspector is required to repeat local software/file validation, but software cannot create hidden truth or organizer authorization.
