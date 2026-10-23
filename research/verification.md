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
4. Concurrent main added safe atomic report writing and alias refusal. These helpers are retained and reused in the frozen checker too: its output must be JSON, cannot overwrite an existing input/card, and cannot be a symbolic/hard-link alias. Tests assert rejection before any raster work and byte preservation.
5. Public-leader parser requires an explicit rank/score table and one unambiguous leader. Failed streamed bodies reset reachability. HTTPS downgrade or changed leaderboard origin/path cannot create a new leaderboard observation. Dated public observations are retained on transport/parser failure and are never artifact receipts. Static HTML derives the observation from the feed instead of a hardcoded fallback.
5. Browser inspection found and fixed narrow-screen table overflow and an unbreakable heading at 320 px. Markdown evidence now uses bounded scroll containers and exactly one semantic page H1. Browser packages are locked and runtime libraries come from that same pinned package, not an unrecorded browser download.
6. Final request review removed a potential approval-flag trust path: this frozen-negative validator always refuses authorization, even if JSON booleans are edited to claim promotion or verified receipts. A dedicated regression supplies such a falsified card and confirms refusal. Reference mirror hashes are rechecked before footprint use, and idempotent packaging validates the retained bundle without rewriting it. No general-purpose selector authorization is claimed.
7. Repository metadata catalog and scientific scope wording distinguish filename hints, unverified historical references, measured H33 ancestry, byte freshness and actual literal uniqueness. No retrospective claim that all historical implementations/results were independently verified.

**Executed software checks:**

- **103 tests passed, zero failures/errors/skips**, covering exact DTI versus a literal brute-force oracle, max-not-sum coverage, 300 m cutoff, exact known-pixel masking, whole-component tails, physical crop/block alignment, paired pooled terms, deliberate AUC leakage, original source pins, fixed guard fixtures, literal overlap boundary/dense-prior behavior, invalid-file rejection, frozen TIFF/ZIP bytes, authorization refusal, restorer errors, feed parsing/network failures, static evidence and read-only suggestions.
- `compileall`, shell syntax, and root `prepare_data.py --help` passed.
- Format CLI exits **0**; normal authorization CLI exits the expected **2** with `safe_to_submit=false`.
- Offline site audit: **7 pages plus 4 compatibility entry points, 120 local targets/anchors checked**, no duplicate IDs, exactly one page H1, image alternative text, explicit research/no-go wording and no browser-facing localhost API.
- Real Chromium 153: **37 checks**, 1440/768/390/320 px, all seven pages, four established root-route redirects, actual browser TIFF download with exact SHA-256, repository-search zero/one-result states, clipboard success and unavailable fallback, failed-feed fallback, and download/decision without JavaScript. Screenshots were inspected locally; CI retains its own screenshots.
- Actual sandbox source-health attempt: **0/13 transport reachable**, recorded transparently. This does not negate the separate research-tool retrieval or invent current source freshness.

Receipts: [software](../docs/evidence/software_validation.json), [browser](../docs/evidence/browser_validation.json), [site](../docs/evidence/site_validation.json), [independent file](../docs/evidence/independent_validation.json). These are local/software receipts, **not organizer upload acceptance**. GitHub Actions repeats the software checks independently. The 25 earlier readiness/format/feed regressions are retained within the 103-case suite; their standalone workflow still runs them too.

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
| Current feed and autonomous suggestions | Read-only official transport/leaderboard parser, stale/failure state, deterministic blocker-based suggestions and daily scheduled workflow, sequenced after the legacy Pages build on main updates. **Not** automatic scientific claim verification or a live hosted training service. Deployment success is checked separately. |
| Three review passes, improve correctness and reliability | This record, 103 regressions, 37 browser checks, CLI refusal, source provenance and explicit unfixed-at-measurement limitation. |
| Create PR and merge main if allowed | Publication uses only the fixed session branch. PR, required checks, merge and deployment are authoritative GitHub operations, not inferred from local tests; their live links/outcome are included in final delivery. |
| Finish with run card and honest remaining work | Root/public JSON card, negative verdict, hashes, representation-specific HOLDOUT-DTI/CIs, literal registry comparisons, validator, name/note, source defect and remaining blockers retained. |

## Publication and continuing work

CI is defined in `.github/workflows/ci.yml`. Pages/read-only source refresh is defined in `.github/workflows/pages.yml`, daily at 06:17 UTC after the legacy main Pages build completes. The workflow stages only the public site and compatible root entry points; it does not push main, modify this raster or run/authorize science. A successful deployment is not presumed from the YAML. The PR and Actions run provide externally verifiable publication receipts.

Concurrent main readiness work at `f4f5944` and hardening through `a7a7c77` was integrated on this same fixed branch, with exact-byte snapshots and its code/tests preserved. Compatibility root status now distinguishes a research download from competition approval; historical documents are labeled as snapshots. No second scientific lane was executed. Pages settings write was denied to the integration; the already successful upload/deploy pattern is reused without changing those settings.

