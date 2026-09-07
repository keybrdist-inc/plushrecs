import datetime as dt
import json
import os
import tempfile
import unittest
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from scripts import sync_catalog


def release(cat="PLUSH126", day="2026-01-01", **extra):
    value = {
        "id": int(cat[5:8]),
        "label_id": 1,
        "cat": cat,
        "release_date": day,
        "title": "A <Title>",
        "default_display_artist": "An & Artist",
        "front_cover": {"url": "https://cdn.example.test/cover.jpg"},
        "bandcamp_url": "https://plush.bandcamp.com/album/a",
        "spotify_url": "https://open.spotify.com/album/a",
    }
    value.update(extra)
    return value


class SyncCatalogTests(unittest.TestCase):
    def test_fetches_all_pages_and_rejects_unstable_pagination(self):
        pages = {
            1: {"data": [release("PLUSH125")], "meta": {"current_page": 1, "last_page": 2, "total": 2}},
            2: {"data": [release("PLUSH126")], "meta": {"current_page": 2, "last_page": 2, "total": 2}},
        }
        self.assertEqual(len(sync_catalog.fetch_all_releases(1, "secret", pages.get)), 2)
        pages[2]["meta"]["total"] = 3
        with self.assertRaises(sync_catalog.CatalogError):
            sync_catalog.fetch_all_releases(1, "secret", pages.get)

    def test_rejects_duplicate_or_partial_page(self):
        response = {"data": [release("PLUSH125")], "meta": {"current_page": 1, "last_page": 1, "total": 2}}
        with self.assertRaises(sync_catalog.CatalogError):
            sync_catalog.fetch_all_releases(1, "secret", lambda _: response)

    def test_excludes_future_undated_and_non_catalog_records(self):
        rows = [release("PLUSH125", "2026-01-01"), release("PLUSH126", "2027-01-01"), release("PLUSH127", None), release("OTHER1", "2020-01-01")]
        selected = sync_catalog.eligible_releases(rows, dt.date(2026, 9, 7))
        self.assertEqual([item["cat"] for item in selected], ["PLUSH125"])

    def test_invalid_metadata_fails_for_eligible_record(self):
        with self.assertRaises(sync_catalog.CatalogError):
            sync_catalog.eligible_releases([release(front_cover={"url": "http://unsafe.test/a"})], dt.date(2026, 9, 7))

    def test_duplicate_catalogs_and_bad_labels_fail(self):
        with self.assertRaises(sync_catalog.CatalogError):
            sync_catalog.eligible_releases([release(), release(id=127)], dt.date(2026, 9, 7))
        response = {"data": [release(label_id=2)], "meta": {"current_page": 1, "last_page": 1, "total": 1}}
        with self.assertRaises(sync_catalog.CatalogError):
            sync_catalog.fetch_all_releases(1, "secret", lambda _: response)

    def test_latest_twelve_are_date_then_catalog_descending(self):
        rows = [release(f"PLUSH{index:03d}", "2026-01-01") for index in range(1, 15)]
        selected = sync_catalog.eligible_releases(rows, dt.date(2026, 9, 7))
        self.assertEqual([item["cat"] for item in selected], [f"PLUSH{index:03d}" for index in range(14, 2, -1)])

    def test_html_is_escaped_and_unsafe_links_rejected(self):
        item = sync_catalog.eligible_releases([release()], dt.date(2026, 9, 7))[0]
        rendered = sync_catalog.render_catalog([item])
        self.assertIn("A &lt;Title&gt;", rendered)
        self.assertIn("An &amp; Artist", rendered)
        self.assertNotIn("A <Title>", rendered)
        with self.assertRaises(sync_catalog.CatalogError):
            sync_catalog.eligible_releases([release(short_url="javascript:alert(1)")], dt.date(2026, 9, 7))

    def test_marker_integrity_and_idempotence(self):
        item = sync_catalog.eligible_releases([release()], dt.date(2026, 9, 7))[0]
        source = "before\n<!-- LABELGRID_CATALOG_START -->\nold\n<!-- LABELGRID_CATALOG_END -->\nafter"
        updated = sync_catalog.replace_catalog(source, sync_catalog.render_catalog([item]))
        self.assertEqual(sync_catalog.replace_catalog(updated, sync_catalog.render_catalog([item])), updated)
        with self.assertRaises(sync_catalog.CatalogError):
            sync_catalog.replace_catalog(source.replace("<!-- LABELGRID_CATALOG_START -->", ""), "x")

    def test_indented_closing_marker_line_is_preserved(self):
        suffix = "\t    " + sync_catalog.END_MARKER + "\n</div>\nfooter"
        source = "header\n    " + sync_catalog.START_MARKER + "\nold card\n" + suffix
        updated = sync_catalog.replace_catalog(source, "new card")
        self.assertEqual(updated, "header\n    " + sync_catalog.START_MARKER + "\nnew card\n" + suffix)
        self.assertEqual(sync_catalog.replace_catalog(updated, "new card"), updated)

    def test_embed_requires_exact_bandcamp_url(self):
        item = sync_catalog.eligible_releases([release()], dt.date(2026, 9, 7))[0]
        embed = {"PLUSH126": {"url": item["links"]["bandcamp_url"], "embed": "https://bandcamp.com/EmbeddedPlayer/album=1/"}}
        self.assertIn("EmbeddedPlayer", sync_catalog.render_catalog([item], embed))
        embed["PLUSH126"]["url"] = "https://plush.bandcamp.com/album/other"
        self.assertNotIn("EmbeddedPlayer", sync_catalog.render_catalog([item], embed))

    def test_main_second_page_failure_and_missing_markers_leave_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.html"
            path.write_text("<!-- LABELGRID_CATALOG_START -->old<!-- LABELGRID_CATALOG_END -->", encoding="utf-8")
            first = {"data": [release()], "meta": {"current_page": 1, "last_page": 2, "total": 2}}
            with patch.dict(os.environ, {"LABELGRID_LABEL_ID": "1", "LABELGRID_API_TOKEN": "secret"}), patch("scripts.sync_catalog._page_request", side_effect=[first, sync_catalog.CatalogError("second page")]):
                before = path.read_bytes()
                self.assertEqual(sync_catalog.main(["--apply", "--html", str(path), "--embeds", str(Path(directory) / "none.json")]), 1)
                self.assertEqual(before, path.read_bytes())
            path.write_text("missing marker", encoding="utf-8")
            with patch.dict(os.environ, {"LABELGRID_LABEL_ID": "1", "LABELGRID_API_TOKEN": "secret"}), patch("scripts.sync_catalog._page_request", return_value={"data": [release()], "meta": {"current_page": 1, "last_page": 1, "total": 1}}):
                before = path.read_bytes()
                self.assertEqual(sync_catalog.main(["--apply", "--html", str(path)]), 1)
                self.assertEqual(before, path.read_bytes())

    def test_redirect_does_not_follow_or_leak_token(self):
        error = HTTPError(sync_catalog.API_URL, 302, "redirect", {}, None)
        with patch("scripts.sync_catalog.urllib.request.build_opener") as build:
            build.return_value.open.side_effect = error
            with self.assertRaisesRegex(sync_catalog.CatalogError, "redirect") as raised:
                sync_catalog._page_request(7, 1, "DO_NOT_PRINT")
            handler = build.call_args.args[0]
            self.assertIsNone(handler.redirect_request(None, None, 302, "", {}, "https://evil.test"))
        self.assertNotIn("DO_NOT_PRINT", str(raised.exception))

    def test_request_query_and_main_dry_run(self):
        page = {"data": [release()], "meta": {"current_page": 1, "last_page": 1, "total": 1}}
        with patch("scripts.sync_catalog.urllib.request.build_opener") as build:
            build.return_value.open.side_effect = HTTPError(sync_catalog.API_URL, 500, "fail", {}, None)
            with self.assertRaises(sync_catalog.CatalogError):
                sync_catalog._page_request(7, 2, "secret")
            request = build.return_value.open.call_args.args[0]
            parsed = urllib.parse.urlsplit(request.full_url)
            self.assertEqual(urllib.parse.parse_qs(parsed.query), {"filter[label_id]": ["7"], "filter[is_live]": ["1"], "page": ["2"], "per_page": ["100"]})
            self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page_html = root / "index.html"
            page_html.write_text("<!-- LABELGRID_CATALOG_START -->old<!-- LABELGRID_CATALOG_END -->", encoding="utf-8")
            embed_file = root / "embeds.json"
            embed_file.write_text("{}", encoding="utf-8")
            with patch.dict(os.environ, {"LABELGRID_LABEL_ID": "1", "LABELGRID_API_TOKEN": "secret"}), patch("scripts.sync_catalog._page_request", return_value=page):
                before = page_html.read_bytes()
                self.assertEqual(sync_catalog.main(["--html", str(page_html), "--embeds", str(embed_file)]), 0)
                self.assertEqual(before, page_html.read_bytes())

    def test_actual_page_and_embed_map_survive_cli_generation(self):
        repo = Path(__file__).resolve().parents[1]
        source = (repo / "website/public/index.html").read_text()
        embeds = json.loads((repo / "website/catalog-embeds.json").read_text())
        rows = [release(cat, bandcamp_url=entry["url"]) for cat, entry in embeds.items()]
        payload = {"data": rows, "meta": {"current_page": 1, "last_page": 1, "total": len(rows)}}
        class Tags(HTMLParser):
            def __init__(self):
                super().__init__()
                self.players = []
            def handle_starttag(self, tag, attrs):
                if tag == "iframe":
                    self.players.append(dict(attrs).get("src"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "index.html"
            target.write_text(source)
            with patch.dict(os.environ, {"LABELGRID_LABEL_ID": "1", "LABELGRID_API_TOKEN": "test-token"}), patch("scripts.sync_catalog._page_request", return_value=payload):
                self.assertEqual(sync_catalog.main(["--apply", "--html", str(target), "--embeds", str(repo / "website/catalog-embeds.json")]), 0)
            rendered = target.read_text()
            parser = Tags()
            parser.feed(rendered)
            for entry in embeds.values():
                self.assertIn(entry["embed"], parser.players)
            self.assertEqual(source.split(sync_catalog.START_MARKER)[0], rendered.split(sync_catalog.START_MARKER)[0])
            self.assertEqual(source.split(sync_catalog.END_MARKER)[1], rendered.split(sync_catalog.END_MARKER)[1])

    def test_strict_pagination_and_ids(self):
        base = {"data": [release()], "meta": {"current_page": 1, "last_page": 1, "total": 1}}
        for value in (True, 1.5, "1", None):
            with self.subTest(value=value):
                malformed = {**base, "meta": {**base["meta"], "total": value}}
                with self.assertRaises(sync_catalog.CatalogError):
                    sync_catalog.fetch_all_releases(1, "test-token", lambda _: malformed)
        for rows in ([release(id=True)], [release(label_id=True)], [release(), release()]):
            with self.subTest(rows=rows):
                malformed = {"data": rows, "meta": {**base["meta"], "total": len(rows)}}
                with self.assertRaises(sync_catalog.CatalogError):
                    sync_catalog.fetch_all_releases(1, "test-token", lambda _: malformed)
        with self.assertRaises(sync_catalog.CatalogError):
            sync_catalog.eligible_releases([])

    def test_sensitive_urls_and_invalid_token_never_reach_network(self):
        for url in ("https://user:pass@example.test/a", "https://127.0.0.1/a", "https://example.test:bad/a", "https://example.test/a?X-Amz-Signature=private", "https://example.test/with space"):
            with self.subTest(url=url), self.assertRaises(sync_catalog.CatalogError):
                sync_catalog.eligible_releases([release(short_url=url)])
        with patch("scripts.sync_catalog.urllib.request.build_opener") as build:
            for token in ("bad\r\nheader", "nonascii-☃"):
                with self.subTest(token=token), self.assertRaises(sync_catalog.CatalogError):
                    sync_catalog._page_request(1, 1, token)
            build.assert_not_called()

    def test_sync_writes_only_when_changed(self):
        item = sync_catalog.eligible_releases([release()], dt.date(2026, 9, 7))[0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.html"
            path.write_text("<!-- LABELGRID_CATALOG_START -->\nold\n<!-- LABELGRID_CATALOG_END -->", encoding="utf-8")
            self.assertTrue(sync_catalog.sync_catalog(path, [item], apply=True))
            first = path.read_bytes()
            self.assertFalse(sync_catalog.sync_catalog(path, [item], apply=True))
            self.assertEqual(first, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
