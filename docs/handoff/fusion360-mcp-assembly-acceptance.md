# Fusion360 MCP Handoff

Prepared 2026-10-18 for migration to a fresh project/session context.

## Purpose

Continue the in-progress assembly/joint acceptance. The requested repository commit/push is complete. Do not treat the current work as deployment-approved: production staging for the latest assembly change explicitly requires an add-in restart and production live acceptance.

## Repository State

- Workspace: `C:\GitRepo\fusion360-mcp-server`
- Source commit: `29b7e0f` on `main`; `origin/main` was aligned before moving this handoff into the repository. The committed parent was `bf23a38`.
- Current package version: `0.9.13`; add-in manifest version: `0.3.5`.
- The handoff-time source changes were committed and pushed as `29b7e0f` (`Add assembly occurrence and joint acceptance workflows`): 22 files changed, including the assembly suite and portable `.vscode/tasks.json`.
- `.vscode/tasks.json` includes a production syntax-check task; its machine-specific `C:\Users\Quent` path was replaced with `${env:APPDATA}` and JSON validation passed. It is included in `29b7e0f`.
- No registry removals are intended. Commit `29b7e0f` added three production definitions: `open_design`, `insert_design`, and `list_occurrences`. Existing assembly/joint and suppression behavior is also being generalized.

## Current Work

The active slice adds assembly occurrence inspection/insertion and joint-selection support, with door/hinge fixtures used for geometry and motion acceptance. Main source surfaces are:

- `addon/server/command_handler.py`
- `addon/server/mechanical_queries.py`
- `src/fusion360_mcp/tools.py`
- `src/fusion360_mcp/mock.py`
- `tests/development_mcp.py`
- `tests/test_assembly_live.py`
- `tests/test_mechanical_live.py`
- `tests/test_mechanical_protocol.py`
- `tests/test_sandbox_documents.py`
- `docs/mechanical/tool-status.tsv`
- `docs/mechanical/generic-tool-audit.tsv`
- `docs/mechanical/README.md`

The new assembly live suite has 13 test functions (30 collected parameterized cases) covering nested as-built occurrence paths, door/hinge source features, inserted-hinge motion/clearance, seven joint types in root/nested contexts, planar mounting, countersunk screw alignment, saved-door joint inventory/interference/animation, and referenced component insertion/open/recovery. Saved external fixture IDs are environment-configured rather than embedded in source: `FUSION_TEST_NESTED_COMPONENT_DATA_FILE_ID` and `FUSION_TEST_HINGE_ASSEMBLY_DATA_FILE_ID`.

## Verified Evidence

All listed live acceptance reports are development-profile results unless explicitly noted otherwise:

- `.pytest_cache/assembly-joint-matrix.xml`: 14/14 joint types/context cases passed (rigid, revolute, slider, cylindrical, pin-slot, planar, ball; root and nested parent).
- `.pytest_cache/nested-joint-path-selection.xml`: nested as-built joint exact occurrence-path selection passed; ambiguous component-name rejection left the joint inventory unchanged.
- `.pytest_cache/inserted-hinge-motion.xml`: inserted hinge sampled motion/clearance passed.
- `.pytest_cache/hinge-source-mounting-holes.xml`: hinge source mounting-hole geometry passed.
- `.pytest_cache/door-source-mounting.xml`: door frame/panel mortise and pilot alignment passed.
- `.pytest_cache/door-joint-inventory-20261018_194320_288842/report.json`: saved door inventory passed with one active revolute door joint.
- `.pytest_cache/door-joint-animation-20261018_211429_736073/report.json`: saved-door opening animation passed.
- `.pytest_cache/door-interference-20261018_211343_444974/report.json`: no cross-occurrence interference passed; report notes only measured frame corner overlaps outside the cross-occurrence check.
- `.pytest_cache/insert-open-nested-fixed.xml`: referenced nested insert/open test passed after correcting the earlier child-occurrence grounding failure.
- `.pytest_cache/insert-open-resumed.xml` and `.pytest_cache/nested-context-resume.xml`: resumed insertion contexts passed.
- `.pytest_cache/hinge-assembly-offline.xml`: focused offline suite, 545 tests passed.
- `.pytest_cache/door-source-mounting.xml`, `.pytest_cache/hinge-source-mounting-holes.xml`, `.pytest_cache/inserted-hinge-motion.xml`, `.pytest_cache/door-joint-animation-20261018_211429_736073/report.json`, and `.pytest_cache/door-interference-20261018_211343_444974/report.json`: saved fixture source geometry, inserted-hinge motion, door animation, and interference checks passed in development.

