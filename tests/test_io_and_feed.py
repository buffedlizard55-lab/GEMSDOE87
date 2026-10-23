import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock
import zipfile

import numpy as np
import pytest
import rasterio
from affine import Affine

from gems57 import submission_writer, gates
from scripts import check_submission, restore_data, update_feed

ROOT = Path(__file__).resolve().parents[1]


def write_small(path, data, *, dtype='float32', crs='EPSG:32611', nodata=None, count=1):
    with rasterio.open(path, 'w', driver='GTiff', count=count, width=data.shape[1], height=data.shape[0],
                       dtype=dtype, crs=crs, transform=Affine(100, 0, 0, 0, -100, 2000), nodata=nodata) as dst:
        for band in range(1, count + 1):
            dst.write(data.astype(dtype), band)


@pytest.mark.parametrize('bad', [np.nan, np.inf, -0.01, 1.01])
def test_independent_written_file_validator_rejects_bad_values(tmp_path, bad):
    p = np.zeros((10, 12), dtype='float32')
    p[2, 2] = bad
    file = tmp_path / 'invalid.tif'
    write_small(file, p)
    sample = tmp_path / 'sample.tif'
    write_small(sample, np.zeros_like(p))
    assert gates.format_report(file, sample)['ok'] is False


@pytest.mark.parametrize('kwargs', [dict(dtype='float64'), dict(crs='EPSG:4326'), dict(nodata=-9999), dict(count=2)])
def test_independent_validator_rejects_wrong_metadata(tmp_path, kwargs):
    file = tmp_path / 'invalid.tif'
    write_small(file, np.zeros((10, 12)), **kwargs)
    sample = tmp_path / 'sample.tif'
    write_small(sample, np.zeros((10, 12)))
    assert gates.format_report(file, sample)['ok'] is False


def test_shared_writer_never_silently_clips_or_fills(tmp_path):
    p = np.zeros((10, 12), dtype='float32')
    fp = np.ones(p.shape, bool)
    known = np.zeros(p.shape, bool)
    for bad in (np.nan, np.inf, -0.01, 1.01):
        p[0, 0] = bad
        with pytest.raises(ValueError, match='no silent repair'):
            submission_writer.write_submission(tmp_path / 'must-not-exist.tif', p, tmp_path / 'sample.tif', fp,
                                                 catalogue=known, name='fixture', note='Synthetic serialization unit test')
        assert not (tmp_path / 'must-not-exist.tif').exists()


@pytest.mark.parametrize('note', ['', 'x' * 141])
def test_shared_writer_enforces_note_limit(tmp_path, note):
    with pytest.raises(ValueError, match='note'):
        submission_writer.write_submission(tmp_path / 'no.tif', np.zeros((2, 2)), tmp_path / 'sample.tif', np.ones((2, 2), bool),
                                             name='fixture', note=note)


def test_shipped_tiff_and_zip_are_exact_and_in_range():
    card = json.loads((ROOT / 'run_card.json').read_text())
    file = ROOT / 'docs/downloads' / card['submission_file']
    with rasterio.open(file) as src:
        data = src.read(1)
        assert src.shape == (3730, 3292)
        assert src.count == 1 and src.dtypes == ('float32',)
        assert src.crs.to_epsg() == 32611
        assert list(src.transform)[:6] == [100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0]
    assert np.isfinite(data).all()
    assert data.min() >= 0 and data.max() <= 1
    assert hashlib.sha256(file.read_bytes()).hexdigest() == card['raster_sha256']
    assert np.count_nonzero(data > 0) == card['n_emitted_positive_pixels'] == 37654
    with zipfile.ZipFile(ROOT / 'docs/downloads' / card['submission_zip']) as z:
        assert z.namelist() == [file.name]
        with z.open(file.name) as src:
            h = hashlib.sha256()
            for block in iter(lambda: src.read(1 << 20), b''):
                h.update(block)
        assert h.hexdigest() == card['raster_sha256']


def test_negative_cannot_pass_submission_authorization():
    required = ['data/raw/sample_submission.tif', 'data/raw/existing_faults.tif']
    if not all((ROOT / p).is_file() for p in required):
        pytest.skip('Restore the two pinned validation inputs for this integration check')
    card = json.loads((ROOT / 'run_card.json').read_text())
    report = check_submission.check_bundle(card)
    assert report['local_format_valid'] is True
    assert report['safe_to_submit'] is False
    assert report['note_length'] <= 140


def test_editing_approval_booleans_cannot_authorize_a_frozen_negative():
    if not (ROOT / 'data/raw/sample_submission.tif').is_file():
        pytest.skip('Restore pinned validation inputs for the authorization integration check')
    card = json.loads((ROOT / 'run_card.json').read_text())
    card.update(safe_to_submit=True, verdict='promote', approved_for_weekly_slot=True,
                organizer_cap_receipt_verified=True, selector_authorization_verified=True)
    card['correlation_overlap_vs_registry']['protocol_uniqueness_pass'] = True
    result = check_submission.check_bundle(card)
    assert result['local_format_valid'] is True
    assert result['safe_to_submit'] is False
    assert result['approved_for_weekly_slot'] is False
    assert 'no promotion path' in result['authorization_scope']


