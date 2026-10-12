# Mechanical and Drawing Coverage

## Coverage Inventory

[Open the HTML audit ledger](audit-ledger.html) for tool-by-tool checks, recorded
acceptance gates and development-only entries. It opens directly in a browser,
without a server or network access. Crosses mean unconfirmed or ineligible, not
necessarily failed. Missing gate records remain unrecorded even when another
ledger marks a generic scope accepted.

After editing the authoritative TSV files, regenerate the snapshot with:

```text
python -m scripts.audit_mechanical_api docs/mechanical/audit-ledger.html --html
```

The test suite enforces snapshot freshness and agent-instruction synchronization.

[Generic-tool audit](generic-tool-audit.tsv) tracks every active production tool.
`accepted_scope` refers to documented representative unit/protocol/live evidence,
not a claim of support for all possible entities. `development_accepted` means a
repair is tested locally but its production acceptance is pending.
`review_required` means generic applicability has not been certified; it is not
a finding that the tool is broken. Existing tools remain registered. Registry
coverage tests prevent newly added tools from disappearing from this audit.

The current legacy slice fixes nested-body/component-sketch `get_object_info`
and `get_scene_info` now enumerates root and nested body instances with occurrence
paths, plus sketches by owning component. It rejects ambiguous names in shared
body/component resolution. Object queries
can specify type, full occurrence path (`root` for root bodies), or sketch owner
component. Missing objects retain `found: false`; ambiguous names raise an error.
Development tests verify duplicate-name rejection, explicit target readbacks,
unchanged geometry after an ambiguous move, and successful movement of a unique
nested body. Production acceptance passed after the Fusion add-in restart: the
live MCP case verified root and nested body inspection, component sketch
inspection, scene occurrence paths, ambiguous-target rejection and a valid
nested-body move with expected assembly-coordinate bounds. Evidence:
`.pytest_cache/object-inspection-production-live.xml` and
`.pytest_cache/object-inspection-production-*/report.json`.

The component-local sketch slice now includes `create_sketch` and the rectangle,
circle, line, arc, spline and polygon drawing tools. Their optional
`component_name` and named `sketch_name` target a uniquely resolved component's
sketch-local frame; legacy root/latest-sketch defaults remain for callers that
omit selectors. Initialized MCP protocol cases cover the wider sketch-operation
family. A development live fixture exercised six drawing primitives, constraints,
dimensions, offset/trim/extend, projection, revolve, sweep and loft on an explicit
YZ-oriented component sketch (71 recorded calls). The report is
`.pytest_cache/generic-geometry-development-20261011_151031/report.json`.
`auto_constrain` is excluded from passing live evidence because Fusion returned
`AutoConstrain is not available since user is restricted`; track it as a blocked
prerequisite. Combined-fixture renders are not claimed as sufficient visual
review for every primitive. Updated production add-in source is staged, but the
loaded Fusion handler still rejected `component_name` on `create_sketch`;
production live acceptance remains pending a Stop/Run of the production add-in.

Appearance assignment now validates body/component/face targets before copying
library appearances into the design; unsupported types and face indices fail
before any library mutation. Unit, initialized-MCP and development live checks
cover valid assignment, invalid type/index and ambiguous target rejection without
appearance-library access. Production live verifies the invalid/ambiguous target
preflight without loading or mutating library appearances. A valid assignment
attempt using the documented `Aluminum - Anodized Red` example was rejected as
absent from the installed library before any appearance copy; valid assignment
acceptance remains pending until an available appearance can be identified.
The shared-lookup live matrix also verifies unchanged
geometry after ambiguous mutators and a successful uniquely named nested-body
move. These checks do not establish
full successful modeling, sheet-metal or manufacturing acceptance for every
affected tool; generic scope remains `review_required` until separately verified.

[capability-coverage.tsv](capability-coverage.tsv) accounts for all 11,053 indexed
methods/properties in `adsk.fusion` and `adsk.drawing`. It does not include CAM,
electronics or unrelated core UI APIs. Required core document/export integration
must be added explicitly when designing a workflow. This is an implementation
backlog, not a claim that all those members are callable through MCP.

