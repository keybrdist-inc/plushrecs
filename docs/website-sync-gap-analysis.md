# Website automatic sync gap analysis

Date: 2026-09-07
Primary issue: https://github.com/keybrdist-inc/plushrecs/issues/11
Status: automatic sync activated and first production deployment verified. No activation blockers remain.

## Current verified state

- The canonical repository is keybrdist-inc/plushrecs. The initial implementation is merged. It adds a LabelGrid catalog generator, preserved Bandcamp mappings, offline tests, and gated daily publication.
- Authorized project credentials identify Plush Recordings as LabelGrid label 2 and confirm the Cloudflare plushrecs project serves about.plushrecs.com. The shell-exported credentials belonged to different access scopes and were not provisioned.
- LABELGRID_API_TOKEN, CLOUDFLARE_API_TOKEN, and CLOUDFLARE_ACCOUNT_ID are configured in GitHub environment plush-website-production. LABELGRID_LABEL_ID=2 is configured. Secret values were not printed or stored in reports.
- A read-only live request returned 136 rows. Legacy HTTP or placeholder links in 21 historical entries exposed validation occurring before homepage selection. The correction validates pagination, IDs, duplicate catalogs, and dates across the response, then validates public metadata/HTTPS links only for the selected 12 entries. LabelGrid records are unchanged.
- The corrected generator produced a live preview of 12 released Plush entries. All 12 cover URLs returned HTTP 200 with browser request headers. Four existing Bandcamp player URLs match current LabelGrid data, and the tested player returned HTTP 200. Default Python user-agent requests encountered Cloudflare 1010 filtering, not missing artwork.
- PLUSH_WEBSITE_SYNC_ENABLED=true is configured. GitHub preview run 34161818604 passed, followed by production run 34161867924. The Mac publisher segment is removed, PLUSH_RSS_PUBLISH_ENABLED=0, and the admin job remains loaded on its original 10800-second interval with RunAtLoad=false. Reload caused no immediate admin execution.

## Action ledger

- A1 done: source/API contract discovery and duplicate search.
- A2 done: owner confirmed repository and homepage scope.
- A3 done: initial implementation merged, including the reviewed closing-marker indentation fix.
- A4 done: owner-authorized cutover removed only the Mac RSS publication segment and retained the admin job schedule. The GitHub publisher is enabled without per-run approval gates.
- A5 deferred: the agent installer omits the --bandcamp flag required by its RSS runbook. This separate source-code fix is unnecessary for cutover because that publisher will be disabled.
- A6 done: authorized credential validation, GitHub secret provisioning, and confirmed label ID.
- A7 done: follow-up PR https://github.com/keybrdist-inc/plushrecs/pull/13 merged after all 19 pre-push tests and final-head CI passed. Copilot's documentation consistency finding was fixed, replied to, and resolved. Final sweep found no outstanding findings.
- A8 done: runner preview matched the local verified preview; production deployment succeeded and the custom-domain catalog matched the artifact. Daily cron is 23 13 * * *, or 07:23 Denver daylight time / 06:23 standard time.

## Deployment evidence and operating limits

- Preview: https://github.com/keybrdist-inc/plushrecs/actions/runs/34161818604 (success; commit/deploy steps skipped).
- Production: https://github.com/keybrdist-inc/plushrecs/actions/runs/34161867924 (success).
- Generated catalog commit: 72f5215f73543e9b71057011b4ef51987bea092a.
- Cloudflare production deployment: 8ff3fb9c-959d-4581-9930-f0a92f3e48ec, associated with that exact commit; latest deployment stage succeeded.
- https://about.plushrecs.com/ returned HTTP 200 and its catalog region exactly matched the validated artifact (12 cards, including PLUSH128).
- GitHub main is unprotected and the workflow's contents: write permission successfully pushed the generated catalog. Environment secrets and label ID were verified by the successful runner, without exposing secret values.

The daily trigger is enabled but its first scheduled firing has not occurred yet; initial verification used workflow_dispatch through the same generation/commit/deploy path. GitHub scheduling can be delayed.

The old Mac publisher is disabled to prevent competing whole-site uploads. Website RSS feed updates are paused; its existing feed remains published. Local RSS generation remains available separately. Restoring automatic RSS publication is a separate coordinated follow-up, not an activation blocker for homepage sync.

## Review and policy evidence

The initial Kody request received no response in its two delayed polling windows. Copilot subsequently reviewed the initial implementation; its single finding was fixed, replied to, and resolved. The follow-up requested Kody once and explicitly requested the already-available Copilot reviewer. The first five-minute poll found Copilot's completed review with one documentation finding and no code findings.

Repository-specific policy calibration is unavailable. The owner explicitly authorized delivery using the manual assessment and later authorized fixes and activation for this session. This is not a policy-check pass; no global policy files were changed. The changes generate public output from read-only API data, keep tokens on the build runner, and retain an explicit publication gate.
