#!/usr/bin/env python3
"""Fetch live LabelGrid releases and render the website catalog block."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import ipaddress
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterable

API_URL = "https://api.labelgrid.com/api/public/releases"
START_MARKER = "<!-- LABELGRID_CATALOG_START -->"
END_MARKER = "<!-- LABELGRID_CATALOG_END -->"
CAT_RE = re.compile(r"^PLUSH[0-9]{3}[A-Z]?$")
MAX_PAGES = 1000
TIMEOUT = 20
LINK_LABELS = {"bandcamp_url": "Bandcamp", "spotify_url": "Spotify", "applemusic_url": "Apple Music", "beatport_url": "Beatport", "short_url": "Listen"}


class CatalogError(RuntimeError):
    pass


def _https_url(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value) or any(char.isspace() for char in value) or "\\" in value:
        raise CatalogError(f"invalid {field}")
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError as exc:
        raise CatalogError(f"invalid {field}") from exc
    try:
        _ = parsed.port  # Validate malformed/out-of-range ports.
        host = parsed.hostname
    except ValueError as exc:
        raise CatalogError(f"invalid {field}") from exc
    if parsed.scheme != "https" or not parsed.netloc or not host or parsed.username or parsed.password:
        raise CatalogError(f"invalid {field}")
    try:
        address = ipaddress.ip_address(host)
        if address.is_private or address.is_loopback or address.is_unspecified or address.is_link_local:
            raise CatalogError(f"invalid {field}")
    except ValueError:
        pass
    sensitive = {"token", "access_token", "auth", "api_key", "apikey", "key", "signature", "sig", "x-amz-signature", "x-amz-credential", "x-amz-security-token"}
    if any(key.lower() in sensitive for key, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)):
        raise CatalogError(f"invalid {field}")
    return value


def _page_request(label_id: int, page: int, token: str) -> dict[str, Any]:
    if not isinstance(token, str) or not token or any(ord(char) < 33 or ord(char) > 126 for char in token):
        raise CatalogError("invalid LabelGrid API token")
    query = urllib.parse.urlencode({"filter[is_live]": "1", "filter[label_id]": str(label_id), "page": page, "per_page": 100})
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            if response.geturl() != request.full_url:
                raise CatalogError("LabelGrid returned a redirect")
            raw = response.read()
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            raise CatalogError("LabelGrid returned a redirect") from None
        raise CatalogError(f"LabelGrid request failed (HTTP {exc.code})") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise CatalogError("LabelGrid request failed") from None
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CatalogError("LabelGrid returned malformed JSON") from None
    if not isinstance(payload, dict):
        raise CatalogError("LabelGrid returned malformed response")
    return payload


def fetch_all_releases(label_id: int, token: str, fetch_page: Callable[[int], dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Fetch every page and reject inconsistent or partial pagination."""
    if type(label_id) is not int or label_id <= 0 or not isinstance(token, str) or not token:
        raise CatalogError("LABELGRID_LABEL_ID and LABELGRID_API_TOKEN are required")
    getter = fetch_page or (lambda page: _page_request(label_id, page, token))
    all_rows: list[dict[str, Any]] = []
    expected_total = expected_last = None
    page = 1
    while True:
        if page > MAX_PAGES:
            raise CatalogError("LabelGrid pagination exceeds safety limit")
        payload = getter(page)
        rows = payload.get("data")
        meta = payload.get("meta")
        if not isinstance(rows, list) or not isinstance(meta, dict):
            raise CatalogError("LabelGrid returned malformed pagination")
        try:
            current, last, total = (meta[key] for key in ("current_page", "last_page", "total"))
        except KeyError:
            raise CatalogError("LabelGrid returned malformed pagination") from None
        if any(type(value) is not int for value in (current, last, total)):
            raise CatalogError("LabelGrid returned malformed pagination")
        if current != page or last < 1 or current > last or total < 0 or last > MAX_PAGES:
            raise CatalogError("LabelGrid returned invalid pagination")
        if expected_total is None:
            expected_total, expected_last = total, last
        elif (total, last) != (expected_total, expected_last):
            raise CatalogError("LabelGrid pagination changed during fetch")
        if any(not isinstance(row, dict) for row in rows):
            raise CatalogError("LabelGrid returned malformed release")
        if any(type(row.get("label_id")) is not int or row["label_id"] != label_id for row in rows):
            raise CatalogError("LabelGrid returned a release for another label")
        if page < last and not rows:
            raise CatalogError("LabelGrid returned an empty intermediate page")
        all_rows.extend(rows)
        if page == last:
            break
        page += 1
    ids = [row.get("id") for row in all_rows]
    if any(type(identifier) is not int or identifier <= 0 for identifier in ids):
        raise CatalogError("LabelGrid returned invalid release IDs")
    if len(all_rows) != expected_total or len(ids) != len(set(ids)):
        raise CatalogError("LabelGrid returned incomplete or duplicate releases")
    return all_rows


