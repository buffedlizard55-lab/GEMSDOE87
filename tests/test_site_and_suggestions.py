import copy
import json
from pathlib import Path

from scripts import build_site, check_site, update_next_steps

ROOT = Path(__file__).resolve().parents[1]


def test_all_local_site_links_headings_and_no_go_wording():
    report = check_site.audit()
    assert report['passed'], report['errors']
    assert report['pages'] == 7
    assert report['local_links_verified'] >= 100


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
    assert result['current_verdict'] == 'negative'
    assert result['safe_to_submit'] is False
    assert result['scientific_experiments_run_by_updater'] == 0
    assert result['submission_slots_used_by_updater'] == 0
    ids = {row['id'] for row in result['actions']}
    assert {'registry-rule-block', 'frozen-defect', 'preserve-weekly-slot', 'source-retry'} <= ids
    assert all(row['automatically_executed'] is False for row in result['actions'])


def test_no_failed_source_suggestion_when_all_transport_reachable():
    card = json.loads((ROOT / 'run_card.json').read_text())
    result = update_next_steps.derive(card, dict(checks=[dict(transport_ok=True)]))
    ids = {row['id'] for row in result['actions']}
    assert 'source-retry' not in ids
    assert 'preserve-weekly-slot' in ids  # public connectivity cannot clear science


def test_duplicate_stop_is_exposed_in_download_and_submission_guide():
    for filename in ('index.html', 'executive-summary.html'):
        html = (ROOT / 'docs' / filename).read_text()
        assert 'do not submit' in html.lower()
        assert 'outer-grid' in html
        assert 'download' in html
        assert 'http://localhost' not in html
        assert 'http://127.0.0.1' not in html


def test_concurrent_readiness_snapshots_preserve_exact_bytes():
    import hashlib
    manifest = json.loads((ROOT / 'research/upstream_readiness/provenance.json').read_text())
    assert manifest['commit'].startswith('f4f5944')
    for row in manifest['files']:
        assert hashlib.sha256((ROOT / row['archive']).read_bytes()).hexdigest() == row['sha256']
