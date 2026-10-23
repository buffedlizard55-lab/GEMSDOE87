#!/usr/bin/env python3
"""Offline audit of generated Pages: links, anchors, download identity, decision clarity."""
from __future__ import annotations
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.ids, self.text, self.lang = [], [], [], None
        self.h1 = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'html':
            self.lang = attrs.get('lang')
        if tag == 'h1':
            self.h1 += 1
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if attrs.get('href'):
            self.links.append(attrs['href'])
        if tag in ('script', 'img') and attrs.get('src'):
            self.links.append(attrs['src'])
        if tag == 'img' and not attrs.get('alt'):
            raise ValueError('Image needs meaningful alt text')

    def handle_data(self, data):
        self.text.append(data)


def audit() -> dict:
    files = sorted(DOCS.glob('*.html'))
    pages = {}
    errors = []
    for path in files:
        p = Page()
        try:
            p.feed(path.read_text())
            if p.lang != 'en':
                errors.append(f'{path.name}: missing language')
            if len(p.ids) != len(set(p.ids)):
                errors.append(f'{path.name}: duplicate IDs')
            if p.h1 != 1:
                errors.append(f'{path.name}: expected exactly one main heading, got {p.h1}')
            pages[path.resolve()] = p
        except ValueError as exc:
            errors.append(f'{path.name}: {exc}')
    local_links = 0
    for path, p in pages.items():
        for href in p.links:
            link = urlsplit(href)
            if link.scheme or link.netloc:
                if link.hostname in ('localhost', '127.0.0.1'):
                    errors.append(f'{path.name}: browser-facing localhost URL')
                continue
            dest = (path.parent / unquote(link.path)).resolve() if link.path else path
            if not dest.is_relative_to(ROOT):
                errors.append(f'{path.name}: link escapes repository: {href}')
                continue
            if not dest.exists():
                errors.append(f'{path.name}: missing local target: {href}')
                continue
            local_links += 1
            if link.fragment and dest.suffix == '.html':
                target = pages.get(dest)
                if target and unquote(link.fragment) not in target.ids:
                    errors.append(f'{path.name}: missing anchor: {href}')
    compatibility = [('index.html', 'index.html'), ('executive-summary.html', 'executive-summary.html'),
                     ('research.html', 'science.html'), ('sources.html', 'sources.html')]
    status_path = ROOT / 'data/submission-status.json'
    root_promoted = False
    if status_path.is_file():
        st = json.loads(status_path.read_text())
        root_promoted = bool(st.get('submission_ready') is True and st.get('status') == 'ready')
    for filename, target in compatibility:
        root_page = ROOT / filename
        html = root_page.read_text()
        expected = 'docs/' + target
        if f'content="0;url={expected}"' not in html or f'href="{expected}"' not in html:
            errors.append(f'{filename}: established entrypoint does not redirect to the current page')
        if not (ROOT / expected).is_file():
            errors.append(f'{filename}: compatibility target missing')
        local_links += 1
    card = json.loads((DOCS / 'evidence/run_card.json').read_text())
    is_prom = card.get('verdict') == 'promote' and card.get('safe_to_submit') is True
    for name in ('index.html', 'executive-summary.html'):
        path = (DOCS / name).resolve()
        p = pages[path]
        words = ' '.join(p.text).lower()
        if not any(card['submission_file'] in href for href in p.links):
            errors.append(f'{name}: missing direct TIFF download')
        if is_prom:
            if 'validated' not in words or 'safe to download' not in words and 'safe to submit' not in words:
                errors.append(f'{name}: promoted candidate readiness banner missing')
        else:
            if 'do not submit' not in words:
                errors.append(f'{name}: negative warning missing')
    if len(card['submission_note']) > 140:
        errors.append('Submission note exceeds the project limit')
    js = (DOCS / 'assets/site.js').read_text()
    if re.search(r'https?://(?:localhost|127\.0\.0\.1)', js):
        errors.append('JavaScript contains a browser-facing localhost dependency')
    return dict(passed=not errors, pages=len(pages), local_links_verified=local_links,
                compatibility_entrypoints=len(compatibility), decision_wording_checked=True, errors=errors)


if __name__ == '__main__':
    result = audit()
    (DOCS / 'evidence/site_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
