#!/usr/bin/env python3
"""Refresh a small, score-free feed of official GEMS source availability.

This script deliberately does not scrape or publish leaderboard scores. It records
source reachability, page titles, checksums, and expected-content checks so that
claims can be reviewed at the source without misattributing a score to a TIFF.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ALLOWED_HOSTS = {
    "github.com",
    "gdr.openei.org",
    "www.usgs.gov",
    "usgs.gov",
    "gbcge.org",
    "www.gbcge.org",
    "epsg.io",
    "docs.nlr.gov",
    "www.nlr.gov",
}
MAX_RESPONSE_BYTES = 2_000_000


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_title = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._parts.append(data)

    @property
    def title(self) -> str:
        return " ".join(" ".join(self._parts).split())[:180]


class _AllowedRedirects(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Request | None:
        host = (urlparse(newurl).hostname or "").lower()
        if host not in ALLOWED_HOSTS:
            raise HTTPError(newurl, code, f"Redirect host not allowlisted: {host}", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _decode_body(body: bytes, content_type: str) -> str:
    charset = "utf-8"
    for part in content_type.split(";")[1:]:
        name, sep, value = part.strip().partition("=")
        if sep and name.lower() == "charset":
            charset = value.strip('"\'') or charset
            break
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def classify_page(
    source: dict[str, Any],
    *,
    http_status: int,
    final_url: str,
    title: str,
    text: str,
    body_sha256: str | None = None,
) -> dict[str, Any]:
    """Classify a fetched public page without extracting numerical scores."""
    final_path = urlparse(final_url).path.lower()
    normalized_text = unescape(text).lower()
    normalized_title = unescape(title).lower()
    expected_terms = [str(term).lower() for term in source.get("expected_terms", [])]

    if "/accounts/login" in final_path or normalized_title.strip() == "login" or (
        "password" in normalized_text and "log in" in normalized_text
    ):
        status = "login_required"
        note = "The source redirected to or rendered a login page; no protected content was read."
    elif http_status < 200 or http_status >= 300:
        status = "http_error"
        note = f"The source returned HTTP status {http_status}."
    elif expected_terms and not all(term in normalized_text for term in expected_terms):
        missing = [term for term in expected_terms if term not in normalized_text]
        status = "content_check_failed"
        note = "Expected source markers were absent: " + ", ".join(missing)
    else:
        status = "reachable_verified"
        note = "The public page responded and its configured content checks passed."

    result: dict[str, Any] = {
        "id": source["id"],
        "label": source["label"],
        "url": source["url"],
        "status": status,
        "http_status": http_status,
        "final_url": final_url,
        "title": title,
        "note": note,
    }
    if body_sha256:
        result["body_sha256"] = body_sha256
    return result


def fetch_source(source: dict[str, Any], timeout: float = 15.0) -> dict[str, Any]:
    url = str(source["url"])
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
        return {
            "id": source.get("id", "unknown"),
            "label": source.get("label", "Unknown source"),
            "url": url,
            "status": "blocked_url",
            "note": "Only HTTPS sources on the source allowlist are fetched.",
        }

    request = Request(
        url,
        headers={
            "User-Agent": "GEMSDOE87-source-feed/1.0 (public-source verification; no credentials)",
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.8,*/*;q=0.5",
        },
    )
    opener = build_opener(_AllowedRedirects())
    try:
        with opener.open(request, timeout=timeout) as response:
            status_code = int(response.status)
            final_url = response.geturl()
            content_type = response.headers.get("Content-Type", "")
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                body = body[:MAX_RESPONSE_BYTES]
            text = _decode_body(body, content_type)
            parser = _TitleParser()
            try:
                parser.feed(text)
            except Exception:
                pass
            return classify_page(
                source,
                http_status=status_code,
                final_url=final_url,
                title=parser.title,
                text=text,
                body_sha256=hashlib.sha256(body).hexdigest(),
            )
    except HTTPError as exc:
        final_url = exc.geturl()
        body = b""
        try:
            body = exc.read(MAX_RESPONSE_BYTES)
        except Exception:
            pass
        text = _decode_body(body, exc.headers.get("Content-Type", "") if exc.headers else "")
        parser = _TitleParser()
        try:
            parser.feed(text)
        except Exception:
            pass
        item = classify_page(
            source,
            http_status=exc.code,
            final_url=final_url,
            title=parser.title,
            text=text,
            body_sha256=hashlib.sha256(body).hexdigest() if body else None,
        )
        if item["status"] == "http_error":
            item["note"] = f"The source returned HTTP status {exc.code}: {exc.reason}."
        return item
    except (URLError, TimeoutError, OSError) as exc:
        return {
            "id": source["id"],
            "label": source["label"],
            "url": url,
            "status": "unavailable",
            "note": f"Fetch failed: {type(exc).__name__}: {exc}",
        }


def build_feed(config_path: Path, output_path: Path, *, fetched_at: str | None = None) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    sources = config.get("sources")
    if not isinstance(sources, list):
        raise ValueError("source config must contain a 'sources' list")
    timestamp = fetched_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    entries = [fetch_source(source) for source in sources if source.get("feed_check", False)]
    feed = {
        "schema_version": 1,
        "checked_at": timestamp,
        "refresh_mode": "automated public-page check; no credentials and no leaderboard scores are collected",
        "numeric_scores_omitted": True,
        "entries": entries,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return feed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("data/sources.json"), help="source registry JSON")
    parser.add_argument("--output", type=Path, default=Path("data/feed.json"), help="feed JSON output path")
    args = parser.parse_args(argv)
    try:
        feed = build_feed(args.config, args.output)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2
    counts: dict[str, int] = {}
    for entry in feed["entries"]:
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
    print(json.dumps({"status": "updated", "checked_at": feed["checked_at"], "source_count": len(feed["entries"]), "by_status": counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
