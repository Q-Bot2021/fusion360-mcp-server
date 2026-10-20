# Issue #2: Staged Production Acceptance

**Issue:** [Accept the Staged Production Assembly Changes](https://github.com/Q-Bot2021/fusion360-mcp-server/issues/2)

**Plan:** [Ticket 02](../../plans/fusion-mcp-tool-audit-and-assembly.md#ticket-02-staged-production-acceptance)

**Status:** Targeted post-restart production acceptance passed, and sandbox
cleanup was verified.

## Preflight

- Repository base revision before Ticket 2 documentation updates:
  `5187b107f690f1c99f02c482a0e3fc5f4e06ab1d`.
- Stage receipt:
  `.pytest_cache/production-joint-stage-20261019_005534.json`
  (`staged_restart_required`).
- Production profile:
  `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\Fusion360MCP`.
- The installed `server/command_handler.py` SHA-256
  `8ea97ba4c04834f68cf8bd4bd68c3dcb00439cfaa3f4f3ffc2ac40407eac6e77`
  matches both the receipt's staged hash and repository source.
- The installed `Fusion360MCP.manifest` SHA-256
  `8d4e82e6f139c883d3b6ac828ed6c7e3f6ac6b6a06b4f4c59fe0736a7acef5cd`
  matches both the receipt's staged hash and repository source.
- Backup `server/command_handler.py` SHA-256
  `95ae2e0cb71b10fac53135af8c6285bb1ced90a2198b81ce4e54b05d285448bd`
  matches the receipt.
- Backup `Fusion360MCP.manifest` SHA-256
  `3834536a5040cff681b947b0fb0a926f979756d3b2f3b1210a8e7b23b79e8ec7`
  matches the receipt.
- User authorized the production add-in restart and test-fixture mutations,
  confirmed that Stop/Run was completed, and designated `MCP_Dev` as the
  sandbox. The live Fusion version is `2705.1.25`; production MCP ping
  responded `pong`.
- The active saved document was identified as
  `DoorPanel_Source_20261018` in `MCP_Dev`. During preflight, a save request
  was accepted without geometry changes and initially reported pending
  metadata. No retry was issued; a subsequent `open_design` succeeded and
  `get_document_state` confirmed the saved identity and project before use.

## Production acceptance

Tested after the authorized production add-in restart through direct,
initialized production MCP tool calls against the `MCP_Dev` sandbox. The
production handler and manifest matched the staged receipt and repository
source at revision `8577880447e2441a176b40c859ec2e0999cf9d8d`. Fusion was
`2705.1.25` on Windows x64.

- `suppress_feature` suppressed `DoorAssemblyRevolute`; `unsuppress_feature`
  restored it. Both calls returned success, with body count, mass, and bounds
  unchanged. A final unsuppress call confirmed the joint was restored.
- `check_interference` for `Frame`/`Door` returned zero cross-occurrence
  collisions. The default query returned only the two previously documented
  Frame corner overlaps, each approximately 1200 cm3. The
  `include_coincident_faces=true` mode was not exercised.
- `open_design` opened the saved `DoorPanel_Source_20261018` and
  `MCP_DoorAssembly_20261018` designs; `get_document_state` confirmed each
  saved identity in `MCP_Dev`.
- `insert_design` inserted two referenced `DoorPanel_Source_20261018`
  instances under `Door` with `grounded=false`. `list_occurrences` returned
  the original two root occurrences and both full nested paths:
  `Door:1+DoorPanel_Source_20261018:1` and
  `Door:1+DoorPanel_Source_20261018:2`.
- `create_as_built_joint` rejected the repeated component-name selector with
  “missing or ambiguous; use its full occurrence path.” The subsequent
  `get_scene_info` and `list_occurrences` matched pre-error body/timeline
  counts and occurrence paths. Supplying both full nested paths created the
  rigid joint and returned those exact paths. `undo` returned success; the
  post-undo timeline count matched the pre-joint count. The production tool
  set does not expose a joint-list query, so joint inventory was not
  independently read back.
- Only the exercised modes are promoted in the ledgers. Other joint types,
  insertion flag combinations, and coincident-face handling remain
  unverified.

## Sandbox cleanup state

The production MCP has no single-occurrence delete tool, and `undo` did not
remove the two test references. No explicit save was issued after insertion.
The user closed `MCP_DoorAssembly_20261018` without saving; reopening it through
production MCP and listing occurrences returned only the original `Frame:1`
and `Door:1` paths. The saved sandbox fixture is restored; the joint remains
unsuppressed.

## Remaining limits

- This is targeted production acceptance for Ticket 02, not blanket acceptance
  of every advertised mode for these tools.
