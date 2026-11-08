# Issue 32: Four-input parametric bottle dispenser

**Issue:** [#32](https://github.com/Q-Bot2021/fusion360-mcp-server/issues/32)  
**Plan:** [execution plan](../../plans/four-input-parametric-bottle-dispenser.md)  
**Branch:** `tickets/parametric-modeling/Implementation/ticket_32`  
**Status:** Workflow migration verified locally; publication in progress.
Generic tools and CAD remain pending.

## Request and preflight

On 2026-11-08, the user approved extending generic Fusion MCP capabilities to
deliver the bottle dispenser and requested one new project ticket plus migration
of missing SCUBA_Torch ticket behavior into Fusion's AGENTS.md.

Confirmed: assembled 58 mm diameter / 215 mm height bottles, eight bottles,
two tiers, even-tier adjustment, top/front loading and bottom/front delivery,
one solid parametric body, four independent inputs and Bambu P1S manufacture.
Bottle output folder: `C:\GitRepo\Bottle_Dispenser`.

Subsequent user decisions: approve public MCP handler/schema, initialized
protocol and live disposable-Fusion test seams; round requested capacity up to
equal full tiers when bottle count is not divisible by tier count.

- Verified repository remote: `Q-Bot2021/fusion360-mcp-server`.
- Primary `github-secondary` issue creation executed without a user form.
- Created issue database ID `6268658024`; direct remote readback confirmed
  issue #32, exact requested body, open state and ten unchecked criteria.
- Operation marker: `bottle-dispenser-four-inputs-20261108-8e03da83`.
- No parent or blocker is presently established. Related audit issues
  #7/#8/#10/#13/#19/#24 do not constitute dependencies merely by reference.
- Starting branch was `main`. Existing uncommitted edits in
  `plans/fusion-mcp-tool-audit-and-assembly.md` are unrelated and preserved;
  exclude them from this ticket's commits.
- Active Fusion document readback: unsaved `Untitled`, document ID
  `9620705c-4367-433f-ac7f-a5a00ce90008`. No CAD mutation has occurred.

## Workflow migration

The pre-existing Fusion guide already covered issue breadcrumbs, commit/push,
remote readback and resolution. Missing SCUBA_Torch behavior being added:

- Read comments, parent/blocker/dependent relationships and existing branches.
- Trace linked evidence to every acceptance criterion; preserve source ownership.
- Resolve material ambiguity explicitly; separate assumptions from requirements.
- Continue existing ticket branches and validate scoped/category naming.
- Update applicable requirements, architecture/readme, visual and status records.
- Require user acceptance before merge; accepting a partial slice does not
  complete unresolved ticket criteria.
- Verify remote main and agreement of local/remote evidence before closure.

Keep the existing Fusion unit/protocol/live, promotion, generic applicability
and audit-ledger rules. Use the existing audit dashboard, not SCUBA_Torch's
product-specific directory hierarchy or hardware validation requirements.

## Acceptance checklist

This mirrors the remote criterion order; check only with published evidence.

- [ ] Ticket workflow migration and documentation consistency.
- [ ] Published linked execution plan and breadcrumbs.
- [ ] Primary-source bottle/P1S research.
- [ ] Generic backward-compatible expression/driven geometry/pattern support.
- [ ] Unit/protocol tests and updated, regenerated, verified audit ledgers.
- [ ] Exact-revision development-live/production-live acceptance and promotion.
- [ ] One-body four-input CAD with verified independent input/topology changes.
- [ ] Eight-bottle capacity, transfer/access/envelope and P1S slicing evidence.
- [ ] Persistent native source/F3D/STL, notes and visual/health readback.
- [ ] Published evidence, user acceptance and verified merge/issue closeout.

## Validation and blockers

Validation:

- VS Code `runTests` could not discover the Python test file; used the existing
  repository pytest runner instead.
- `uv run --python 3.12 pytest tests/test_instructions_sync.py -q`: 11 passed.
- `git diff --check`: passed.
- Production Fusion active-document read: passed; no modeling mutation.
- Remote issue creation/readback: passed through primary MCP without forms.

Primary-source research is persistent in the separately owned
[bottle project](../../../Bottle_Dispenser/docs/bottle-research.md). It reports
the P1S nominal 256 x 256 x 256 mm volume, assembled bottle shape/variant
considerations and full-drying care guidance. Manufacturer bottle dimensions
were not verified; retain the user's measurements as inputs.

Infrastructure implementation, installed add-in/host reload, live acceptance,
CAD construction, slicing and physical feed testing are not complete. Bottle
rolling/contact shape and usable print envelope remain open questions.
The retained development MCP is not exposed by this client's current tool
discovery; direct visible candidate modeling will require that connection.

## Closeout

No merge approval, resolution comment or final-state verification yet.
Keep the issue open until its acceptance and closeout gates pass.