The audit scans active handler bodies for attribute names. A match yields
`receiver_review_required`, not assigned/covered: `add`, `name`, `item` and other
common members are ambiguous. No match yields `unassigned_review_required`, not
proof of absence: shared helper calls may contain the actual API use. Review
qualified receiver types, schema arguments and operation semantics before mapping
members to tools. Type/collection utilities should usually be grouped into tools
or resources, not thousands of independent public wrappers. Generic reflection,
arbitrary property setters and Python execution are not permitted.

```text
uv run --python 3.12 python -m scripts.audit_mechanical_api docs/mechanical/capability-coverage.tsv
```

The audit replaces its conservative baseline. Keep separately reviewed assignment
and acceptance evidence before regeneration. The pointer index supplies URLs;
fetch official member documentation on demand and verify installed version,
preview status, signature, units, prerequisites and lifecycle.

## Initial Development Candidates

| Tool | Resource | Unit/Protocol | Live | Production |
| --- | --- | --- | --- | --- |
| `get_feature_health` | `fusion360://development/feature-health` | Passed | Passed on named 20 mm parametric box | Promoted; resource remains development-only |
| `get_drawing_info` | `fusion360://development/drawing` | Passed | Passed on sandbox drawing after adapter repair | Unregistered; checked drawing API is preview |

The named fixture `MCP_FeatureHealth_Box` was created through the existing
`create_box_parametric` tool. Live tool/resource agreement was verified against
its `Extrude1` feature: healthy state 0, empty warning message. Evidence is
[feature-health-live.json](evidence/feature-health-live.json). At this checkpoint,
the source document was still unsaved; this is not cloud persistence acceptance.

## Authorized Sandbox Lifecycle Candidates

`create_design` creates and activates a separate empty, unsaved Fusion
design. The generalized source contract accepts an explicit nonempty name
(1-100 characters, no path separators or control whitespace), without requiring
a cloud project or test-fixture prefix. The generalized helper is installed and
was invoked successfully through production geometry and save acceptance.
Unit coverage separately verifies ordinary names and absence of cloud-project
access. Earlier production acceptance used the restricted fixture contract.
Creation does not save into any cloud project.
Existing documents are not closed, cleared, or saved. Feedback on an existing
design must be handled in place, not by calling this tool for a replacement
without explicit approval.

Release `0.4.0` registers this tool in production, with the same definition and
unlabeled production handler in the development profile. Dedicated unit/protocol
checks cover name
guards, failed creation without retry, and creation without an active document.
Live acceptance checks invalid-input state preservation, new document identity,
unsaved state, and an empty scene. Run
`tests/test_development_registration.py::test_create_new_fusion_design_live`
with `--run-fusion-e2e`; exact-source hashes and results are recorded in
`.pytest_cache/new-design-production-live.json` and
`.pytest_cache/new-design-development-live.json`. Production acceptance of the
renamed dispatch passed after staging and restarting the production add-in:
discovery, invalid-name state preservation, new document identity, unsaved state,
zero bodies/sketches/features/timeline entries, and no development response label.
Development was disabled during this production verification. The empty unsaved acceptance document is
retained for inspection; this test does not close or save any document.

The user authorized creating/saving verification designs in `MCP_Dev`. Added
development-only `get_document_state` (also resource
`fusion360://development/document`), `save_sandbox_design`,
`create_sandbox_drawing`, and `open_sandbox_drawing`. Their unit/protocol checks
pass; live save, creation and open phases were observed successfully, with final
drawing tool/resource acceptance passing after the adapter repair described below.
`get_document_state` is promoted after successful core-API unit/protocol and live
identity readback. Its document resource remains development-only. Other lifecycle
tools remain development-only because the revised save path lacks a clean live
acceptance run and drawing-dependent APIs are preview.

## Production Promotion

### Generic Candidates

Release `0.9.0` registers component-local `draw_sketch_text` and
`extrude_sketch_entities`, explicit-index `chamfer_edges`, and paginated
`get_body_topology`. Edge indices must be inspected again after geometry changes;
each chamfer edge has an adjacent reference face and two distances in centimeters.
Body names must be unique; an optional full `occurrence_path` (or `root`) selects
the intended instance explicitly. The stencil-specific selector is not a generic
production candidate and remains development-only.

