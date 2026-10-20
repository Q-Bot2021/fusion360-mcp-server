# Production Tool Audit Baseline

Baseline captured for GitHub issue #1.

Captured on 2026-10-19.

## Source and environment

- Audited code revision: `00ba5dcfc9d92eb1b135f051eb15f8fc6ad99a5e`, the
  repository `HEAD` when the audit began on branch `ticket-1-103-tool-baseline`.
- Package version: `0.9.13` from `pyproject.toml`.
- Repository add-in manifest version: `0.3.5` from
  `addon/Fusion360MCP.manifest`; this is not confirmation of the version loaded
  by the running Fusion process.
- Local Fusion executable and `fusion_version.txt`: `2705.1.25`.
- Host platform: Windows, OS version `10.0.26200.0`, AMD64.
- The Fusion process was running and the configured MCP `ping` returned `pong`.
  This is transport/health evidence only, not a Fusion API or modeling acceptance
  result.

The active document was not opened or inspected. No named, test-owned CAD or
drawing fixture identifiers were supplied for this run. The repository contains
the `Fusion360MCPDev` add-in source and tests requiring named fixtures, but this
does not prove the development add-in is installed or loaded. Live acceptance
was not run. In particular, production-live acceptance requires its own
production add-in restart and test-owned design.

Fixture entry points are documented in `tests/conftest.py`,
`tests/test_fusion_e2e.py`, and `tests/test_mechanical_live.py`. The first two
Fusion resource-template fixture selectors are `--fusion-test-body` and
`--fusion-test-component`. Historical fixture names in documentation are not
treated as currently available.

## Registry and mode reconciliation

- `fusion360_mcp.tools.get_tool_list()` exposes 103 production tools from 104
  retained definitions.
- `execute_code` is the one disabled definition and is excluded from the active
  count.
- `generic-tool-audit.tsv` has exactly 103 unique entries and matches active
  production discovery.
- `tool-status.tsv` now has an entry for every active production tool, plus the
  seven existing development-only entries. The 33 production entries missing
  from the previous ledger were added as `unverified`, not inferred passes.
- The tool-level ledger records an `evidence_revision` for every row. Only the
  newly rerun `export_step` unit/protocol result is bound to this source
  revision; the prior aggregate rows remain `unrecorded`.
- `tool-mode-status.tsv` contains 303 schema modes: each explicit input-enum
  value and boolean value is a separate mode; tools without those choices have
  one `default` row. Independent schema choices are recorded separately rather
  than expanding every possible parameter combination.
- `capability-coverage.tsv` contains 11,053 mechanical/drawing API pointer
  entries. It reconciles to the API pointer index; it is an implementation
  backlog and does not establish coverage or acceptance for any MCP tool.

Every mode has a generic-scope classification and explicit unit, initialized
protocol, development-live, and production-live statuses. The
`export_step/default` unit and initialized-protocol checks were rerun at the
audited source revision; their exact test references are in the mode ledger.
Other mode-level gates remain `unverified`: the prior tool-level ledger is
aggregate, and does not bind each mode's result to an exact source revision. Its
referenced local evidence artifacts exist, but the records do not establish the
source revision for each mode. Those historical summaries remain in
`tool-status.tsv` as context and were not promoted to mode-level passes. No
historical artifact was proven to come from a different revision, so unknown
provenance is recorded as `unrecorded`/`unverified`, not mislabeled as stale.

The `auto_constrain` live modes also remain blocked on an eligible Fusion account
entitlement. Its blocker is recorded in the mode ledger.

Current matrix totals: one unit pass and one initialized-protocol pass
(`export_step/default`); three blocked development-live and three blocked
production-live gates (`auto_constrain`); the remaining 1,204 gate entries are
unverified. The blocked live modes require an eligible account entitlement.

## Authoritative evidence

- [Generic scope and active tool inventory](generic-tool-audit.tsv)
- [Tool-level historical gate summaries](tool-status.tsv)
- [Per-mode evidence matrix](tool-mode-status.tsv)
- [Mechanical/drawing API pointer coverage](capability-coverage.tsv)
- [Generated audit view](audit-ledger.html)
- [Issue #1 execution breadcrumb](../tickets/issue-1-baseline.md)

The TSV ledgers are authoritative. Regenerate the HTML with:

```text
python -m scripts.audit_mechanical_api docs/mechanical/audit-ledger.html --html
```

## Validation

- `uv run pytest tests/test_mechanical_coverage.py tests/test_instructions_sync.py tests/test_tools.py -q` — 49 passed.
- `uv run pytest tests/test_addon_api_usage.py tests/test_protocol_e2e.py -k "step_export" -q` — 10 passed, 121 deselected.
- `uv run ruff check scripts/audit_mechanical_api.py tests/test_mechanical_coverage.py` — passed.
- The opt-in Fusion-live tests were not run: no named test-owned design/fixture
  was supplied, and production-live checks require a production add-in restart.
