# Website automatic sync gap analysis

Date: 2026-09-07
Primary issue: https://github.com/keybrdist-inc/plushrecs/issues/11
Status: generator corrections and live preview validated; GitHub runner preview and production cutover remain pending.

## Current verified state

- The canonical repository is keybrdist-inc/plushrecs. The initial implementation is merged. It adds a LabelGrid catalog generator, preserved Bandcamp mappings, offline tests, and gated daily publication.
- Authorized project credentials identify Plush Recordings as LabelGrid label 2 and confirm the Cloudflare plushrecs project serves about.plushrecs.com. The shell-exported credentials belonged to different access scopes and were not provisioned.
- LABELGRID_API_TOKEN, CLOUDFLARE_API_TOKEN, and CLOUDFLARE_ACCOUNT_ID are configured in GitHub environment plush-website-production. LABELGRID_LABEL_ID=2 is configured. Secret values were not printed or stored in reports.
- A read-only live request returned 136 rows. Legacy HTTP or placeholder links in 21 historical entries exposed validation occurring before homepage selection. The correction validates pagination, IDs, duplicate catalogs, and dates across the response, then validates public metadata/HTTPS links only for the selected 12 entries. LabelGrid records are unchanged.
- The corrected generator produced a live preview of 12 released Plush entries. All 12 cover URLs returned HTTP 200 with browser request headers. Four existing Bandcamp player URLs match current LabelGrid data, and the tested player returned HTTP 200. Default Python user-agent requests encountered Cloudflare 1010 filtering, not missing artwork.
- The Mac admin job is loaded and currently contains the old whole-site RSS publisher. PLUSH_WEBSITE_SYNC_ENABLED remains false during preparation. No GitHub sync/deploy workflow has been dispatched yet.

## Action ledger

- A1 done: source/API contract discovery and duplicate search.
- A2 done: owner confirmed repository and homepage scope.
- A3 done: initial implementation merged, including the reviewed closing-marker indentation fix.
- A4 in progress: owner authorized setup and production activation. Cutover will remove only the Mac RSS publication segment, retain the admin job's 10800-second schedule, and reload without immediate execution before enabling the GitHub publisher.
- A5 deferred: the agent installer omits the --bandcamp flag required by its RSS runbook. This separate source-code fix is unnecessary for cutover because that publisher will be disabled.
- A6 done: authorized credential validation, GitHub secret provisioning, and confirmed label ID.
- A7 review close-out: follow-up PR https://github.com/keybrdist-inc/plushrecs/pull/13 corrects selection-before-public-field-validation. All 19 pre-push tests and code-head CI passed. Copilot reviewed the code and raised one documentation consistency finding, corrected here; thread resolution and final-head CI are verified in the session handoff.
- A8 pending: GitHub runner preview, publisher cutover, initial production sync, and verification of the daily schedule.

## Remaining activation checks

Run the workflow with publish=false and inspect its artifact. Confirm GitHub can push the generated catalog and Cloudflare can deploy from that runner. The main branch is unprotected; the workflow requests contents: write. Validate the deployed homepage after the first production run.

Both publishers upload the whole site. Remove the Mac RSS publication step before enabling unattended GitHub publication. This pauses website RSS feed updates; its existing feed remains published. The admin sweep, LabelGrid refresh, and Drive mirror steps remain scheduled. Local RSS generation remains available separately.

## Review and policy evidence

The initial Kody request received no response in its two delayed polling windows. Copilot subsequently reviewed the initial implementation; its single finding was fixed, replied to, and resolved. The follow-up requested Kody once and explicitly requested the already-available Copilot reviewer. The first five-minute poll found Copilot's completed review with one documentation finding and no code findings.

Repository-specific policy calibration is unavailable. The owner explicitly authorized delivery using the manual assessment and later authorized fixes and activation for this session. This is not a policy-check pass; no global policy files were changed. The changes generate public output from read-only API data, keep tokens on the build runner, and retain an explicit publication gate.