def _normalize_release(row: dict[str, Any], today: dt.date) -> dict[str, Any] | None:
    cat = row.get("cat")
    if not isinstance(cat, str) or not CAT_RE.fullmatch(cat):
        return None
    raw_date = row.get("release_date")
    if raw_date in (None, ""):
        return None
    if not isinstance(raw_date, str):
        raise CatalogError(f"invalid metadata for {cat}")
    try:
        release_date = dt.date.fromisoformat(raw_date[:10])
    except ValueError:
        raise CatalogError(f"invalid metadata for {cat}") from None
    if release_date > today:
        return None
    title = row.get("title")
    artist = row.get("default_display_artist")
    cover = row.get("front_cover")
    if not isinstance(title, str) or not title or not isinstance(artist, str) or not artist or not isinstance(cover, dict):
        raise CatalogError(f"invalid metadata for {cat}")
    image = _https_url(cover.get("url"), f"cover for {cat}")
    links: dict[str, str] = {}
    for field in LINK_LABELS:
        if row.get(field) not in (None, ""):
            links[field] = _https_url(row[field], f"{field} for {cat}")
    return {"cat": cat, "date": release_date, "title": title, "artist": artist, "image": image, "links": links}


def eligible_releases(rows: Iterable[dict[str, Any]], today: dt.date | None = None) -> list[dict[str, Any]]:
    today = today or dt.datetime.now(dt.timezone.utc).date()
    normalized = [item for row in rows if (item := _normalize_release(row, today)) is not None]
    cats = [item["cat"] for item in normalized]
    if len(cats) != len(set(cats)):
        raise CatalogError("duplicate eligible catalog numbers")
    normalized.sort(key=lambda item: (item["date"], item["cat"]), reverse=True)
    if not normalized:
        raise CatalogError("no eligible Plush releases")
    return normalized[:12]


def render_catalog(releases: Iterable[dict[str, Any]], embeds: dict[str, Any] | None = None) -> str:
    embeds = embeds or {}
    cards: list[str] = []
    for release in releases:
        cat, title, artist = (html.escape(str(release[k]), quote=True) for k in ("cat", "title", "artist"))
        image = html.escape(release["image"], quote=True)
        links = release["links"]
        primary = links.get("bandcamp_url") or next(iter(links.values()), "")
        anchor = f'<a href="{html.escape(primary, quote=True)}" target="_blank" rel="noopener noreferrer">' if primary else ""
        close = "</a>" if anchor else ""
        body = f'{anchor}<div class="album-image"><img src="{image}" alt="{cat} — {title}" style="width: 100%; height: 100%; object-fit: cover;"></div>{close}'
        links_html = " ".join(f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{LINK_LABELS[field]}</a>' for field, url in links.items())
        body += f'<div class="album-info"><div class="album-title">{title}</div><div class="album-artist">{artist}</div>'
        if links_html:
            body += f'<div class="album-links">{links_html}</div>'
        body += "</div>"
        embed = embeds.get(release["cat"])
        if isinstance(embed, dict) and embed.get("url") == links.get("bandcamp_url") and isinstance(embed.get("embed"), str):
            embed_url = embed["embed"]
            if embed_url.startswith("https://bandcamp.com/EmbeddedPlayer/") and not any(ord(char) < 32 or char.isspace() or char == "\\" for char in embed_url):
                body += f'<iframe style="border: 0; width: 100%; height: 120px;" src="{html.escape(embed_url, quote=True)}" title="{title} by {artist} on Bandcamp" loading="lazy"></iframe>'
        cards.append(f'<div class="album-card">{body}</div>')
    return "\n".join(cards)


def replace_catalog(html_text: str, content: str) -> str:
    if html_text.count(START_MARKER) != 1 or html_text.count(END_MARKER) != 1:
        raise CatalogError("catalog markers must occur exactly once")
    start = html_text.index(START_MARKER) + len(START_MARKER)
    end = html_text.index(END_MARKER)
    if end < start:
        raise CatalogError("catalog markers are out of order")
    end_line = html_text.rfind("\n", start, end) + 1
    if end_line >= start and not html_text[end_line:end].strip():
        end = end_line
    return html_text[:start] + "\n" + content + "\n" + html_text[end:]


def load_embeds(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise CatalogError("catalog-embeds.json is malformed") from None
    if not isinstance(data, dict):
        raise CatalogError("catalog-embeds.json must be an object")
    return data


def sync_catalog(html_path: Path, releases: list[dict[str, Any]], embeds: dict[str, Any] | None = None, apply: bool = False) -> bool:
    current = html_path.read_text(encoding="utf-8")
    updated = replace_catalog(current, render_catalog(releases, embeds))
    changed = updated != current
    if apply and changed:
        mode = html_path.stat().st_mode
        fd, tmp = tempfile.mkstemp(prefix=f".{html_path.name}.", dir=str(html_path.parent), text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(updated)
            os.chmod(tmp, mode & 0o7777)
            os.replace(tmp, html_path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--html", type=Path, default=Path("website/public/index.html"))
    parser.add_argument("--embeds", type=Path, default=Path("website/catalog-embeds.json"))
    args = parser.parse_args(argv)
    try:
        label_raw = os.environ.get("LABELGRID_LABEL_ID", "")
        if not label_raw.isdigit() or int(label_raw) <= 0:
            raise CatalogError("LABELGRID_LABEL_ID must be a positive integer")
        token = os.environ.get("LABELGRID_API_TOKEN", "")
        rows = fetch_all_releases(int(label_raw), token)
        selected = eligible_releases(rows)
        changed = sync_catalog(args.html, selected, load_embeds(args.embeds), args.apply)
        print(f"catalog: {len(selected)} releases; {'changed' if changed else 'unchanged'}" + (" (applied)" if args.apply and changed else ""))
        return 0
    except (CatalogError, OSError) as exc:
        if isinstance(exc, OSError):
            print("error: unable to read or write catalog files", file=sys.stderr)
            return 1
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
