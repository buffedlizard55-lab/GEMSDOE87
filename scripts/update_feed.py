#!/usr/bin/env python3
"""Refresh public URL transport health; never fabricate authentication or scores.

This checker does not turn URL reachability into scientific verification and
never changes the immutable research verdict or submits to DrivenData. Failed
fetches preserve the date of the last actual leaderboard observation.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
LEADERBOARD = 'https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/'
ALLOWED_HOSTS = {'www.drivendata.org', 'community.drivendata.org', 'github.com',
                 'docs.nlr.gov', 'www.usgs.gov', 'pubs.usgs.gov', 'gbcge.org', 'gdr.openei.org'}


class TableRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.table, self.row, self.cell = [], None, None, None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.depth += 1
            if self.depth == 1:
                self.table = []
        if self.depth != 1:
            return
        if tag == 'tr':
            self.row = []
        if tag in ('td', 'th') and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.depth == 1 and self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if self.depth == 1:
            if tag in ('td', 'th') and self.row is not None and self.cell is not None:
                self.row.append(' '.join(' '.join(self.cell).split()))
                self.cell = None
            if tag == 'tr' and self.row is not None:
                if self.row:
                    self.table.append(self.row)
                self.row, self.cell = None, None
            if tag == 'table':
                self.tables.append(self.table)
                self.table, self.row, self.cell = None, None, None
        if tag == 'table':
            self.depth = max(0, self.depth - 1)


def parse_leaderboard(text: str) -> float | None:
    """Accept one leading row only in an explicit rank-and-score table.

    A random rank-like row, a footer number, duplicate leaders, or a changed
    column layout must retain the last dated observation, not invent an update.
    """
    parser = TableRows()
    parser.feed(text)
    leaders = []
    for table in parser.tables:
        if not table:
            continue
        headers = [cell.strip().lower() for cell in table[0]]
        ranks = [i for i, label in enumerate(headers) if label in ('rank', '#', 'place')]
        scores = [i for i, label in enumerate(headers) if label in ('score', 'dti', 'public score', 'public dti')]
        if len(ranks) != 1 or len(scores) != 1:
            continue
        rank_col, score_col = ranks[0], scores[0]
        for row in table[1:]:
            if len(row) <= max(rank_col, score_col) or not re.fullmatch(r'#?\s*1', row[rank_col]):
                continue
            if not re.fullmatch(r'(?:0|1)\.\d{4,6}', row[score_col]):
                return None
            value = float(row[score_col])
            if not 0 <= value <= 1:
                return None
            leaders.append(value)
    return leaders[0] if len(leaders) == 1 else None


def check(source):
    url = source['url']
    row = dict(id=source['id'], url=url, transport_ok=False,
               content_verified_by_health_check=False)
    if urlparse(url).scheme != 'https' or urlparse(url).hostname not in ALLOWED_HOSTS:
        row.update(status='blocked-unexpected-host', error='Source is outside the explicit official-public host allowlist')
        return row, None
    try:
        response = requests.get(url, timeout=(5, 12),
                                headers={'User-Agent': 'GEMSDOE87-public-source-health/1.0'},
                                stream=True)
        with response:
            row.update(http_status=response.status_code, final_url=response.url)
            if urlparse(response.url).scheme != 'https' or urlparse(response.url).hostname not in ALLOWED_HOSTS:
                row.update(status='redirected-outside-approved-https-scope')
                return row, None
            login = '/login' in urlparse(response.url).path
            row.update(transport_ok=bool(response.ok and not login),
                       status='login-required' if login else 'reachable' if response.ok else 'http-error')
            if source['id'] == 'leaderboard' and row['transport_ok']:
                final, expected = urlparse(response.url), urlparse(LEADERBOARD)
                if final.netloc != expected.netloc or final.path.rstrip('/') != expected.path.rstrip('/'):
                    row['leaderboard_parse_status'] = 'unexpected-origin-or-path; prior observation retained'
                    return row, None
                chunks = []
                size = 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 5 * 1024 * 1024:
                        raise ValueError('Leaderboard body exceeds transport budget')
                    chunks.append(chunk)
                value = parse_leaderboard(b''.join(chunks).decode(response.encoding or 'utf-8', errors='replace'))
                if value is not None:
                    return row, dict(value=value, source_url=LEADERBOARD,
                                     observed_utc=datetime.now(timezone.utc).isoformat(),
                                     evidence_class='PUBLIC-LEADERBOARD-OBSERVATION',
                                     artifact_submission_receipt=False)
                row['leaderboard_parse_status'] = 'no-unambiguous-leading-row; prior observation retained'
        return row, None
    except (requests.RequestException, ValueError) as exc:
        row.update(transport_ok=False, status='transport-unavailable', error=str(exc)[:350])
        return row, None


def main():
    path = ROOT / 'docs/data/feed.json'
    prior = json.loads(path.read_text()) if path.exists() else {}
    sources_doc = json.loads((ROOT / 'registry/sources.json').read_text())
    sources = sources_doc['sources']
    # Owner H33 is a historical research source, not part of official URL health.
    sources = [s for s in sources if s['id'] != 'h33']
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(check, sources))
    observations = [observation for _, observation in outcomes if observation]
    output = dict(schema_version=1, last_attempt_utc=datetime.now(timezone.utc).isoformat(),
                  research_content_reviewed_utc_date=sources_doc.get('reviewed_utc_date', '2026-10-23'),
                  checks=[row for row, _ in outcomes],
                  public_leaderboard_observation=observations[-1] if observations else prior.get('public_leaderboard_observation'),
                  observation_refreshed_this_attempt=bool(observations),
                  current_account_cap=None, remaining_account_slots=None,
                  organizer_submission_receipt=None,
                  policy='URL transport health only; does not certify content, authenticated cap, artifact score, or promotion.',
                  scientific_experiments_run=0, submission_slots_used=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.partial')
    temporary.write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)
    ok = sum(row['transport_ok'] for row, _ in outcomes)
    print(f'URL transport checks: {ok}/{len(outcomes)} reachable; failure/login states retained explicitly.')
    return 0  # Transport failures are feed data, not permission to fabricate a fresh observation.


if __name__ == '__main__':
    raise SystemExit(main())