The original request is **not fully satisfied as a winning or protocol-cleared submission**. Literal universal overlap, lack of control improvement, the frozen experiment's edge defect, unauthenticated originals/cap/receipts, one malformed prior, and incomplete historical mechanism review remain explicit. A separately authorized next run must resolve the protocol contradiction before any new experiment; see the research queue. No user action or human inspector is required to repeat local software/file validation, but software cannot create hidden truth or organizer authorization.

## Active-branch follow-up — 2026-10-23 (software only)

### Pass 1 — inspect and implement

Read the inherited brief, four-hypothesis queue, H33 analysis, stop certificate,
run card, shared-tool pins and publication pipeline. This checkout already has a
completed **negative**, unlike the historical empty-checkout descriptions above.
No new hypothesis was fitted and no scientific budget was reset.

Found that `build_site.py` previously checked only that a preflight JSON existed
before publishing hardcoded “format-valid” text. Added a publication integrity
gate **before any page writes**: require explicit passing preflight booleans,
matching encoded/decoded hashes in the card and receipt, current TIFF SHA-256,
and a ZIP containing exactly the same TIFF bytes. Reject unsafe paths and
symlink downloads. Stream hashes with Python's standard library so scheduled
Pages builds need no raw feature cache or raster dependencies. This binds the
existing raster inspection to the published bytes; it is not a replacement
validator, organizer authentication, or permission to submit.

Also made read-only next-step derivation reject edited approval flags, and
changed the scientific-check workflow push filter from a prior session's branch
to `arena/**`, so this and later fixed Arena branches receive checks.

### Pass 2 — adversarial regression and actual artifact inspection

- Restored the two small hash-pinned grid/catalogue mirrors through GitHub;
  original organizer authenticity remains unverified. The prior three-file
  restoration receipt is preserved as historical evidence, not overwritten by
  this narrower reinspection.
- **133 tests passed**, no skips; added 30 publication/approval regressions.
  Fixtures with altered TIFF bytes, equal-length wrong ZIP bytes, extra members,
  corrupt ZIPs, stale hashes, false/missing/nonboolean receipt flags and unsafe
  paths must fail. Confirmed failure occurs before page writes.
- Reopened the real research TIFF/ZIP: `check_submission.py --format-only`
  returned **0**; the authorization command returned **2**, with local format
  valid and submission refused. The TIFF hash, run card, holdout, shared modules
  and experiment budget are unchanged.
- Static audit passed: seven pages, four root redirects and 120 local links.
  Real Chromium passed all 37 existing checks, including actual download hash,
  four viewport widths, no-JavaScript use and failed-feed fallback.
- `compileall` and `git diff --check` passed. These are software checks, not DTI
  measurements. The browser receipt is dated to this recheck.

### Pass 3 — original-request reconciliation and next work

The full brief remains in README. The site still offers the original newly
computed **research** TIFF, not a new candidate from this review. No weekly slot
was used. A protocol-cleared submission is **not delivered**: the inherited
universal-overlap stop and failed improvement gate still apply. No leaderboard
improvement, complete cross-site scientific review or new official-source
verification is claimed. GitHub confirms the official reference repository is
accessible; non-GitHub official sites, Dropbox and organizer authentication
remain outside this sandbox's allowed outbound hosts/access.

Before a separately authorized future scientific run, resolve how continuous
registry surfaces should be represented in the dot-overlap protocol (without
silently exempting them in this stopped run), confirm layer definitions for the
queued hypotheses, restore the shared cache, and establish matched controls.
Reevaluate the corrected edge guard only in that future run. Keep any slot
selector separate and require authenticated current cap/usage. PR merge and CI
outcomes must be checked on GitHub, not inferred from these local results.

### Concurrent-main integration before merge

PR #12 merged while this review PR #13 was awaiting CI, causing conflicts in
the browser-receipt timestamp and the equivalent approval-flag guard. Integrated
`origin/main` on the fixed active branch, retained its corrupt-ZIP CLI refusal
and additional tests, and kept the same negative-only guard. Re-ran the combined
suite: **137 tests passed**, plus all **37 Chromium checks** and the static-site
audit. This synchronization changed no raster, holdout, budget or shared tool.

## Final active-branch audit — 2026-10-23 UTC

After integrating the current main publication-integrity gate, the final local run passed all 137 Python tests, 37 Chromium checks, the static audit, TIFF/ZIP format preflight, and fail-closed authorization check. The current TIFF and decision remain unchanged; this was not a new scientific run.

- [`validation-inputs-2026-10-23.json`](../docs/evidence/validation-inputs-2026-10-23.json) records the two small hash-pinned mirrors used for software checks. The older three-input `data/restore_receipt.json` remains historical; the full feature stack was not restored.
- The latest checked-in public source-health attempt remains `2026-10-22T22:33:20.895788Z`, with 0/13 official-source transports reachable. No fresh official-page retrieval, account-cap observation or organizer receipt is claimed.
- The site publication gate now verifies the current TIFF, exact ZIP member, card/receipt hashes, and fail-closed approval state **before page writes**. This protects the existing research download from stale/mutated bytes; it does not approve it for submission.
