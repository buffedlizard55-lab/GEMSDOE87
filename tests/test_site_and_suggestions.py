import copy
import hashlib
import json
from pathlib import Path
import pytest

from scripts import build_site, check_site, update_next_steps

ROOT = Path(__file__).resolve().parents[1]


def test_all_local_site_links_headings_and_decision_wording():
    report = check_site.audit()
    assert report['passed'], report['errors']
    assert report['pages'] == 8
    assert report['local_links_verified'] >= 100


def test_experiment_index_lists_every_run_card_accurately():
    rows, notes = build_site._experiment_rows()
    assert notes == []
    archived = {p.parent.name for p in (ROOT / 'evidence').glob('*/run_card.json')}
    assert archived, 'expected archived run cards'
    assert 'h87_csct' in archived
    assert len(rows) == len(archived)
    html = (ROOT / 'docs/experiments.html').read_text()
    for name in archived:
        assert f'id="exp-{name}"' in html, name
        assert (ROOT / 'docs/evidence' / f'{name}_run_card.json').is_file(), name
    assert 'research-only' in html
    assert 'Approved for a weekly slot' in html


def test_markdown_tables_scroll_without_extra_main_headings():
    result = build_site.render_markdown('# Heading\n\n| A | B |\n|---|---|\n| one | two |\n')
    assert '<h1' not in result
    assert '<h2 id="heading">' in result
    assert '<div class="table-wrap"><table>' in result
    assert '</table></div>' in result


def observation(value=.4413):
    return dict(value=value, source_url='https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/',
                observed_utc='2026-10-22', evidence_class='PUBLIC-LEADERBOARD-OBSERVATION',
                artifact_submission_receipt=False)


def test_static_public_observation_comes_from_feed_not_hardcoded_fallback():
    assert build_site.public_leader_snapshot({'public_leaderboard_observation': observation(.4567)}) == ('0.4567', '2026-10-22')
    assert build_site.public_leader_snapshot({})[0] == 'unavailable'
    bad = observation()
    bad['artifact_submission_receipt'] = True
    assert build_site.public_leader_snapshot({'public_leaderboard_observation': bad})[0] == 'unavailable'
    bad = observation(1.2)
    assert build_site.public_leader_snapshot({'public_leaderboard_observation': bad})[0] == 'unavailable'


def test_read_only_suggestions_never_mutate_science_or_budget():
    card = json.loads((ROOT / 'run_card.json').read_text())
    before = copy.deepcopy(card)
    feed = dict(checks=[dict(transport_ok=False)], last_attempt_utc='2026-10-22')
    result = update_next_steps.derive(card, feed)
    assert card == before
    assert result['current_verdict'] == 'promote'
    assert result['safe_to_submit'] is True
    assert result['scientific_experiments_run_by_updater'] == 0
    assert result['submission_slots_used_by_updater'] == 0
    ids = {row['id'] for row in result['actions']}
    assert {'manual-portal-upload', 'source-retry'} <= ids
    assert all(row['automatically_executed'] is False for row in result['actions'])


def test_no_failed_source_suggestion_when_all_transport_reachable():
    card = json.loads((ROOT / 'run_card.json').read_text())
    result = update_next_steps.derive(card, dict(checks=[dict(transport_ok=True)]))
    ids = {row['id'] for row in result['actions']}
    assert 'source-retry' not in ids
    assert 'manual-portal-upload' in ids


def test_validated_readiness_exposed_in_download_and_submission_guide():
    for filename in ('index.html', 'executive-summary.html'):
        html = (ROOT / 'docs' / filename).read_text()
        assert 'validated' in html.lower()
        assert 'outer-grid' in html
        assert 'download' in html.lower()
        assert 'http://localhost' not in html
        assert 'http://127.0.0.1' not in html


def test_concurrent_readiness_snapshots_preserve_exact_bytes():
    manifest = json.loads((ROOT / 'research/upstream_readiness/provenance.json').read_text())
    assert manifest['commit'].startswith('f4f5944')
    rows = manifest['files'] + [row for update in manifest.get('updates', []) for row in update['files']]
    for row in rows:
        assert hashlib.sha256((ROOT / row['archive']).read_bytes()).hexdigest() == row['sha256']


def test_refreshed_pages_deploys_after_legacy_build_and_checks_public_feed():
    workflow = (ROOT / '.github/workflows/pages.yml').read_text()
    assert '  workflow_run:' in workflow and 'workflows: [pages-build-deployment]' in workflow
    assert 'types: [completed]' in workflow and '\n  push:' not in workflow
    assert '.cache/published-feed.json' in workflow and 'feed_last_attempt_utc' in workflow


def test_next_steps_refuses_tampered_approval_flags():
    neg = json.loads((ROOT / 'evidence/h87gcf/run_card.json').read_text())
    for patch in ({'safe_to_submit': True}, {'verdict': 'promote'},
                  {'safe_to_submit': None}, {'verdict': None}):
        card = copy.deepcopy(neg)
        card.update(patch)
        before = copy.deepcopy(card)
        with pytest.raises(ValueError, match='refuses approval flags'):
            update_next_steps.derive(card, {})
        assert card == before


def test_ci_push_checks_include_all_fixed_session_branches():
    for name in ('ci.yml', 'tests.yml'):
        workflow = (ROOT / '.github/workflows' / name).read_text()
        assert "'arena/**'" in workflow
        assert 'arena/e6d76d5c-gemsdoe87' not in workflow
