#!/usr/bin/env python3
"""Build an explicitly metadata-only prior-approach catalog, never a score table."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TAGS = {
    'ridge / line-shape name': r'ridge|lineament|frangi|hessian',
    'gradient / physical-layer name': r'hgm|gradient|magnetic|gravity|magnet|basement',
    'pruning / thinning / sparse emission name': r'prun|thin|sparse|pindrop|decimat|solo|decile',
    'fusion / weighting name': r'blend|fusion|fused|bundle|ensemble|mix|weighted',
    'continuous / soft representation name': r'continuous|soft|confidence|probabil',
    'learned-model name': r'unet|u-net|randomforest|random-forest|xgboost|neural',
    'spatial allocation / gating name': r'quadrant|regional|density|gating|(?:^|[-_])gate(?:[-_]|$)',
}


def main():
    sites = json.loads((ROOT / 'evidence/site_inventory.json').read_text())
    history = json.loads((ROOT / 'registry/historical_index.json').read_text())
    inventory = json.loads((ROOT / 'evidence/registry_refreshed.json').read_text())
    filenames = {}
    for row in inventory['rasters']:
        for source in row['sources']:
            repo, path = source.split(':', 1)
            filenames.setdefault(repo, set()).add(path)
    claims = {}
    for row in history['scored']:
        claims[row['site_repo']] = claims.get(row['site_repo'], 0) + 1
    rows = []
    for site in sites['repos']:
        paths = sorted(filenames.get(site['repo'], []))
        names = '\n'.join(Path(path).name.lower() for path in paths)
        rows.append(dict(repository=site['repo'], pinned_commit=site['commit'],
                         pinned_tree_url=f"https://github.com/buffedlizard55-lab/{site['repo']}/tree/{site['commit']}",
                         indexed_raster_paths=len(paths), historical_unverified_claim_references=claims.get(site['repo'], 0),
                         literal_filename_tags=[tag for tag, pattern in TAGS.items() if re.search(pattern, names)] or ['not inferred'],
                         representative_filenames=[Path(path).name for path in paths[:3]],
                         scope='Metadata triage only; names do not verify implementation, geology, uniqueness or organizer performance.'))
    result = dict(schema_version=1, repositories=len(rows), historical_claim_references=len(history['scored']),
                  source='Pinned accessible Git trees plus hash-verified raster inventory; original numerical claims quarantined in historical_index.json.',
                  numeric_historical_scores_used=False, all_websites_editorially_reviewed=False,
                  measured_ancestry_case='H33 versus its GEMSDOE31 parent only; see h33_forensics.json.', rows=rows)
    (ROOT / 'docs/data/prior_catalog.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'Cataloged {len(rows)} repository metadata snapshots; no new experiment or organizer-score claim.')


if __name__ == '__main__':
    main()
