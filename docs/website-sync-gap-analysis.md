# Website automatic sync gap analysis

Date: 2026-09-07
Primary issue: https://github.com/keybrdist-inc/plushrecs/issues/11
Status: implementation in progress; production activation held.

## Verified scope

The homepage contains hardcoded release cards. The existing agent RSS publisher updates feed.xml and covers, then deploys the whole site, but does not regenerate the homepage catalog. The owner confirmed homepage catalog sync and keybrdist-inc/plushrecs as the canonical repository. This change corrects stale project.yml routing accordingly.

The LabelGrid release-list OpenAPI contract supports integer filter[is_live], filter[label_id], and paginated data/meta. Public rendering uses cat, title, default_display_artist, release_date, front_cover.url, and supplied store URLs. No release status enum or catalog number is inferred. The generator validates the complete response before replacing the marked homepage region. Existing known Bandcamp players are retained through a checked-in mapping.

## Remaining gaps

- Live LabelGrid behavior and account configuration are unverified. No credentials or authenticated API responses were accessed. Validate the label ID, live filter, metadata, and public cover URLs before activation.
- The existing Mac RSS publisher deploys the entire site from a different checkout. Coordinate or pause it before activating this workflow to avoid overwriting a fresh catalog with stale HTML. This change does not modify that job.
- GitHub Actions secrets, environment protections, permission to commit generated output to main, and Cloudflare deployment credentials require owner setup/verification. The enable variable defaults off.
- New Bandcamp embed IDs are not supplied by the API. New releases use supplied listening links until an exact player mapping is provided.
- The agent runbook requires --bandcamp in its RSS chain but the inspected installer omits it. That adjacent behavior fix is deferred to the agent repository.

## Action ledger

- A1 done: read-only discovery using smaller-model scouts, source/schema verification, and duplicate searches.
- A2 done: canonical repository and homepage scope confirmed by owner.
- A3 in progress: created and assigned issue 11 before creating isolated feature/#11-website-sync worktree. Implementation, pre-push gate, PR, and review loop are the current delivery item.
- A4 paused-for-HITL: merge, production activation, live account verification, and coordination with the old publisher. Complete the activation procedure in website-sync.md after approval.
- A5 deferred-why: RSS --bandcamp discrepancy belongs to a separate repository and is outside this homepage implementation.

## Validation

GitHub workflow syntax passes actionlint 1.7.12. Offline pre-push regression tests and PR review results will be recorded here before handoff.