def test_restore_is_hash_verified_and_idempotent(tmp_path, monkeypatch):
    blob = b'pinned synthetic data'
    entry = dict(id='fixture', dest='a.bin', repo='example/repo', ref='pinned', path='a', sha256=hashlib.sha256(blob).hexdigest())
    calls = []
    def fake_fetch(repo, ref, path, dest):
        calls.append(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
    monkeypatch.setattr(restore_data, 'fetch', fake_fetch)
    assert restore_data.restore_entry(entry, tmp_path)['status'] == 'restored'
    assert restore_data.restore_entry(entry, tmp_path)['status'] == 'present'
    assert calls == ['a']


def test_bad_restore_hash_is_not_installed(tmp_path, monkeypatch):
    entry = dict(id='fixture', dest='a.bin', repo='example/repo', ref='pinned', path='a', sha256='0' * 64)
    monkeypatch.setattr(restore_data, 'fetch', lambda repo, ref, path, dest: dest.write_bytes(b'wrong'))
    with pytest.raises(SystemExit, match='HASH MISMATCH'):
        restore_data.restore_entry(entry, tmp_path)
    assert not (tmp_path / 'a.bin').exists()


def test_failed_multipart_restore_removes_temporary_files(tmp_path, monkeypatch):
    entry = dict(id='fixture', dest='a.bin', repo='example/repo', ref='pinned', parts=['one', 'two'], sha256='0' * 64)
    def fake_fetch(repo, ref, path, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b'partial')
        if path == 'two':
            raise RuntimeError('transport failure')
    monkeypatch.setattr(restore_data, 'fetch', fake_fetch)
    with pytest.raises(RuntimeError):
        restore_data.restore_entry(entry, tmp_path)
    assert not (tmp_path / 'a.assembling').exists()
    assert not (tmp_path / 'a.bin').exists()
    assert not list((tmp_path / 'raw_parts').glob('*'))


def test_unknown_restore_ids_fail_instead_of_claiming_zero_success():
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/restore_data.py'), '--ids', 'not-a-real-dataset'], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'Unknown or empty manifest IDs' in result.stderr


def test_public_leader_parser_requires_rank_and_score_table():
    html = """<table><tr><th>Rank</th><th>Team</th><th>Score</th></tr>
    <tr><td>2</td><td>Other</td><td>0.3904</td></tr>
    <tr><td>1</td><td>Leader</td><td>0.4413</td></tr></table><footer>0.9999</footer>"""
    assert update_feed.parse_leaderboard(html) == .4413
    assert update_feed.parse_leaderboard('<p>Score 0.9999</p>') is None
    assert update_feed.parse_leaderboard('<table><tr><th>Team</th><th>Score</th></tr><tr><td>X</td><td>.99</td></tr></table>') is None
    assert update_feed.parse_leaderboard('<table><tr><td>1</td><td>0.9999</td></tr></table>') is None
    assert update_feed.parse_leaderboard(html + html) is None


def test_source_checker_blocks_unlisted_hosts():
    row, observation = update_feed.check(dict(id='fixture', url='https://attacker.invalid/data'))
    assert row['transport_ok'] is False
    assert observation is None
    assert row['status'] == 'blocked-unexpected-host'


def test_source_transport_failure_never_becomes_verified(monkeypatch):
    def fail(*args, **kwargs):
        raise update_feed.requests.RequestException('test offline')
    monkeypatch.setattr(update_feed.requests, 'get', fail)
    row, observation = update_feed.check(dict(id='leaderboard', url=update_feed.LEADERBOARD))
    assert row['transport_ok'] is False
    assert row['content_verified_by_health_check'] is False
    assert observation is None


def mock_response(url):
    response = MagicMock()
    response.__enter__.return_value = response
    response.url = url
    response.ok = True
    response.status_code = 200
    return response


def test_source_login_redirect_is_explicit(monkeypatch):
    response = mock_response('https://www.drivendata.org/accounts/login/?next=/data/')
    monkeypatch.setattr(update_feed.requests, 'get', lambda *a, **k: response)
    row, observation = update_feed.check(dict(id='data', url='https://www.drivendata.org/competitions/306/competition-doe-gems/data/'))
    assert row['transport_ok'] is False
    assert row['status'] == 'login-required'
    assert row['content_verified_by_health_check'] is False
    assert observation is None


def test_stream_failure_resets_reachability(monkeypatch):
    response = mock_response(update_feed.LEADERBOARD)
    response.iter_content.side_effect = update_feed.requests.RequestException('truncated body')
    monkeypatch.setattr(update_feed.requests, 'get', lambda *a, **k: response)
    row, observation = update_feed.check(dict(id='leaderboard', url=update_feed.LEADERBOARD))
    assert row['transport_ok'] is False
    assert row['status'] == 'transport-unavailable'
    assert observation is None


def test_tampered_reference_hash_rejected_before_raster_decode(tmp_path):
    download = tmp_path / 'docs/downloads'
    download.mkdir(parents=True)
    blob = b'synthetic container, deliberately not a TIFF'
    (download / 'fixture.tif').write_bytes(blob)
    (tmp_path / 'registry').mkdir()
    entries = [dict(id=k, dest=k + '.tif', sha256='0' * 64) for k in ('sample_submission', 'existing_faults')]
    (tmp_path / 'registry/data_manifest.json').write_text(json.dumps(dict(files=entries)))
    with pytest.raises(ValueError, match='Reference mirror hash mismatch'):
        check_submission.check_bundle(dict(submission_file='fixture.tif', submission_zip='fixture.zip',
                                           raster_sha256=hashlib.sha256(blob).hexdigest()), root=tmp_path)


def test_existing_negative_serializer_verifies_without_rewriting(monkeypatch):
    if not all((ROOT / 'data/raw' / f).is_file() for f in ('sample_submission.tif', 'existing_faults.tif')):
        pytest.skip('Restore the two pinned validation inputs for idempotent serializer check')
    from scripts import package_negative
    card = json.loads((ROOT / 'run_card.json').read_text())
    files = [ROOT / 'docs/downloads' / card[k] for k in ('submission_file', 'submission_zip')]
    files += [ROOT / 'run_card.json', ROOT / 'docs/evidence/run_card.json']
    stamps = [p.stat().st_mtime_ns for p in files]
    def forbidden(*args, **kwargs):
        pytest.fail('Idempotent serializer must not re-run candidate/registry science')
    monkeypatch.setattr(package_negative, 'compare_array_to_registry', forbidden)
    assert package_negative.main() == 0
    assert [p.stat().st_mtime_ns for p in files] == stamps


@pytest.mark.parametrize('url', [
    'http://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/',
    'https://github.com/example/leaderboard',
    'https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/',
])
def test_redirect_cannot_forge_a_leaderboard_observation(monkeypatch, url):
    response = mock_response(url)
    response.encoding = 'utf-8'
    response.iter_content.return_value = [b'<table><tr><th>Rank</th><th>Score</th></tr><tr><td>1</td><td>0.9999</td></tr></table>']
    monkeypatch.setattr(update_feed.requests, 'get', lambda *a, **k: response)
    row, observation = update_feed.check(dict(id='leaderboard', url=update_feed.LEADERBOARD))
    assert observation is None
    assert row['content_verified_by_health_check'] is False
    if url.startswith('http:'):
        assert row['transport_ok'] is False


@pytest.mark.parametrize('relative', ['run_card.json', 'docs/downloads/gems87-bmtd-20261022-50041440adba-RESEARCH-DO-NOT-SUBMIT.tif'])
def test_cli_report_cannot_overwrite_frozen_inputs(monkeypatch, relative):
    path = ROOT / relative
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    def forbidden(*args, **kwargs):
        pytest.fail('Unsafe output must be refused before reading/scoring any raster')
    monkeypatch.setattr(check_submission, 'check_bundle', forbidden)
    monkeypatch.setattr(sys, 'argv', ['check_submission.py', '--format-only', '--output', str(path)])
    assert check_submission.main() == 2
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_designated_report_refuses_symlink_and_hardlink_aliases(tmp_path):
    source = tmp_path / 'input.tif'
    source.write_bytes(b'preserved synthetic input')
    output = tmp_path / 'docs/evidence/independent_validation.json'
    output.parent.mkdir(parents=True)
    card = dict(submission_file='fixture.tif', submission_zip='fixture.zip')
    output.symlink_to(source)
    with pytest.raises(ValueError, match='link alias'):
        check_submission.checked_report_output(output, card, tmp_path)
    output.unlink()
    output.hardlink_to(source)
    with pytest.raises(ValueError, match='link alias'):
        check_submission.checked_report_output(output, card, tmp_path)
    assert source.read_bytes() == b'preserved synthetic input'


@pytest.mark.parametrize('error', [
    zipfile.BadZipFile('corrupt ZIP fixture'),
    RuntimeError('encrypted ZIP fixture'),
])
def test_cli_bad_zip_returns_structured_refusal(monkeypatch, tmp_path, capsys, error):
    report = tmp_path / 'refusal.json'
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(check_submission, 'check_bundle', fail)
    monkeypatch.setattr(sys, 'argv', ['check_submission.py', '--format-only', '--output', str(report)])
    assert check_submission.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result['safe_to_submit'] is False
    assert result['inspection_completed'] is False
    assert result['errors'] == [str(error)]
    assert not report.exists()  # Never publish a successful receipt on failure.
