# Issue #2: Staged Production Acceptance

**Issue:** [Accept the Staged Production Assembly Changes](https://github.com/Q-Bot2021/fusion360-mcp-server/issues/2)

**Plan:** [Ticket 02](../../plans/fusion-mcp-tool-audit-and-assembly.md#ticket-02-staged-production-acceptance)

**Status:** In progress. Production hash preflight passed; post-restart
acceptance is not yet recorded.

## Preflight

- Repository source revision: `5187b107f690f1c99f02c482a0e3fc5f4e06ab1d`.
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
  `DoorPanel_Source_20261018` in `MCP_Dev`. No geometry mutation was made.
  During preflight, a save request was accepted, but document metadata remains
  pending (`data_file_id` and project name are temporarily unavailable). No
  retry was issued. Inspect document state before relying on it as a fixture.

## Pending acceptance

- Obtain a current identity for the saved `MCP_DoorAssembly_20261018` or
  `DoorHinge_Subassembly_20261018` fixture. Fusion MCP exposes opening a design
  by data-file ID but not listing files in a cloud project. The fixture IDs are
  intentionally not committed.
- Run initialized production MCP and live assertions for exact nested
  occurrence-path joint selection, ambiguous-selector no-mutation,
  suppression/unsuppression, interference, and open/insert/list behavior.
- Record post-restart source identity, Fusion/platform, test-owned design state,
  results, and artifacts before changing any audit status.
- No production acceptance ledger status is promoted by this preflight.
