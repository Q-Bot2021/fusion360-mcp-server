# Fusion MCP Tool Audit and Assembly Readiness

## Goal

Audit and repair all 103 discoverable production MCP tools and every advertised mode, while delivering a production assembly workflow with nested occurrence targeting and animatable joints. Keep each capability pending until its own evidence passes. Promote tools individually; leave the overall audit open while any in-scope mode is unverified or blocked.

This plan is the shared execution reference for [tickets #1-#31](https://github.com/Q-Bot2021/fusion360-mcp-server/issues). Each issue links to the relevant section below. The ticket is the unit of work; this plan supplies common rules and domain-specific steps.

## Shared Execution Rules

1. **Start from the current state.** Read the ticket and open blockers, check the worktree and source revision, and inspect current ledger entries and relevant evidence. The historical handoff and ignored test artifacts are leads, not proof that a result still applies.
2. **Work one advertised mode at a time.** Reproduce the current behavior, add a focused regression at the public handler or MCP boundary, make the smallest generic repair, and verify successful and rejected inputs. Invalid or ambiguous selections must be rejected before mutation.
3. **Keep production behavior generic.** Use explicit entities and occurrence paths, component-local coordinate frames, and runtime-discovered design/library state. A fixture may make a test repeatable but must not become a production name, orientation, cloud ID, or root-only assumption.
4. **Use the evidence ladder for every changed or promoted capability.** Record unit/regression, initialized MCP protocol, development-live, and production-live results separately. Production-live evidence follows a production add-in restart and matches the exact source revision. Registration, mocks, skipped tests, and development evidence do not substitute for production acceptance.
5. **Protect live designs.** Use only disposable or test-owned designs. Before mutation, verify document identity and targets. Use one modeling operation per tool call, inspect after errors, and never blindly retry a mutation. Restore fixture state and record cleanup.
6. **Maintain the audit as evidence changes.** Update the generic audit and affected status rows at each verified milestone or new blocker. Regenerate the HTML only from the TSV sources. Keep blocked, failed, stale, and pending statuses visible.
7. **Close a ticket only on its acceptance criteria.** Attach exact-revision evidence, fixture and Fusion/platform versions, assertions, results, artifact locations, and commands not run with reasons. Leave unsupported or entitlement-blocked modes unresolved rather than infer a pass.

## Dependencies and Milestones

- Ticket 1 establishes the baseline and unblocks all domain work.
- Ticket 2 is the production deployment gate for staged joint-selection, suppression, interference, and promoted document-reference behavior. It blocks production acceptance of affected tools, not unrelated implementation.
- Assembly sequence: 1 -> 4 -> 5 -> 6. Ticket 2 is also a production gate for changed assembly behaviors.
- Sketch sequence: 1 -> 7 -> 8. Ticket 9 depends on an eligible external entitlement, not on ticket 8.
- Feature sequence: 1 -> 7 -> 10 -> 11 and 12 -> 13. Ticket 17 depends on ticket 15 because it preserves directional surface behavior.
- CAM sequence: 1 -> 29 -> 30.
- Ticket 31 is final closeout and depends on all preceding tickets.
- External prerequisites are local blockers only: entitled Fusion account for AutoConstrain; a valid installed appearance; configured accessible assembly fixture IDs; and supported installed Fusion APIs/workspaces. A blocker on one mode does not block independent domain tickets.

## Ticket Execution Sections

## Ticket 01 Baseline and evidence matrix

**Scope:** All active production registry names and advertised modes. Reconcile current discovery with the generic audit, status ledger, and capability coverage; exclude disabled definitions from the active count.

**Execution:** Capture the branch, source revision, package/add-in versions, Fusion version/platform, and fixture availability. For each tool/mode, identify current unit, initialized-protocol, development-live, and production-live evidence and its source revision. Mark stale evidence stale; classify missing, failed, blocked, pending, and accepted scope without converting API coverage or mocks into acceptance.

**Done when:** The active registry and audit inventory reconcile exactly; every mode has explicit status and evidence or a named blocker; coverage/freshness checks pass; the generated HTML matches the TSV sources.

## Ticket 02 Staged production acceptance

**Scope:** Existing production-staged occurrence-path selection for `create_as_built_joint`, joint-aware suppression, interference behavior, and production-pending `open_design`, `insert_design`, and `list_occurrences`.

**Execution:** Verify stage receipt, handler/manifest hashes, and backup hashes before touching installed production files. Confirm the Fusion MCP repository and production add-in profile. After authorization, Stop/Run the add-in, initialize MCP against production, and test exact nested occurrence paths, ambiguous-selector no-mutation behavior, suppression/unsuppression round-trip, interference query, and document open/insert/list behavior using test-owned designs.

**Done when:** Every affected tool has separate protocol and production-live results on the post-restart source revision; backups and live design state are accounted for; only verified ledger statuses change.

## Ticket 03 Design lifecycle and safe document controls

**Scope:** `create_design`, `save_design`, `get_document_state`, `get_design_type`, `set_design_type`, `delete_all`, `undo`, and `ping`.

**Execution:** Exercise new and existing disposable documents, first save and subsequent save, document identity/state readback, supported design-type transitions and consent, undo after a known operation, and health-check behavior. Test invalid design types, missing documents, and destructive requests against identity guards; use `delete_all` only on a test-owned design.

**Done when:** Each supported mode has explicit protocol and live assertions for resulting document state; rejected destructive or unsupported requests leave the intended document unchanged; save/reopen preserves the expected design identity and contents.

## Ticket 04 Referenced designs and occurrence structure

**Scope:** `create_component`, `open_design`, `insert_design`, `list_occurrences`, and `list_components`.

**Execution:** Verify that adding a child to a shared parent definition affects all instances by design. Insert a referenced test-owned design under root and nested parents, save/reopen, and inspect component definitions separately from occurrence instances. Select repeated components by full occurrence path; allow a name selector only when unique; prove missing and ambiguous selectors reject before mutation.

**Done when:** Reference identity survives save/reopen; root, nested, and repeated occurrences are distinguishable in readback; shared-definition behavior is explicit; invalid selection leaves occurrence inventory unchanged; required protocol/development/production gates are recorded.

## Ticket 05 Joint authoring and rigid grouping

**Scope:** `add_joint`, `create_as_built_joint`, and `create_rigid_group`; joint types are rigid, revolute, slider, cylindrical, pin-slot, planar, and ball.

**Execution:** Run the seven-type matrix under both root and nested parent occurrences. Use explicit occurrence paths for repeated instances and test a unique-name fallback. Validate joint inputs and both rigid-group members before adding anything. Compare joint and group inventory before/after missing, ambiguous, self, or invalid selections. Confirm joint type and selected occurrences by readback.

**Done when:** All seven advertised types are created at the intended root/nested occurrences; invalid calls make no inventory or transform changes; motion behavior is consistent with type; all required evidence gates are current.

## Ticket 06 Joint driving and animation

**Scope:** Productionize `create_joint`, `list_joints`, `drive_joint`, and `animate_joint` as needed for the full user workflow.

**Execution:** Use a test-owned referenced door/hinge assembly. Insert/open it, select nested occurrences, create or inspect a revolute joint, drive a known range, capture animation frames, save/reopen, and verify joint and transform persistence. Confirm the fixed frame remains fixed and restore the fixture's baseline. Treat collision checks at sampled frames as sampled checks, not continuous swept-clearance proof.

**Done when:** The complete workflow is callable through production MCP after restart; schemas and errors are validated; animation outputs and saved state are read back; fixture restoration and all four evidence gates are recorded.

## Ticket 07 Sketch geometry authoring

**Scope:** `create_sketch`, `draw_rectangle`, `draw_circle`, `draw_line`, `draw_arc`, `draw_spline`, `create_polygon`, and `draw_sketch_text`.

**Execution:** Create sketches on supported planes and offsets in root and rotated component contexts. Draw each geometry family with explicit sketch targeting and verify coordinates/counts via readback. Include invalid dimensions, missing sketch, unsupported frame, and ambiguous target rejection. For text, inspect a rendered view and check it is legible, unclipped, and clear of boundaries.

**Done when:** Supported geometry is in the intended sketch-local frame; invalid calls add no sketch entities; text has visual evidence where supported; protocol, development-live, and production-live status is explicit per mode.

## Ticket 08 Constraints and curve preparation

**Scope:** `add_constraint`, `add_dimension`, `offset_curve`, `trim_curve`, `extend_curve`, and `project_geometry`.

**Execution:** Build known sketches with labeled entities in root and rotated component frames. Apply each supported constraint/dimension and verify solver or dimension state. Prepare curves and verify resulting entity counts and geometry. Project supported model geometry and check sketch ownership. Exercise missing, ambiguous, incompatible, and solver-failing selections and assert no unintended sketch change.

**Done when:** Each advertised mode has deterministic state readback and explicit error/no-mutation cases; unit, initialized-protocol, development-live, and production-live results are recorded.

## Ticket 09 AutoConstrain entitlement

**Scope:** `auto_constrain` for eligible Fusion accounts.

**Execution:** Confirm supported Fusion version and account entitlement before invocation. On an authorized test sketch, call through MCP, inspect constraints and geometry, and test unsupported or unentitled behavior without representing it as success. Do not request or record credentials.

**Done when:** Eligible-account protocol/live evidence verifies the resulting sketch state; if no entitled environment is available, the ledger and issue remain explicitly blocked by license with no waiver.

## Ticket 10 Sketch-driven solid creation

**Scope:** `extrude`, `extrude_sketch_entities`, `revolve`, `sweep`, `loft`, `create_hole`, and `create_thread`.

**Execution:** Use named test-owned profiles, paths, axes, and faces in root and rotated/nested contexts. Cover each advertised extent/direction/type mode, especially signed and symmetric extents. Read back feature health, body count, bounds, volume, units, hole parameters, and thread mode. Reject open, missing, incompatible, or ambiguous profiles before mutation.

**Done when:** Every supported mode produces the asserted feature/body state; invalid requests leave geometry unchanged; all relevant evidence gates and tool statuses are current.

## Ticket 11 Solid finishing features

**Scope:** `fillet`, `chamfer`, `chamfer_edges`, `shell`, `draft_faces`, and `offset_faces`.

**Execution:** Use disposable solids with known edges/faces. Verify selected topology and expected geometry/volume changes for supported options and root/nested contexts. Exercise stale indices, missing faces, impossible radii/thickness, and unsupported geometry; inspect feature health after each rejected case.

**Done when:** Success cases affect only requested topology and invalid cases do not corrupt the design; each advertised mode has unit, protocol, development-live, and production-live evidence.

## Ticket 12 Boolean, split, and feature history

**Scope:** `boolean_operation`, `split_body`, `split_face`, `suppress_feature`, and `unsuppress_feature`.

**Execution:** Use disposable multi-body designs with known tool/target bodies and split geometry. Read back body/face counts and volume. Suppress and restore a named feature, including joint-aware behavior where applicable; compare body and feature health before/after. Reject missing or incompatible participants before mutation.

**Done when:** Boolean and split results match expected geometry; suppression round-trips restore the prior state; failure paths leave the design intact; staged production suppression evidence is reconciled.

## Ticket 13 Body transforms and patterns

**Scope:** `move_body`, `mirror`, `scale_body`, `rectangular_pattern`, `circular_pattern`, and `rename_body`.

**Execution:** Target explicit bodies/occurrences in root and nested contexts. Verify transformed bounds and orientation, mirror plane, scale factor, pattern count/spacing/direction, and rename readback. Include collisions, zero/negative/invalid counts, ambiguous names, and non-default component orientation.

**Done when:** Only selected entities change and resulting geometry matches parameters; invalid calls leave the design unchanged; each advertised mode has current protocol and live evidence.

## Ticket 14 Direct primitives

**Scope:** `create_box`, `create_box_parametric`, `create_cylinder`, `create_sphere`, and `create_torus`.

**Execution:** Create each primitive in root and explicit component contexts with varied dimensions and orientation. Read back bounds, volume, and component ownership. Test invalid dimensions, unsupported placement, and any root-only limitation without leaving partial bodies.

**Done when:** Valid inputs create the intended body in the requested context and invalid requests create none; production behavior has no fixture-name or fixed-orientation dependency.

## Ticket 15 Patch, stitch, and trim surfaces

**Scope:** `patch_surface`, `stitch_surfaces`, and `trim_surface`.

**Execution:** Use disposable surfaces with known closed/open boundaries and cutter surfaces/bodies. Test horizontal, vertical, and rotated component-local orientations; inspect surface body count, topology, area/volume, and stitch tolerance outcomes. Reject invalid boundaries before mutation.

**Done when:** Supported inputs produce the asserted surface topology; tolerance and invalid-input boundaries are explicit; required unit, protocol, development-live, and production-live gates pass.

## Ticket 16 Ruled surface

**Scope:** Repair `ruled_surface` using the installed Fusion API signature.

**Execution:** Verify the signature against the installed Fusion version and Autodesk API reference. Test supported edge types, direction/extent options, root/component targets, and invalid edges. Confirm the created surface geometry and feature health by readback.

**Done when:** The previously failing valid case passes regression, protocol, development-live, and production-live acceptance; invalid cases create no surface; ledger failure status is removed only with exact-revision evidence.

## Ticket 17 Symmetric surface thickening

**Scope:** Repair symmetric total thickness in `thicken_surface` while preserving valid directional modes.

**Execution:** Use a measurable planar and curved test surface. Check both sides of the input surface, total thickness (not per-side thickness), resulting volume, and direction modes. Include invalid thickness and self-intersection/rejection behavior.

**Done when:** Symmetric output has the requested total thickness, directional modes remain unchanged, and protocol/development/production regression evidence passes.

## Ticket 18 Sheet metal

**Scope:** `create_flange`, `create_bend`, `unfold`, and `flat_pattern`.

**Execution:** Use a supported sheet-metal design with known thickness and bends. Create a flange/bend, unfold the selected bend, generate the flat pattern, and read back feature state and dimensions. Test unsupported design types and invalid edges before mutation.

**Done when:** The sequence produces a valid flat pattern and expected bend state; rejection is safe; every advertised mode has current protocol and live evidence.

## Ticket 19 Construction planes and UCS

**Scope:** `create_construction_plane` and `create_ucs`.

**Execution:** Exercise each advertised plane definition with known points, faces, axes, and angles. Read back origin, normal, and orientation in root and component-local contexts. Check Fusion version and preview eligibility before invoking UCS; represent unsupported versions clearly.

**Done when:** Supported modes match expected coordinate geometry; unsupported/preview-only modes stay non-production when required; invalid inputs do not add construction geometry.

## Ticket 20 Construction axes

**Scope:** Repair two-point `create_construction_axis` and retain intersection, edge, and perpendicular modes.

**Execution:** Reproduce the two-point API validation failure; verify the installed API signature; test valid point pairs, coincident points, intersection references, edge references, and perpendicular references. Read back axis origin/direction and check unchanged construction inventory after rejection.

**Done when:** All supported modes pass unit/protocol/development-live/production-live checks on the installed version; the two-point regression is closed with evidence.

## Ticket 21 Scene and object inspection

**Scope:** `get_scene_info`, `get_object_info`, `get_bounding_box`, `get_body_topology`, `get_feature_health`, and `get_physical_properties`.

**Execution:** Query root and nested/repeated occurrences with explicit paths. Compare returned counts, names, bounds, topology, health, mass/volume/area, and center of mass to known fixtures. Include empty designs, missing targets, ambiguous names, unit conversions, and version limitations. Assert queries do not mutate design state.

**Done when:** Read-only results match known geometry and component context; errors name the unresolved target; protocol and live evidence is recorded per mode.

## Ticket 22 Measurements and mesh comparison

**Scope:** `measure_distance`, `measure_angle`, and `compare_meshes`.

**Execution:** Use known geometric references with exact expected distances/angles and unit variants. Compare mesh bodies with known deviation and ensure unsupported Fusion versions/designs fail clearly. Include nested component coordinate frames and invalid or ambiguous entity pairs.

**Done when:** Numeric outputs and units match reference cases; unsupported mesh prerequisites are explicit; no query mutates geometry; protocol/live gates pass.

## Ticket 23 Section and interference analysis

**Scope:** `create_section_analysis` and `check_interference`.

**Execution:** Build known crossing/non-crossing bodies and a nested door/hinge assembly. Verify section plane position/orientation and occurrence-pair interference readback at the baseline and sampled revolute positions. Restore transforms and distinguish sampled checks from continuous motion guarantees.

**Done when:** Analysis matches known intersections and section geometry; staged production interference behavior is accepted after restart; no continuous clearance claim exceeds the sampling evidence.

## Ticket 24 Parameter lifecycle and units

**Scope:** `get_parameters`, `create_parameter`, `set_parameter`, and `delete_parameter`.

**Execution:** Cover length, angle, and unitless parameters; create, read, update expressions, verify dependent values, and delete. Test duplicates, missing names, invalid expressions, referenced parameters, unit conversions, and API calls returning false.

**Done when:** Values and expressions round-trip exactly within documented unit behavior; error/false-return cases are surfaced; protocol and production live evidence is recorded.

## Ticket 25 Direct body color

**Scope:** `set_color`.

**Execution:** Apply RGB values to explicit root and nested body targets, read color back, and compare geometry properties before/after. Test invalid channels, missing body, and ambiguous target names.

**Done when:** The selected appearance color matches the request and geometry is unchanged; invalid targets are rejected before assignment; live and protocol evidence is recorded.

## Ticket 26 Library appearance

**Scope:** `set_appearance` with a real installed library item.

**Execution:** Discover an available appearance from the current Fusion library rather than hard-coding a fixture-specific item. Apply it to a disposable body and verify appearance identity by readback. Test missing library entries and invalid/ambiguous body targets.

**Done when:** A positive live assignment is verified in the target Fusion environment; missing installed appearance remains an explicit blocker and does not become accepted from preflight or mocks.

## Ticket 27 Mesh import and CAD export

**Scope:** `import_mesh`, `export`, `export_f3d`, `export_step`, and `export_stl`.

**Execution:** Use disposable source designs and temporary approved output directories. Import a known mesh and verify bounds/units/body count. Export each advertised format and reopen or inspect file structure. Test invalid paths, overwrite behavior, unsupported entities, and failed export cleanup.

**Done when:** Outputs exist and are readable with expected geometry; import units are verified; failure paths do not overwrite unrelated files; production and protocol evidence is recorded.

## Ticket 28 View sheets and rendering

**Scope:** `export_view_sheet` and `render_view`.

**Execution:** Generate views for representative designs and camera orientations. Check output file existence and inspect images for nonblank geometry, framing, correct view orientation, and no clipping. Cover invalid camera/view and output-path errors.

**Done when:** Image artifacts are visually reviewed and correspond to the intended design; file/failure handling is correct; supported modes have protocol and live evidence.

## Ticket 29 CAM setup and operations

**Scope:** `cam_create_setup`, `cam_create_operation`, `cam_list_setups`, `cam_list_operations`, and `cam_get_operation_info`.

**Execution:** Use a supported manufacturing workspace and test-owned CAM fixture. Create a setup and supported operation, read back parameters and operation state, and cover empty inventories, unsupported workspace, missing setup/operation, and invalid parameters.

**Done when:** Setup and operation state is verified through MCP and Fusion; invalid requests fail safely; protocol and production-live evidence records the Fusion workspace/version.

## Ticket 30 CAM toolpath and post-processing

**Scope:** `cam_generate_toolpath` and `cam_post_process`.

**Execution:** Start from a verified setup/operation from ticket 29. Generate toolpath, verify its state, post-process with a supported post configuration, and inspect output. Test invalid setup/operation, missing post, and unsafe/unwritable output paths.

**Done when:** Toolpath and posted output are verified on a supported CAM fixture; failure cases leave no misleading output; all evidence gates pass.

## Ticket 31 Full production audit closeout

**Scope:** Every 103 discoverable production tools and advertised modes, plus the production assembly animation workflow.

**Execution:** Reconcile each ticket's result against active discovery, generic audit, status ledger, API coverage, source revision, and exact evidence. Regenerate the HTML from TSV; run full offline, protocol, coverage/freshness, instruction-sync, Ruff, and required production-live gates. Preserve every unresolved blocker and failed mode in the report.

**Done when:** No status is inferred from mocks, registration, skipped tests, or stale evidence; all accepted capabilities have current evidence; all remaining blockers are explicit; the full audit report names source revision, Fusion/platform version, fixture/evidence references, and unrun checks with reasons.

## Current Known Risks and Blockers

- Initial audit counts and commit/staging references are snapshots; ticket 1 must refresh them before relying on them.
- The assembly fixture IDs are environment-configured and must be accessible before saved-design tests run.
- AutoConstrain requires an entitled account. Appearance acceptance requires a valid installed library item.
- Ruled-surface signature, symmetric thickening, and two-point construction axis have known failures; retain those statuses until evidence passes.
- Production acceptance requires production profile and add-in restart; development passes are not production evidence.
