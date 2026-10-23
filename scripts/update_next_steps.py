#!/usr/bin/env python3
"""Deterministic read-only suggestions from recorded gates and source health.

No hypothesis fitting, model execution, parameter changes, slot selection or
submission. A changing public web page cannot override the frozen negative.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def derive(card, feed):
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
            'The source correction has synthetic regression coverage only; original negative data, hash and measurements are retained.',
            'A corrected scientific measurement requires a new authorized run, not an automatic retry.')
    if card['verdict'] == 'negative':
        add('preserve-weekly-slot',
            f"Do not spend a weekly competition slot on {card.get('submission_name', 'this artifact')}.",
            'The improvement gate did not clear and a byte-fresh TIFF is not a uniqueness or submission authorization.',
            'Read-only recommendation; no selector or upload operation exists in this updater.')
    failures = sum(not row.get('transport_ok', False) for row in feed.get('checks', []))
    if failures:
        add('source-retry', 'Retry official-source transport on the next scheduled refresh; preserve dated observations.',
            f'{failures} source transport checks failed or required login. Reachability never verifies a geological claim.',
            'Public source-health checks only; no credentials, no authenticated account-state inference.')
    if card.get('current_weekly_cap_from_submission_page') is None:
        add('account-receipt', 'Require an authenticated current cap/usage receipt before any future selector authorization.',
            'A rules PDF or public leaderboard does not identify account-specific remaining slots or this artifact\'s acceptance.',
            'No real slot selected or consumed in this project.')
    add('physical-research-queue', 'Retain untested hypotheses as a future research queue, not tested winners.',
        'Fault-specific signatures and named non-fault mimics are documented; no new external dataset or improved result is invented.',
        'Do not spend a weekly slot on a negative holdout. Exact layer definitions and official provenance must be checked first.')
    return dict(schema_version=1, generated_utc=datetime.now(timezone.utc).isoformat(),
                based_on_run=card['hypothesis'], raster_sha256=card['raster_sha256'],
                source_health_last_attempt_utc=feed.get('last_attempt_utc'),
                current_verdict=card['verdict'], safe_to_submit=card['safe_to_submit'],
                actions=actions, scientific_experiments_run_by_updater=0,
                submission_slots_used_by_updater=0,
                scope='Deterministic next steps from measured blockers and transport status; not semantic verification of new scientific knowledge.')


def main():
    card = json.loads((ROOT / 'docs/evidence/run_card.json').read_text())
    feed = json.loads((ROOT / 'docs/data/feed.json').read_text())
    result = derive(card, feed)
    (ROOT / 'docs/data/next_steps.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(f"Updated {len(result['actions'])} read-only suggestions; verdict and experiment budget unchanged.")


if __name__ == '__main__':
    main()