`save_design` requires the inspected active document identity. First save requires
a bounded name and either an accessible project ID or a unique project name;
the destination is that project's root folder, with duplicate-name rejection.
For an already-saved document, omit the name/project to save a new version in
place. Accepted saves with pending cloud metadata require read-only inspection,
not another save call. The legacy sandbox saver remains development-only during
transition. Development acceptance passed for XY/root and YZ/component text,
positive text cut/join, negative profile new-body extrusion, explicit chamfers,
paginated topology, first save, and an in-place saved-document version. Reviewed
outward-facing renders show single-line labels clear of the chamfer. Production
registration uses neutral metadata and shared production handler routes in both
profiles. After production installation and restart, the production-only geometry
and save acceptance tests passed (two cases). Reports are under
`.pytest_cache/generic-geometry-production-*` and
`.pytest_cache/generic-save-production-*`, with JUnit results at
`.pytest_cache/generic-production-live.xml`.

Production renders after extrusion and chamfering were visually reviewed for
both root XY and component YZ sketches: labels are single-line and readable,
without clipping, overlap or missing glyphs. Placement-only outward views were
occluded by the fixture plate and are not evidence of visible sketch placement.
The save test verified the same cloud file identity after an in-place version
save. Disposable acceptance designs and evidence are retained; no existing user
design was cleared or replaced.

This verifies these registrations, not generic compliance of the entire legacy
registry. The broader audit remains open, including root-only `get_object_info`
and first-match body lookup in older tools. The specialized stencil selector,
legacy sandbox saver, preview drawing tools and fixed reload maintenance command
remain development-only.

The legacy `mirror` tool now accepts an optional full `occurrence_path` for a
named nested body; the default root-body-index behavior is unchanged. Unit,
mock, protocol and live production checks pass after the add-in restart. The
production validation created a nested component body, used the returned
`occurrence_path` from `get_scene_info`, and confirmed the mirrored body count
increased by one without error.

The legacy `fillet` and equal-distance `chamfer` tools now accept bounded
explicit edge indices plus an optional full occurrence path, and create features
in the selected body's owning component. Their `top`/`bottom`/`vertical` options
remain world-Z compatibility selectors, not the generic path. Unit, protocol and
development and production live checks passed on root XY and rotated component
YZ bodies with volume-change assertions. Fresh production evidence is in
`.pytest_cache/generic-geometry-production-20261011_204850/report.json`; the
paired development report is `generic-geometry-development-20261011_204832`.
The initialized-MCP run passed both cases (JUnit: `remaining-geometry-live.xml`).
It also verified projection, revolve, sweep and loft in their component contexts.
Current component text captures are misframed and are not new visual acceptance;
prior reviewed text evidence remains separate from these geometry assertions.

The legacy `shell` tool now accepts explicit current `face_indices` and an
optional full occurrence path. `get_body_topology(entity_type="faces")` provides
paginated face bounds, area and surface type so callers can choose faces without
assuming world-Z top/bottom. The old top/bottom selector remains a world-Z
convenience. After the add-in restart, the production live test selected a face
from a YZ-oriented component body, invoked `get_body_topology`, ran `shell`, and
confirmed the volume shrank while removing one face.

### Remaining Primitive And Parameter Audit

Production initialized-MCP acceptance now includes seven root-owned primitive
cases: translated box, X/Z cylinders, two spheres and X/Z tori. Bounds and volumes
match analytic expectations; renamed targets remain queryable, absent bounds
return `found: false`, and missing physical-property targets return errors without
changing body counts. These tools remain under generic review: the primitive
contracts do not select a component and this run does not establish that scope.

Three parameter lifecycles verify millimeters, degrees and unitless values,
duplicate-name rejection, updates in declared units, deletion and missing-name
rejection. JUnit evidence is `.pytest_cache/remaining-primitives-parameters-live.xml`
(10 passed); per-case source/installed hashes and calls are in `primitive-*` and
`parameter-production-*` report folders. Parameter/schema/mock regression tests
passed (263 cases). The follow-up `.pytest_cache/remaining-parameters-both-live.xml`
passed all six mm/deg/unitless lifecycles in development and production. Parameter
unit tests now also execute empty/populated inventory and deletion handlers,
including missing-target and API-exception paths (38 passed). `get_parameters`
is accepted for design-wide user-parameter inventory. Mutation tools remain under
review for wider input boundaries, referenced-parameter live behavior and the
unchecked `deleteMe` false-return path; no production code was changed.

