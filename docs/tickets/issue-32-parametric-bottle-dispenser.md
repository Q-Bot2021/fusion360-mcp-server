# Issue 32: Four-input parametric bottle dispenser

**Issue:** [#32](https://github.com/Q-Bot2021/fusion360-mcp-server/issues/32)  
**Plan:** [execution plan](../../plans/four-input-parametric-bottle-dispenser.md)  
**Branch:** `tickets/parametric-modeling/Implementation/ticket_32`  
**Status:** Workflow migration published; first parameter-tool candidates passed
unit, initialized protocol and development-live checks. Production promotion,
remaining geometry/pattern work and CAD remain pending.

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

- [x] Ticket workflow migration and documentation consistency.
- [x] Published linked execution plan and breadcrumbs.
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

The user subsequently confirmed the development MCP/add-in are running and
authorized separate disposable test designs. Initialized stdio acceptance
reached the development endpoint successfully. The test runner is development
infrastructure, not a dispenser-modeling orchestration workaround.

## Published tracking milestone

- Published commit:
  [e6cae721afd1f831b85a1c458015583d06431b1a](https://github.com/Q-Bot2021/fusion360-mcp-server/commit/e6cae721afd1f831b85a1c458015583d06431b1a).
- Remote branch hash verified with `git ls-remote`.
- Remote issue readback verified two checked criteria and eight unchecked,
  open state, count-rounding decision and approved test seams.

## Parameter-tool development acceptance

Implemented as development-only candidates; normal production discovery and
dispatch are unchanged:

- `get_design_parameters`: bounded user/model parameter inspection across
  local components, internal numeric values or text readback, expressions,
  roles, API parameter-component ownership and creator-component metadata.
- `set_parameter_expression`: one local numeric user/model expression edit,
  guarded by active document ID, unique name and exact prior expression.
  Validate against declared units before assignment; return actual readback.
  Text/derived edits are rejected. Expression validity is not geometry validity.

Official API sources:
[allParameters](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_Design_allParameters.htm),
[ModelParameter.expression](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_ModelParameter_expression.htm),
[isValidExpression](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_UnitsManager_isValidExpression.htm),
[valueType](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_Parameter_valueType.htm),
[createdBy](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_ModelParameter_createdBy.htm),
[component](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_ModelParameter_component.htm).
The value-type API requires September 2025 or newer Fusion.

TDD tracer failures were observed before implementing inspection, editing,
initialized discovery and creator-ownership metadata. The first live child
test exposed that Fusion's parameter component may be root while the creating
sketch belongs to a child. Preserve that API readback and expose creator
ownership separately; a regression and repeated live run verify the fix.

Verification on Windows, running Fusion **2705.1.25** (executable version):

- Focused unit/protocol/development-registry tests: **53 passed**, four live
  cases deselected (not represented as acceptance).
- Full normal suite after mutation-mirror repair: **787 passed, 181 skipped**.
  Skipped live tests are not live acceptance.
- Full repository `uv run --python 3.12 ruff check`: passed.
- Explicit live command:
  `uv run --python 3.12 pytest tests/test_parametric_parameters_live.py --run-fusion-e2e -q`:
  **1 passed** with XY/root and YZ/child fixtures.
- Live assertions: mm, degree and unitless expression round-trips; model
  dimension binding; box dimensions change from 40 to 42 to 54 mm as specified;
  stale document/old expression, missing names and incompatible angle units
  reject without changed bounds; owning feature health is healthy.
- Restore fixture inputs/model expressions. Separate unsaved test designs
  remain open; no existing user document was cleared, overwritten or saved.
  Retain the reusable development add-in and connection.

Exact-source SHA-256 evidence (runtime reload hashes matched staged handlers):

```text
addon/server/command_handler.py
b6b085624614c8a28e7ca3abba264afe8a7c7f6d1f93e525862df2283c5328c6
addon/server/mechanical_queries.py
2a43cbd5234904aa11f3f209cac086b32547997a2e0b7040b2a94b608c49afab
tests/development_mcp.py
572ad0c0483eacb50ef02545987c2596e04b5892852b7c4deeb6e13327b646c5
tests/test_parametric_parameters_live.py
da1eeabcd7c92508bab55ecc7f9ead310136ba5c1824598bdccfab826c2e4b09
```

The raw report is `.pytest_cache/issue-32-parameter-development-live.json`;
the durable assertions/hashes above record its acceptance scope. Parameter
primitives do not yet create count-driven feature patterns or constrain every
sketch origin. No production promotion/live result or dispenser CAD exists.

## Closeout

No merge approval, resolution comment or final-state verification yet.
Keep the issue open until its acceptance and closeout gates pass.
