"""Publication integrity tests, not geological experiments or raster validation."""
import hashlib
import json
import zipfile

import pytest

from scripts import build_site, update_next_steps


@pytest.fixture
def publication(tmp_path):
    (tmp_path / 'downloads').mkdir()
    (tmp_path / 'evidence').mkdir()
    payload = b'fixture bytes, deliberately not a scientific raster'
    card = dict(safe_to_submit=False, verdict='negative', submission_file='research.tif',
                submission_zip='research.zip', raster_sha256=hashlib.sha256(payload).hexdigest(),
                decoded_raster_sha256='a' * 64)
    (tmp_path / 'downloads/research.tif').write_bytes(payload)
    with zipfile.ZipFile(tmp_path / 'downloads/research.zip', 'w') as z:
        z.writestr('research.tif', payload)
    receipt = dict(card, local_format_valid=True, reference_mirror_hashes_match=True,
                   no_nan_inside_footprint=True, range_0_1=True, crs_shape_transform_match=True,
                   zip_contains_exactly_one_matching_tiff=True)
    (tmp_path / 'evidence/independent_validation.json').write_text(json.dumps(receipt))
    return tmp_path, card, receipt


def test_current_bytes_bound_to_passing_receipt(publication):
    docs, card, _ = publication
    build_site.require_validated_download(card, docs)


@pytest.mark.parametrize('key', ['local_format_valid', 'reference_mirror_hashes_match',
    'no_nan_inside_footprint', 'range_0_1', 'crs_shape_transform_match',
    'zip_contains_exactly_one_matching_tiff'])
@pytest.mark.parametrize('value', [False, None, 'true'])
def test_failed_missing_or_nonboolean_check_blocks(publication, key, value):
    docs, card, receipt = publication
    receipt[key] = value
    (docs / 'evidence/independent_validation.json').write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='passing preflight'):
        build_site.require_validated_download(card, docs)


@pytest.mark.parametrize('key', ['raster_sha256', 'decoded_raster_sha256'])
def test_stale_receipt_blocks(publication, key):
    docs, card, receipt = publication
    receipt[key] = '0' * 64
    (docs / 'evidence/independent_validation.json').write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='inconsistent'):
        build_site.require_validated_download(card, docs)


def test_modified_tiff_blocks(publication):
    docs, card, _ = publication
    (docs / 'downloads/research.tif').write_bytes(b'changed')
    with pytest.raises(ValueError, match='validated hash'):
        build_site.require_validated_download(card, docs)


@pytest.mark.parametrize('kind', ['extra-member', 'different-bytes', 'invalid-zip'])
def test_changed_zip_blocks(publication, kind):
    docs, card, _ = publication
    path = docs / 'downloads/research.zip'
    if kind == 'invalid-zip':
        path.write_bytes(b'not a ZIP')
    else:
        payload = (docs / 'downloads/research.tif').read_bytes()
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('research.tif', b'x' * len(payload) if kind == 'different-bytes' else payload)
            if kind == 'extra-member':
                z.writestr('extra.txt', 'extra')
    with pytest.raises((ValueError, zipfile.BadZipFile)):
        build_site.require_validated_download(card, docs)


@pytest.mark.parametrize('name', ['../research.tif', '/tmp/research.tif', 'dir\\research.tif'])
def test_unsafe_download_path_blocks(publication, name):
    docs, card, _ = publication
    card['submission_file'] = name
    with pytest.raises(ValueError, match='filename'):
        build_site.require_validated_download(card, docs)


def test_main_checks_before_writing_any_page(publication, monkeypatch):
    docs, card, _ = publication
    (docs / 'downloads/research.tif').write_bytes(b'changed')
    monkeypatch.setattr(build_site, 'DOCS', docs)
    monkeypatch.setattr(build_site, 'load', lambda _: card)
    with pytest.raises(ValueError):
        build_site.main()
    assert not list(docs.glob('*.html'))


def test_suggestions_refuse_edited_approval_flags():
    with pytest.raises(ValueError, match='Frozen negative'):
        update_next_steps.derive({'safe_to_submit': True, 'verdict': 'promote'}, {})