Root and YZ-component query acceptance passed in both profiles (two cases,
`.pytest_cache/remaining-component-queries-live.xml`). Named body/component bounds,
analytic box volume and center, nested renaming, component inventory, parametric
design type, document identity and feature-health pagination are verified.
Rejected missing-component and missing-body requests leave geometry unchanged.
Feature health is accepted for explicit component feature inventory. Remaining
query/rename unit gaps, name collisions, empty component bounds, repeated-instance
paths and direct-mode design-type checks remain pending.

Solid operation production probes (`.pytest_cache/remaining-solid-live.xml`)
passed ten cases and failed four. Root/child join, cut and intersect match
analytic overlap volumes; XY/YZ splits increase body count and conserve summed
volume. These successes are not complete unit/development acceptance.
Uniform scale fails with `invalid ref point`; nonuniform scale calls
`ScaleFeatures.createInput` with too many arguments. Every mutation error has a
saved post-error scene and was not blindly retried. Scaling remains unaccepted;
production source/installed code has not been changed to conceal these failures.

The scale repair is development-accepted, not production live accepted. It uses
a retained hidden 3D sketch point as the reference entity, owned by the selected
solid body's component. World anchor coordinates are transformed into that
component; nonuniform factors use its local axes. Factors must be finite and
positive, all nonuniform factors must be supplied, and direct-history designs
are rejected before mutation. Unit and initialized-protocol tests pass; eight
root/child XY/YZ off-origin anchor cases verify bounds and volume in development
(`.pytest_cache/scale-development-anchors.xml`). The production add-in still runs
the old handler until a reviewed installation and Stop/Run.
Revision `0.9.7` now stages only the repaired `scale_body` method in the existing
production handler file, preserving the installed helpers. The final development
run passed all eight cases (`scale-development-final.xml`), and installed syntax
checks pass. Production live acceptance remains pending an actual add-in restart;
schema/mock/source changes alone do not reload Fusion's in-memory handler.
After the reported production restart, all eight production scaling cases passed
(`.pytest_cache/scale-production-restart-current.xml`): root/child XY/YZ solids,
off-origin world anchors and uniform/nonuniform volume/bounding-corner checks.
Scaling is accepted for its documented parametric solid-body scope.

### Timeline And Design-Type Audit

Surface tools remain registered as requested, with failed acceptance visible;
leaving registrations in place does not make the surface candidate deployable.
The next audit slice passed four development/production workflows
(`.pytest_cache/remaining-timeline-live.xml`): suppression/restoration of a box
extrusion preserves volume, missing feature names are rejected, and empty designs
switch between direct/parametric modes with no-op and invalid-value checks.
Document identity is unchanged throughout. Five real-handler design-type unit
cases also pass. `get_design_type` is accepted for mode inspection. Suppression
name uniqueness/component tests and populated history-loss consent for
`set_design_type` remain pending; these mutations are not generically accepted.
Construction probes (`.pytest_cache/remaining-construction-live.xml`) passed six
cases: YZ offset and XY angled planes, plus plane-intersection axes, in both
profiles. Timeline growth and unchanged body geometry/document identity were
checked; geometric plane/axis parameters and other methods remain unverified.
Two-point axes using raw `Point3D` values failed in both profiles with Fusion's
`InternalValidationError`. Post-error scenes were captured, with no blind retry.
Neither construction tool is promoted to complete generic acceptance.
Distance/color probes (`.pytest_cache/remaining-inspection-live.xml`) produced
four scoped color-assignment passes and six distance failures. Distance used
nonexistent result fields and root-only body lookup. The development-only query
repair uses installed-API `positionOne`/`positionTwo`, the unique body resolver
and finite three-coordinate point validation. Six unit cases, initialized MCP
protocol checks and all three known-distance development cases pass
(`.pytest_cache/distance-development-repair.xml`). Production remains unchanged
and failed until separately staged/reloaded/tested. Color assignment has not
received visual/readback, reuse or unit acceptance and stays under review.

### License-Gated Tools

`auto_constrain` is the confirmed account-entitlement blocker in this audit:
Fusion denied the restricted test account even though the API was installed.
Its handler docstring and client-visible MCP description now identify this
restriction and retain availability for eligible licensed users. The exact
subscription tier is unverified. Other prerequisites, geometry failures and
untested CAM tools are not labeled paywalled without supporting evidence.

