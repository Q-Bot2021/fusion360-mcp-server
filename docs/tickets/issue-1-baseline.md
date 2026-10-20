# Issue #1: 103-tool baseline

**Issue:** [Establish the 103-Tool Baseline and Evidence Matrix](https://github.com/Q-Bot2021/fusion360-mcp-server/issues/1)

**Plan:** [Ticket 01](../../plans/fusion-mcp-tool-audit-and-assembly.md#ticket-01-baseline-and-evidence-matrix)

**Baseline evidence:** [Production Tool Audit Baseline](../mechanical/tool-audit-baseline.md)

Captured on 2026-10-19 against implementation revision
`00ba5dcfc9d92eb1b135f051eb15f8fc6ad99a5e`.

**Status:** Closed as completed on 2026-10-20. See the
[verified resolution comment](https://github.com/Q-Bot2021/fusion360-mcp-server/issues/1#issuecomment-6283429744)
and [published implementation commit](https://github.com/Q-Bot2021/fusion360-mcp-server/commit/2beb5ea8eb6ffd281dea260a0b2f18e38ce0d8a0).

## Acceptance checklist

- [x] Reconciled 103 active production tools with the generic audit; recorded the
  disabled `execute_code` definition separately.
- [x] Added status rows for all 103 production tools and inventoried all 303
  schema-defined modes.
- [x] Recorded explicit generic-scope, unit, initialized-protocol,
  development-live, and production-live status for every mode. Gates without
  revision-bound mode evidence remain unverified; AutoConstrain's account
  entitlement is called out as a blocker.
- [x] Recorded source revision, package/add-in metadata, local Fusion version,
  host platform, fixture prerequisites, and evidence limitations.
- [x] Reran `export_step/default` unit and initialized-protocol checks against
  the audited source revision and linked the exact test cases in the matrix.
- [x] Verified audit coverage/freshness and generated-view consistency.

## Verification and limitations

- Audit baseline source revision: `00ba5dcfc9d92eb1b135f051eb15f8fc6ad99a5e`.
- Validation: 49 focused coverage/instructions/registry tests passed; 10
  `export_step` unit/protocol tests passed; Ruff passed.
- The running Fusion app was not asked to inspect or mutate the active document.
- No mode-level live test was run. The running app and MCP ping do not establish
  development or production acceptance; named, test-owned fixtures and a
  production add-in restart are required for those gates.
- Existing aggregate tool-level results are preserved as historical context;
  they were not elevated into mode-specific passes without source-revision
  evidence.
