# LabelGrid homepage catalog sync

The homepage catalog can be regenerated from LabelGrid without editing release cards by hand. `scripts/sync_catalog.py` reads the authenticated release-list API on the build runner. The browser receives static HTML and never receives the API token. Only the marked catalog region in `website/public/index.html` changes. The rest of the site, RSS feed, and existing cover files are preserved.

## Catalog contract

The generator uses `GET https://api.labelgrid.com/api/public/releases` with `filter[is_live]=1`, `filter[label_id]`, `page`, and `per_page`. This contract was checked against `plushrecs-agent/docs/vendor/labelgrid-openapi.json`, operation `public-releases.index`. The filter is documented as an integer. No release status enum is guessed.

It validates every page and selects the latest 12 explicitly numbered Plush releases dated today or earlier in UTC. Future and undated releases are excluded. Catalog suffixes such as PLUSH120A are supported. Artwork and links come from the API. Existing Bandcamp players are retained through `website/catalog-embeds.json` when the API's Bandcamp URL matches the recorded URL. New releases show their supplied listening links. The API does not supply Bandcamp embed IDs, so players for new releases are optional entries in that mapping, never inferred.

An empty catalog, malformed eligible release, duplicate record, inconsistent pagination, unsafe URL, API failure, or missing HTML markers aborts generation. No partial result is written. The API token is read only from `LABELGRID_API_TOKEN` in the environment. There is no credential-store or `.env` lookup. Raw API responses are not persisted or logged.

## Local use

Python 3.10 or newer is sufficient. Supply `LABELGRID_API_TOKEN` and the confirmed numeric `LABELGRID_LABEL_ID` through the approved runtime environment. Do not paste tokens into commands or repository files.

```sh
python3 scripts/sync_catalog.py          # compare only; no files written
python3 scripts/sync_catalog.py --apply  # replace catalog in this checkout only
```

Use an isolated checkout when generating locally. The command does not commit, push, deploy, update LabelGrid, or write the Plush mirror.

For contributors, the pre-push gate is `.githooks/pre-push`. This repository had no existing hook. Invoke it through Git without changing shared checkout configuration:

```sh
git -c core.hooksPath="$(pwd)/.githooks" push
```

It runs the offline regression suite. The same suite runs in the PR's Catalog checks workflow. Do not bypass the hook or run an identical full suite immediately before pushing.

## Scheduled workflow and activation

`.github/workflows/catalog-sync.yml` is **disabled unless** the repository variable `PLUSH_WEBSITE_SYNC_ENABLED` is exactly `true`. It only runs from `main`. Its daily schedule is 13:23 UTC (06:23 Denver daylight time, 07:23 standard time). GitHub schedules can be delayed and run from the default branch, as described in [GitHub's schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

An enabled scheduled run generates the catalog, tests it, saves a preview artifact, commits only `website/public/index.html` when changed, and uploads `website/public` to Cloudflare Pages project `plushrecs`, production branch `main`. A failed push or validation prevents deployment. A no-change run still deploys so a previous failed deployment can recover. No force push or automatic conflict resolution is used. The upload follows [Cloudflare's direct-upload CI procedure](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/).

Manual dispatch defaults to `publish=false`. It generates and tests in the temporary runner and saves `catalog-preview`, but does not commit or deploy. The same enable gate and environment apply. The preview is a generated HTML page; view it within a copy of `website/public` so relative site assets resolve.

Before activation, the owner must approve these production effects and complete:

1. Verify the account's Plush label ID, live-filter behavior, cover URL longevity/public access, and released metadata through an approved read-only API dry run. Schema-level tests do not establish live account configuration.
2. Configure the `plush-website-production` GitHub environment. Add environment secrets `LABELGRID_API_TOKEN`, `CLOUDFLARE_API_TOKEN`, and `CLOUDFLARE_ACCOUNT_ID`. Scope the LabelGrid token to the label's read access and Cloudflare token to the intended account's Pages deployment permission. Set repository variable `LABELGRID_LABEL_ID` to the verified ID. No credentials are supplied by this change.
3. Verify repository Actions policy permits `contents: write` and the generated catalog commit to `main`. Branch protection may refuse this, in which case stop and decide the authorized publication approach rather than bypass protection.
4. Coordinate with the existing Mac `plushrecs-agent` RSS publisher. Both deploy the **whole site**. Its existing launchd chain is not changed here. Disable or serialize that publisher during cutover and ensure any retained publisher fetches the latest website commit before publishing. GitHub concurrency only serializes this workflow, not Mac deployments. Resolve this before enabling scheduled publication.
5. To preview before production, require owner approval on `plush-website-production`, then enable `PLUSH_WEBSITE_SYNC_ENABLED=true` and manually dispatch with `publish=false`. Scheduled requests will await approval too; approve only the preview run. Inspect its artifact and links. Approve production dispatch only after the preview is acceptable. Decide whether to retain per-run environment approval or remove it for unattended daily publication.
6. Confirm the deployed homepage and an existing Bandcamp player, then monitor workflow failures in GitHub Actions. This workflow sends no outbound messages.

To pause future runs, set `PLUSH_WEBSITE_SYNC_ENABLED=false`. An already-running deployment is not cancelled by changing that variable. Use Cloudflare's previous successful deployment for an owner-approved rollback, and reconcile the source catalog before re-enabling sync.