Production pattern acceptance passed six root/child cases
(`.pytest_cache/remaining-patterns-live.xml`). Rectangular patterns have six
copies with the requested world-X/Y spacings and equal volumes. Full-circle
X/Z patterns have four distinct equal-volume copies with invariant axial centers.
These are scoped live results, not complete acceptance: unit/development gates,
input boundaries and partial-angle cases remain pending.

Surface probes found valid XY/YZ patch creation (area 6 cm2, zero volume) and
stitching of adjacent patches (one body, summed area 12 cm2). Positive thickening
passed. Negative and symmetric requests incorrectly thicken on the positive side:
the old handler ignores the sign and sends its symmetry flag as chain selection.
The development-only repair is unit-tested and undergoing live geometry checks.
Ruled-surface probes fail at the input signature: Fusion requires an edge profile,
distance, angle and rule type, not the raw edge and distance currently supplied.
Reports: `remaining-patch-live.xml`, `remaining-surface-workflows-live.xml` and
`remaining-surface-entry-live.xml` in `.pytest_cache`. None of the failed surface
contracts is accepted; production surface methods remain unchanged.
Development thickening now passes positive/negative XY/YZ directions, but
symmetric requests still produce twice the intended total thickness after input
setters. `thicken-development-directions.xml` records four passes and two failures.
The symmetric candidate remains unaccepted, and neither it nor the ruled-surface
repair has been staged in production. Useful failing fixtures/reports are retained.
The third development probe uses explicit centimeter expressions and per-side
distance; symmetric geometry still doubles the requested total thickness
(`.pytest_cache/thicken-development-explicit-units.xml`: four passed, two failed).
Further edits to this handler are paused for review rather than applying an
unexplained correction factor. Full deployment remains blocked by the unresolved
surface contracts and missing tool-specific acceptance, even though scaling has
fresh production acceptance and licensing caveats are now documented.

### STEP Export Repair

`export_step` exports one named body, including nested component bodies. Autodesk
documents `Component` as the supported STEP geometry input; the previous handler
incorrectly supplied a body or occurrence, ignored the export success result,
and failed for filename-only paths. The repaired handler copies the body into
an owned disposable direct-design component, exports it, closes only that
temporary document and reactivates the source. It never changes sibling visibility.

Explicit home-relative paths are expanded, relative paths resolve in Fusion's
working directory, and success requires a nonempty output file. Existing output
paths are rejected to avoid accidental overwrites. Mock results carry
`simulated: true` and are not filesystem evidence.

Unit regressions and MCP request-handler tests pass. Development live acceptance
uses root and nested bodies, verifies unchanged source identity and geometry
counts, and reads each STEP with OpenCascade to compare solid count, bounds and
volume. Install the optional `step-validation` dependency group to repeat
`tests/test_sandbox_live.py::test_step_export_live` with `--run-fusion-e2e`.
Production installation and add-in restart are complete. Production-only live
acceptance passed for the root body and a YZ-oriented component body with an
unrelated sibling. Independent STEP reading verified one solid per export,
matching dimensions and volume, and unchanged source document identity and
geometry counts. Reports under `.pytest_cache/step-acceptance-production-*`
record source and installed-handler hashes, calls and exported file paths;
`.pytest_cache/step-export-production-live.xml` records the passing live test.

Release `0.3.0` adds two verified read-only production tools: `get_feature_health`
and `get_document_state`. Definitions, annotations, mock handlers and add-in
dispatch are registered together. Production results omit development-only
markers; development discovery reuses production definitions without duplicates.
Installed production source was hash-checked against its prior revision, updated,
and activated through the existing fixed handler-refresh maintenance command.
Live production discovery and document-state readback passed. The feature helper
has passing development live evidence and production unit/protocol wrapper tests;
its final production-context check awaits the CAD fixture in the foreground.
See [tool-status.tsv](tool-status.tsv) for individual promotion/test statuses.
`dev_reload_candidates` remains development infrastructure, not a production tool.
`get_drawing_info`, `create_sandbox_drawing` and `open_sandbox_drawing` remain local
preview candidates, regardless of successful live tests. `save_sandbox_design`
awaits clean acceptance of the corrected metadata-pending path.
No resource URIs were promoted in this change. The remaining per-member API
coverage backlog is not implied complete by this promotion.

### Live Sandbox Findings

