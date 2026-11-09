# Issue 32: Four-input parametric bottle dispenser

**Issue:** [#32](https://github.com/Q-Bot2021/fusion360-mcp-server/issues/32)  
**Plan:** [execution plan](../../plans/four-input-parametric-bottle-dispenser.md)  
**Branch:** `tickets/parametric-modeling/Implementation/ticket_32`  
**Status:** Four generic capabilities verified locally and staged into production
with original-file backups. Add-in restart, client reconnection and production
live acceptance remain pending. Dispenser CAD has not yet been created.

## Latest production staging milestone

User approved production promotion. The 0.13.0 registry and explicit add-in
wrappers expose four generic parameter/profile/pattern capabilities; development
discovery reuses their metadata. Public wrappers do not expose the test loader.
Mock solver/history limitations return errors without fabricated mutation deltas.

Verification of this promotion slice:

- Full normal suite: **817 passed, 184 skipped**; skips are not acceptance.
- Explicit combined development-live workflows: **2 passed**, both production
  cases deselected. XY/root, YZ/child and XZ/child cover all local pattern axes,
  negative profile coordinates, signed spacing, quantities 2 -> 1 -> 3 and
  regenerated width/volume/one-solid/feature-health checks.
- Full Ruff checks and `git diff --check` passed. Normal tests include registry
  coverage, 309 advertised-mode inventory, generated-ledger freshness and
  instruction synchronization. VS Code's test tool was unavailable because
  no client was connected; the existing pytest runner was used.
- Supplemental XZ testing initially placed negative-direction copies outside
  the positive-direction connecting spine. Correcting the fixture's spine
  offset established the same independent expected volumes as the other axes.
  Negative `extrude` distance remains unsupported by that existing tool; the
  fixture uses its supported positive extent and an offset spine.
- Generated audit visual inspection remains blocked by the disconnected client.

Before staging, all three installed production files matched repository main
after newline normalization. Exact original hashes were guarded, originals
backed up, then only the handler, mechanical helper and manifest were copied.
Installed SHA-256 readback:

- Handler: `4013383ea7ee2b959859e2da470ec60808aa6c12e3921e2f76411dc74185067f`
- Helper: `eadade258c07358646639e8de14dc15058633d3eac89a6af279bc6597f2c834e`
- Manifest: `c7cf113ba32c893d82226aadb1e54f159eb206c61b619655552e8b49c230f895`

Originals and staging receipt are retained in the session's
`files\production-stage-32` directory. The production add-in has **not** been
restarted. Production live tests and visible client discovery are mandatory next
gates; staged bytes alone do not prove running code. Local mode acceptance stays
bound to published source revision
`d610bd6fa6bb658a9c68a7ad7967e0c468b7b6ed`; both development-live workflows
were rerun successfully after publication. Production live remains pending.

No connected client is currently available for Fusion/GitHub/browser tools;
configured GH_TOKEN/GITHUB_TOKEN fallback environment variables are absent.
Remote checklist synchronization therefore remains pending reconnection.
The existing production connection and retained development add-in are preserved.

## Original request and preflight

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

## Constrained geometry and feature-pattern development acceptance

Implemented two further generic development candidates:

- `draw_parametric_convex_profile`: one fully constrained closed convex region
  in an explicitly selected empty sketch; 3-32 ordered vertices with native
  x/y length expressions. Point coordinates must stay above the caller's fixed
  reference coordinates. Convexity, duplicates, collinearity, references and
  expressions are validated before geometry mutation.
- `pattern_features`: explicitly selected unsuppressed features in their
  owning component, repeated along a local construction axis with native
  quantity and spacing expressions. Quantity is integer 1-1000 and spacing
  nonzero at creation. Future input changes require health/geometry inspection.

The focused live test exposed two independently reproduced API behaviors:
seeding points at the origin infers coincident constraints, and constructing
edges before coordinate dimensions infers redundant constraints. Seed
independent points off-origin, drive them to the exact requested expressions,
then connect existing points. This is initialization only; no residual geometry
offset or fixed vertex is introduced. Removing either precaution reproduced
the over-constraint error; both are exercised by zero-coordinate live fixtures.

Fusion's units manager uses document length semantics with empty validation
units and rejects `"unitless"` as a unit string. Validate/evaluate the quantity
expression multiplied by `1 cm` as a length, then pass the original expression
to the native pattern. This dimensional normalization rejects unitful quantity
expressions while retaining dimensionless named parameter references.

Verification:

- Focused unit/protocol/registry/mutation-sync run: **75 passed**, four unrelated
  live cases deselected.
- Explicit initialized-stdio/development-live run:
  `uv run --python 3.12 pytest tests/test_parametric_geometry_live.py --run-fusion-e2e -q`:
  **1 passed**, with XY/root and YZ/child cases on Fusion 2705.1.25 / Windows.
- Closed profile fully constrained, eight driving coordinates, joined shelves
  remain one solid, count changes **2 -> 1 -> 3**, and width **40 -> 50 mm**
  changes the expected volume. Default inputs restored.
- Rejected fractional/unitful quantities, zero spacing, missing seeds, stale
  document and duplicate pattern name leave bodies, sketches and timeline
  unchanged. Pattern and owning feature health are healthy.
- No dispenser CAD created; disposable unsaved fixtures retained. No existing
  user design cleared, overwritten or saved.

Exact hashes from the successful geometry live report:

```text
addon/server/command_handler.py
bdec3099e1e62b0f5da49427a54837dcad017ee720caa9e58ebe4747597d41f4
addon/server/mechanical_queries.py
9f6ecf4c110ea7bf3fad0bd6f3e384ecd1b375083286365889a165d651152c75
tests/development_mcp.py
af7248cc6c983f0084b1bcbaf7a98d2556d8269c0da782098f73a3a1fc721644
tests/test_parametric_geometry_live.py
80979bd6a89d96e44f6c9b31a880e4f265ac2ec4f8ac556b0e3f55c399ca4903
```

Raw report: `.pytest_cache/issue-32-geometry-development-live.json`.
Production registration/restart/live acceptance and client discovery remain
pending. Generated audit HTML browser inspection was interrupted; freshness
tests passed, but visual inspection is not claimed.

## Closeout

No merge approval, resolution comment or final-state verification yet.
Keep the issue open until its acceptance and closeout gates pass.
