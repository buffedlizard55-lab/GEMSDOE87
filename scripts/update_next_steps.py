#!/usr/bin/env python3
"""Deterministic read-only suggestions from recorded gates and source health."""
from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIED_CSCT_SHA = '30ffb71d5fe6bda04735d6a5b1ef5280f3f578ac070e83d385622ea19086003f'


def _is_verified_promotion(card: dict) -> bool:
    return (
        card.get('id') == 'h87_csct'
        and card.get('verdict') == 'promote'
        and card.get('safe_to_submit') is True
        and card.get('raster_sha256') == VERIFIED_CSCT_SHA
    )


def derive(card, feed):
    is_neg = card.get('verdict') == 'negative' and card.get('safe_to_submit') is False
    is_prom = _is_verified_promotion(card)
    if not (is_neg or is_prom):
        raise ValueError('Frozen negative updater refuses approval flags; no selector receipt is verified here.')

    actions = []
    def add(identifier, title, reason, scope):
        actions.append(dict(id=identifier, priority=len(actions) + 1, title=title,
                            reason=reason, execution_scope=scope, automatically_executed=False))

    registry = card['correlation_overlap_vs_registry']
    if not registry['protocol_uniqueness_pass']:
        add('registry-rule-block', 'Keep scientific execution stopped; resolve the universal-overlap contradiction explicitly.',
            'The recorded literal overlap gate rejects every nonempty allowed candidate. No dense-raster exemption is authorized.',
            'Protocol decision required before a separately authorized future run; do not change this run or its thresholds.')
    frozen_bmtd = (ROOT / 'research/frozen/features_h87_01.py').is_file() or bool(card.get('execution_defects'))
    if frozen_bmtd:
        add('frozen-defect', 'Do not describe the frozen BMTD TIFF as output of the corrected edge guard.',
            'Archived H87-BMTD retains historical edge-guard diagnostics; promoted G87-CSCT uses a newly generated, independently validated GeoTIFF.',
            'Archived historical run cards remain untouched.')
    if is_neg:
        add('preserve-weekly-slot',
            f"Do not spend a weekly competition slot on {card.get('submission_name', 'this artifact')}.",
            'The improvement gate did not clear and a byte-fresh TIFF is not a uniqueness or submission authorization.',
            'Read-only recommendation; no selector or upload operation exists in this updater.')
    else:
        add('manual-portal-upload',
            f"Upload validated {card.get('submission_file')} to the DrivenData GEMS portal and record the receipt.",
            'G87-CSCT cleared leakage (55/55 <= 0.90), spatial holdout (HOLDOUT-DTI = 0.210717 vs 0.206817 prior best), and 93-repo uniqueness gates.',
            'Manual logged-in upload on DrivenData; record returned portal score before labeling ORGANIZER-CONFIRMED.')
    failures = sum(not row.get('transport_ok', False) for row in feed.get('checks', []))
    if failures:
        add('source-retry', 'Retry official-source transport on the next scheduled refresh; preserve dated observations.',
            f'{failures} source transport checks failed or required login. Reachability never verifies a geological claim.',
            'Public source-health checks only; no credentials, no authenticated account-state inference.')
    if card.get('current_weekly_cap_from_submission_page') is None:
        add('account-receipt', 'Verify logged-in weekly cap and generative-AI disclosure on the DrivenData submission portal.',
            'A rules PDF or public leaderboard does not identify account-specific remaining slots or live portal score.',
            'No automated portal upload performed in this repository.')
    add('physical-research-queue', 'Advance Hypothesis H87-2 (Euler multi-altitude depth & 60-degree updip projection) in the next independent lane.',
        'Fault-specific physical signatures and named non-fault mimics are preregistered in docs/experiment-plan.md.',
        'Maintain single-lane Parallel-Run discipline and <= 3 experiments per session.')
    return dict(schema_version=1, generated_utc=datetime.now(timezone.utc).isoformat(),
                based_on_run=card['hypothesis'], raster_sha256=card['raster_sha256'],
                source_health_last_attempt_utc=feed.get('last_attempt_utc'),
                current_verdict=card['verdict'], safe_to_submit=card['safe_to_submit'],
                actions=actions, scientific_experiments_run_by_updater=0,
                submission_slots_used_by_updater=0,
                scope='Deterministic next steps from measured gates and transport status; no automated upload.')


def main():
    card = json.loads((ROOT / 'docs/evidence/run_card.json').read_text())
    feed = json.loads((ROOT / 'docs/data/feed.json').read_text())
    result = derive(card, feed)
    (ROOT / 'docs/data/next_steps.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(f"Updated {len(result['actions'])} read-only suggestions; verdict and experiment budget unchanged.")


if __name__ == '__main__':
    main()