The above `.pytest_cache` artifacts are local and ignored by Git. Test collection after replacing embedded fixture IDs passed (30 cases). Final normal suite: `.pytest_cache/handoff-precommit-final.xml`, 942 total, 180 opt-in skips, 762 passed, zero failures/errors. Full Ruff, `.vscode/tasks.json` JSON validation, and `uv lock --check --offline` passed. A normal-suite registry test initially failed because its development-only assertion did not account for the three intended assembly promotions; the assertion now explicitly allows `open_design`, `insert_design`, and `list_occurrences`, and the final suite passes. Staged `git diff --cached --check` is clean.

These are test-owned fixture cases, not blanket proof of generic production acceptance.

## Production Staging

`.pytest_cache/production-joint-stage-20261019_005534.json` records `staged_restart_required` for a narrow production handler change: occurrence-path selection for existing `create_as_built_joint` selectors. It records the production handler/manifest pre- and post-stage SHA-256 hashes and backup location `.pytest_cache/production-joint-backup-20261019_005534`.

Next production gate:

1. Verify the staged production files and backup hashes before mutation/testing.
2. Stop/Run the `Fusion360MCP` add-in so its in-memory handler reloads.
3. Run production-only MCP/live acceptance for the changed occurrence-path behavior and `suppress_feature` change; do not use development acceptance as production evidence.
4. Update the TSV ledger and regenerate `docs/mechanical/audit-ledger.html` only from verified results.

The current ledger (`docs/mechanical/tool-status.tsv`) marks production acceptance pending for `create_as_built_joint`, `open_design`, `insert_design`, `list_occurrences`, `suppress_feature`, and `check_interference`. Other previously recorded gaps remain open. In particular, `thicken_surface` symmetric geometry and `ruled_surface` API signature remain failed; the user explicitly asked to leave those tools registered and continue with other tools. `create_construction_axis` two-point mode also remains failed. AutoConstrain is account-entitlement restricted for this account; the tool remains available to eligible users and the exact subscription tier is unverified.

## Immediate Handoff Actions

1. After opening this document in the new project context, verify the current branch/status and inspect the latest production stage report.
2. Complete the production add-in Stop/Run and production-only live acceptance for the staged occurrence-path change and joint-aware suppression/interference behavior. Update ledgers from actual results.
3. Continue the generic tool audit after that gate; retain failed surface/construction modes and all other pending statuses rather than claiming blanket acceptance.
4. The assembly suite's two saved-design IDs require `FUSION_TEST_NESTED_COMPONENT_DATA_FILE_ID` and `FUSION_TEST_HINGE_ASSEMBLY_DATA_FILE_ID`; configure accessible fixtures in the new environment before selecting those live tests.
5. The durable handoff belongs at `docs/handoff/fusion360-mcp-assembly-acceptance.md`; ignored `.pytest_cache` evidence remains local and must be copied separately if needed across machines.

## Repository Gates And Safety

Read `AGENTS.md`, `.github/copilot-instructions.md`, and `dev_rules.md` before further capability changes. Keep `.claude/CLAUDE.md` and `.github/copilot-instructions.md` synchronized if either changes. New/changed registered tools require unit, initialized MCP protocol and live local-Fusion acceptance; maintain `docs/mechanical/tool-status.tsv` and `generic-tool-audit.tsv`, regenerate HTML with `python -m scripts.audit_mechanical_api docs/mechanical/audit-ledger.html --html`, and run coverage/instruction checks.

Use only disposable/test-owned designs for mutations, one modeling operation per tool call, inspect after errors, and never blindly retry a mutation. Keep the loopback-only transport and disabled arbitrary execution policy. The `.pytest_cache` reports above are ignored local artifacts; preserve/copy them separately if the migration changes machines or clears the workspace cache.

## Suggested Skills

- `python-fact-grounded-coding` for further Fusion handler/API repairs that need verified installed signatures and live evidence.
- `handoff` only if this work needs to move again; this document is now maintained as a repository artifact.