Saved design: `MCP_FeatureFixture_20261010_181017`, containing the named parametric
20 mm box, in `MCP_Dev`. Created and opened drawing:
`MCP_FeatureFixture_20261010_181017 Drawing`, also in `MCP_Dev`.
The active sheet and `adsk::drawing::Drawing` object identity were read through
the MCP tool and matching resource, and their responses agreed.
Evidence: [creation/open phases](evidence/sandbox-drawing-phases.json) and
[passing drawing inspection](evidence/drawing-info-live.json).

The original lifecycle test did not pass end-to-end: the immediate post-save
`DataFile.parentProject` read failed while cloud metadata settled, although the
save had succeeded. A later read verified the saved destination, so save was not
repeated. The helper now distinguishes accepted save with pending readback from
a failed save; callers must query state rather than retry mutation.
The initial drawing inspection then failed in the native `Drawing.productType`
adapter. The repaired query reports documented `objectType` instead and passed
the explicit read-only live test. These are observed native failures, not claims
that all versions behave the same. The historical phase artifact intentionally
retains its incomplete workflow status; separate passing readback is not used to
rewrite that original run as green. A clean all-in-one run remains pending.

Save requires the inspected unsaved document identity, a new `MCP_` name and a
uniquely identified accessible `MCP_Dev` destination. It rejects existing names,
saved source documents, arbitrary paths and stale identities. Drawing creation
requires a fully uploaded saved Fusion design in that project and uses documented
preview `DrawingManager.createDrawingInput` / `createDrawing`. Returned project
identity is checked. Opening is restricted to the returned root-folder drawing.
These are distinct calls and are never retried automatically after sending.

The explicit live workflow is
`tests/test_sandbox_live.py::test_save_fixture_create_and_open_drawing`, selected
with `--run-fusion-e2e`. It records each phase in
`.pytest_cache/sandbox-drawing-live.json` before proceeding. On errors, inspect
the design/cloud project before any retry. Upload readiness failures are not
resolved by a blind repeat of the creation call. No GUI command or arbitrary
execution fallback is used. This preview workflow remains local research.

Feature health enumerates a single component's feature collection, with an offset
and limit (maximum 200), feature names/types, health enum values and warning/error
messages. Component-name ambiguity fails explicitly. The resource uses default
pagination; it is not an unbounded full-design dump.

Drawing inspection lazily imports `adsk.drawing`, checks the active product and
returns the document identity and active sheet name. It does not create sheets,
views, dimensions, annotations or export a drawing. The checked Autodesk
`Drawing.activeSheet` page is preview and must not be promoted on the basis of
successful local tests alone. `export_view_sheet` already present in this MCP is
a CAD viewport export, not proof of engineering-drawing API coverage.

Remaining candidates use shared MCP handlers but stay in `tests.development_mcp`
and Fusion360MCPDev. Production discovery includes only the two eligible queries
listed above; preview and incomplete candidates remain isolated.

## Verification and Next Groups

Unit tests: `tests/test_mechanical_queries.py`. Protocol tests:
`tests/test_mechanical_protocol.py`. Ledger checks:
`tests/test_mechanical_coverage.py`. Live cases:
`tests/test_mechanical_live.py`, explicitly selected with `--run-fusion-e2e`.
Use a CAD document containing features for the feature test; use an actual
drawing document with a sheet for the drawing test. Select the cases individually
when switching active documents. Missing prerequisites fail requested acceptance,
not skip or count as success. Reports are written only after passing assertions.

Stage reviewed source with `scripts.install_development_addin`, start the
development add-in, and select the read-only tests. Bootstrap changes require one
Stop/Run; subsequent helper changes use fixed `dev_reload_candidates`. Never clear
a user's design or infer mutation consent from a request to inventory APIs.

The remaining work is not complete. Review and implement batches for sketch
editing/constraints, construction geometry, feature extents/operations, BRep and
surface topology, sheet metal, assembly/joint motion, parameters/materials,
inspection/export, drawing document lifecycle, sheets/views, dimensions/annotations
and drawing export. Every mapped behavior requires unit cases, real protocol
cases and meaningful live-Fusion evidence before production promotion, as required
by [development rules](../../dev_rules.md). Per-member ledger statuses remain
unverified until that evidence exists; do not bulk-check off a class because one
query or method passed. New resource/templates have the same acceptance gates.