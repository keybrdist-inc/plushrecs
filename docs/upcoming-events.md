# OBS upcoming events overlay

Use `https://about.plushrecs.com/upcoming-events` as an OBS Browser Source.
Set 1080 × 1080 for a square flyer or 1920 × 1080 for black side bars.
The full flyer is centered without cropping. There is no navigation link,
text overlay, audio, or visible control. Flyers crossfade every 180 seconds
over 800ms. Reduced-motion mode switches directly.

Query options:

- `?timer=180` sets seconds between flyers. Use a positive whole number within
  the browser timer limit (1–2147483 seconds). Missing or invalid values use 180.
- `?id=24019` pins the PHACE flyer. IDs are the actual Recon campaign IDs from
  event page URLs, not positions in the list. The anniversary flyer is `24044`.
- `?id=24044&timer=180` keeps the anniversary flyer pinned; a single selected
  item does not cycle. Feed refreshes still pick up artwork changes.

A pinned event remains visible after its date while present in the feed.
An unknown or invalid ID shows black, with no fallback to an unrelated event.
Remove `id` to return to upcoming-event rotation.

The page refreshes every five minutes from `/api/upcoming-events`, a Pages
Function that reads the same public Promoly campaign feed as recondnb.net,
with the owner fixed to 6079. No credentials are required or returned.
Upstream requests are cached for five minutes. Without `id`, the page includes events dated
today or later in America/Denver, matching Recon's homepage date rule, sorted
soonest first. Past events expire while OBS stays open, including when offline.
An unpinned event's flyer expires after its advertised date, on the next
rotation or feed refresh.

The client retains loaded, eligible flyers on feed failures, skips broken
images, retries on the next refresh, and shows black when no events remain.
The API returns only public flyer metadata. Pagination is bounded to ten pages
and fails with 503 rather than publishing a partial list. Invalid individual
campaigns are excluded. The browser never receives the raw campaign response.

`_routes.json` restricts Function execution to the event feed endpoint.
The existing whole-site publication workflow includes Functions during its
Wrangler upload. Overlay or Function changes trigger that serialized workflow
on main, subject to its existing enable gate. Opening a PR does not deploy.

Offline checks: `npm run test:events` (Node 22+, no packages to install), plus the
existing Python suite. The pre-push hook runs both. PR CI also builds Functions.
For local end-to-end inspection, run `wrangler pages dev website/public` from
the repository root and open `/upcoming-events`.

Approved visual reference: [working mockup](https://pages-d52757e2.s3.us-west-2.amazonaws.com/a/76b397bc3d32653cf93aeaf5d2bd6e44/upcoming-events.html).
