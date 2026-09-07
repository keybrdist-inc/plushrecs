# Website automatic sync gap analysis

Date: 2026-09-07
Primary issue: https://github.com/keybrdist-inc/plushrecs/issues/11
Status: PR open; Copilot review received and its single finding fixed. Final thread and CI verification are recorded in the session handoff. Production activation held.

PR: https://github.com/keybrdist-inc/plushrecs/pull/12

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
- A3 review fix prepared: PR 12 received a completed Copilot review with one finding after the initial Kody wait. The generator now preserves closing-marker indentation, with a regression test for exact suffix preservation and repeated generation. Final thread resolution and current-head CI status are verified at handoff.
- A4 paused-for-HITL: merge, production activation, live account verification, and coordination with the old publisher. Complete the activation procedure in website-sync.md after approval.
- A5 deferred-why: RSS --bandcamp discrepancy belongs to a separate repository and is outside this homepage implementation.

## Validation

GitHub workflow syntax passes actionlint 1.7.12. All 16 offline regression tests passed through the pre-push hook. Local structural review found no remaining critical defects after fixing embed-map lookup/rendering and API validation. No live API or production smoke test ran.

The required policy checker reported: `policy: missing or unreadable escalation matrix: /Users/keybrdistt/.claude/skills/llm-autonomy-policy/escalation-matrix.plushrecs.md`. No Plush calibration was found in the Codex/Claude skill locations or shared skill source. This is an unavailable policy verdict, not a policy pass. The owner explicitly authorized continuing with this documented manual assessment. The policy verdict remains unavailable; no calibration files were changed.

Manual risk assessment: this adds API-authenticated catalog generation and gated production publishing. PR checks have no deployment credentials. The shipped enable gate is off unless explicitly configured. No production effects occur from the local implementation. Activation still needs owner approval, live API verification, and publisher coordination. No changes were made to global policy files.

## External review ledger

- Review requested once with `@kody start-review` at 2026-09-07T18:55:40Z, after checking all three GitHub review surfaces and finding no review-bot activity.
- Immediate confirmation: request comment 5574642463 exists on PR 12.
- Delayed poll 1 at 19:00:57Z: only the request comment exists; no inline findings or reviews.
- Delayed poll 2 at 19:06:05Z: unchanged; no reviewer acknowledgement, inline findings, or reviews.
- Outcome: PENDING, not approval. The allowed two-poll window is exhausted. No repeated trigger or speculative reviewer mention was posted. An available reviewer or human review is needed to close the review loop.
- A final documentation-only commit records this ledger; no runtime code changed after the successful code-head CI check. Its pre-push/CI result is reported with the session handoff.

## Copilot follow-up

Copilot reviewed commit 927560dc460b6995004fda045d6ef17b984258e4 and reported one inline finding (comment 3952188822). The replacement function discarded indentation immediately before the closing catalog marker. The fix retains whitespace on a standalone closing-marker line while keeping existing inline-marker behavior, and adds an exact-output/idempotence regression test. The original unanswered Kody request is retained as historical evidence; no duplicate trigger is needed now that a completed reviewer report is available.
