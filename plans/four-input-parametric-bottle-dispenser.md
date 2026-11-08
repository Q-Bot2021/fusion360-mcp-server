# Ticket 32: Four-input parametric bottle dispenser

**Issue:** [#32](https://github.com/Q-Bot2021/fusion360-mcp-server/issues/32)  
**Breadcrumb:** [execution record](../docs/tickets/issue-32-parametric-bottle-dispenser.md)  
**Status:** Workflow migration published. Parameter-inspection/expression-edit
candidates passed unit, initialized protocol and development-live checks.
Constrained-profile and feature-pattern development-live checks also pass.
Production promotion and CAD remain pending.

## Confirmed requirements and ownership

- Fully assembled Dr. Brown's 8 oz narrow-neck bottles, including collar,
  nipple and protective cap. User measurements: 58 mm maximum diameter,
  215 mm overall height. Manufacturer confirmation is not yet established.
- Eight bottles on two tiers by default. Bottles lie across the dispenser
  width, rolling rearward on the upper lane, then forward on the lower lane.
  Load at top/front and retrieve at bottom/front.
- One solid body, native Fusion feature history, exactly four independent
  user inputs: `BottleDiameter`, `BottleHeight`, `BottleCount`, `TierCount`.
  Derived dimensions may be named expressions, not extra independent inputs.
- Support even tier counts (2, 4, 6, ...). Changing count/tier inputs must
  change capacity/layout and tier topology without rerunning a builder.
- Capacity is at least the requested count: the user approved rounding up to
  equal full tiers when the count is not divisible by the tier count.
- Single-piece FDM printing on a Bambu P1S. Dimensions alone do not prove
  slicing feasibility or a working gravity feed.
- Generic tools/evidence belong here. Bottle research, CAD exports and use/
  printing notes belong in the user-approved `C:\GitRepo\Bottle_Dispenser`.
  Native CAD remains authoritative in Fusion online storage.
- User approved extending the MCP and migrating missing SCUBA_Torch ticket
  workflow behavior. User acceptance is required before merge.

## Evidence and open decisions

Production tool discovery and handler inspection establish that box sizes
accept expressions; parameter create/update, sketch dimensions/offsets,
extrusions and pattern counts/spacing are numeric-only. Box size dimensions
also do not anchor its sketch placement. This is insufficient for a wholly
four-input-driven dispenser.

Related audit tickets: #7 (geometry), #8 (constraints), #10 (features),
#13 (patterns), #19 (construction) and #24 (parameters). Reuse their evidence
and helpers where applicable; these are overlap references, not implicit
blocking dependencies. This ticket does not require closing every audit mode.

Before selecting geometry, resolve:

1. Bottle rolling-contact diameters at body, collar and cap, axial runout,
   non-round features, and whether a 58 mm cylindrical swept envelope is
   conservative. A narrow neck can produce conical rolling and yaw.
2. Required slope and clearances from actual rolling behavior, not cylinder
   assumptions. Confirm whether the turn region can hold a bottle safely;
   count a turn position only if occupancy and subsequent release are proved.
3. Default envelope versus actual P1S usable slicing area, including brim and
   printer exclusion zones. A four-bottle straight lane plus a separate
   bottle-diameter return gap may exceed the bed.
4. Prove the approved minimum-capacity rule when `BottleCount` is not divisible
   by `TierCount`; additional rounded-up positions do not replace the requested
   default eight-bottle occupancy check.
5. Valid count/tier limits and behavior outside them. Odd tiers are out of
   scope; record and reject invalid inputs explicitly, not by silent rounding.
6. Print orientation, unsupported shelf spans, cleanability, drainage,
   dispensing stop and hand access. No physical reliability claim until tested.

## Ordered execution and completion gates

### 1. Tracking and workflow migration

- [x] Migrate only missing SCUBA_Torch workflow behavior, preserving Fusion gates.
- [x] Verify the new issue and branch; publish this plan and breadcrumbs.
- [x] Run existing instruction/documentation checks; preserve unrelated edits.

Done when published local/remote records identify scope, decisions, branch,
evidence and incomplete work; guidance requires user acceptance before merge.

### 2. Research and generic capability design

- [x] Record primary-source research in the bottle project.
- [ ] Trace existing parameter/sketch/feature/pattern helpers and Autodesk API
  members. Verify official signatures and installed-version prerequisites.
- [ ] Resolve material geometry/count choices and define the smallest generic
  tool contracts. Prefer exposing driving parameters over duplicating builders.

Candidate seams to investigate (not an approved API design): expression
creation/update and readback for user/model parameters, origin-anchored driving
sketch dimensions, expression-backed offsets/extrusions, and feature patterns
whose quantity and spacing are native parameter expressions. Body patterns
must not leave disconnected bodies in the final result.

First implemented slice: development-only `get_design_parameters` and
`set_parameter_expression`. Inspect native user/model parameter names and
expressions, then edit one explicitly inspected expression by document ID.
This can bind existing numeric sketch/plane/feature dimensions to native
expressions without proliferating expression fields across every tool.
Pattern-feature creation and origin constraints remain separate work; the
parameter primitives alone do not establish a four-input dispenser.

Second slice: expression-driven closed convex profiles and native feature
patterns pass XY/root and YZ/child joined-solid tests, including quantity
**2 -> 1 -> 3** and size changes with healthy feature history. The single-copy
pattern case needed by the default two-tier layout is verified. CAD feed-path
and print-envelope verification remain distinct pending requirements.

Done when the API/geometry choices meet all four inputs, including topology
changes, and known unsupported inputs have explicit outcomes before mutation.

The [bottle/P1S research](../../Bottle_Dispenser/docs/bottle-research.md) is
persistent in the separately owned bottle project, not published in this
repository. Official P1S nominal build volume is 256 x 256 x 256 mm. Bottle
dimensions remain user measurements; the research did not verify manufacturer
dimensions. Official care guidance requires full drying before storage.

The user approved three public test seams: MCP schemas/handlers (contracts,
units, targets, rejection), initialized MCP protocol (discovery/results), and
live disposable Fusion designs (regeneration, input/topology changes, body
count and feature health). None establishes physical rolling or printability.

### 3. Implement and verify infrastructure

- [ ] Add focused failing tests at public handler/schema seams; implement
  backward-compatible numeric and expression behavior using shared helpers.
- [ ] Test invalid/ambiguous selections, units, missing/duplicate names,
  expression errors, meaningful boundaries and unintended-mutation prevention.
- [ ] Pass initialized MCP protocol tests with real handlers and staged schemas.
- [ ] Update generic/status TSVs, regenerate the audit HTML and run freshness,
  synchronization, focused lint and full pre-submission tests.
- [ ] Stage through retained development infrastructure; obtain exact-revision
  development-live results in disposable designs on different planes/components.
- [ ] Obtain required review/restart and production-live evidence before
  promoting eligible changes. Reload host discovery before using changed tools.

Done when every changed contract has its own unit, protocol and live evidence.
Development scripts may verify infrastructure; user modeling remains direct,
visible tool calls. No arbitrary execution or modeling orchestration workaround.

### 4. Model and verify the dispenser

- [ ] Create a separate named design without clearing the unrelated active one.
- [ ] Build constrained history, transfer path, stops, access and ventilation
  through direct tools; join all solid geometry into one body.
- [ ] Test each of the four inputs independently, restore the defaults, then
  test another even-tier topology. Check expression readback, body count,
  feature health, bounds, capacity and clear bottle envelopes after changes.
- [ ] Visually inspect side, top and isometric views of the final result.
- [ ] Save native source and export F3D/STL; verify export persistence.
- [ ] Verify P1S slicing feasibility or report it blocked. Document physical
  gravity-feed testing separately as pending until actually performed.

Done when eight-bottle occupancy and transfer are geometrically established,
all input-driven changes preserve one healthy solid body, and print/CAD
artifacts are persistent. Do not claim practical feed reliability from CAD.

### 5. Review and closeout

- [ ] Publish verified slices and synchronize remote/local criteria.
- [ ] Present outcomes and gaps; wait for user acceptance before merging.
- [ ] Verify remote main, resolution comment, final checklist/state and local
  breadcrumbs per the remote issue procedure.

Incomplete gates keep the ticket open, even if a partial milestone is accepted.
