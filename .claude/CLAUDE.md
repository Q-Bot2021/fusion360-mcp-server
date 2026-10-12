# Fusion360 MCP Server

## Context and Required Rules

Read and apply [Development and testing rules](../dev_rules.md) before developing code or registering MCP capabilities.

- **[UNIT]** All newly developed executable code requires unit tests in the same change. Changed behavior requires regression tests.
- **[E2E]** Every new or changed tool, resource and resource template must pass MCP protocol end-to-end tests and live local-Fusion end-to-end tests before production registration or publication of the change. Unavailable Fusion or skipped tests mean pending acceptance, not success.
- **[SYNC]** Keep [.claude/CLAUDE.md](../.claude/CLAUDE.md) and [.github/copilot-instructions.md](../.github/copilot-instructions.md) identical. Whenever either file changes, update both in the same change. Only CRLF/LF line-ending differences are allowed; CI enforces equivalence.

## Generic Applicability

All MCP modeling, query and document tools must be generically applicable to any
given part or design supported by the requested Fusion operation. Use explicit
targets and appropriate coordinate systems, not test-project, fixture-name,
stencil-layout, fixed-orientation, root-component or fixed-cloud-project
assumptions. Test conventions must not become production tool requirements.
Clearly document and reject unsupported entities and API prerequisites before
mutation. Preserve all security, validation, consent and no-blind-retry rules.
Generalize specialized implementations before promotion; a rename is insufficient.
Verify differing applicable parts, orientations and component contexts through
unit, protocol and live tests. Keep development maintenance explicitly scoped.

## Audit Ledger Maintenance

Maintain the audit ledger in the same change as every tool creation, update,
rename, promotion or removal. Update `docs/mechanical/generic-tool-audit.tsv`
and the affected acceptance entries in `docs/mechanical/tool-status.tsv`; record
evidence, limitations and pending gates honestly. A skipped test, mock response,
or production registration is not live acceptance. Reopen acceptance when a
behavior change invalidates prior evidence; do not carry forward stale checks.
Regenerate `docs/mechanical/audit-ledger.html` with
`python -m scripts.audit_mechanical_api docs/mechanical/audit-ledger.html --html`
and run `tests/test_mechanical_coverage.py` plus `tests/test_instructions_sync.py`.
The TSV files are authoritative; never hand-edit generated HTML status cells.

## Overview

This Python MCP server connects AI coding agents to Autodesk Fusion 360 for CAD automation. Agents communicate over stdio; commands are forwarded as JSON to the Fusion360MCP add-in installed in Fusion's AddIns folder.

```text
MCP client <-> stdio server <-> TCP 127.0.0.1:9876 <-> Fusion add-in <-> CustomEvent <-> Fusion main thread
```

Fusion API calls run on the main thread through a work queue and CustomEvent bridge. Mock mode requires no Fusion installation. Derive active capabilities from discovery rather than assuming historical tool counts.

## Security Policy

- `execute_code` is unconditionally disabled. Its source and definitions remain for reference, but it is not discoverable or callable. Never re-enable it or use it as a workaround.
- Both TCP endpoints are IPv4 loopback only. `--host` and `FUSION_MCP_HOST` accept only `localhost` or `127.0.0.1`, normalized to `127.0.0.1`. Custom local ports remain supported. No remote override or wildcard bind is allowed.
- Bundled TCP bridge startup is disabled. For VS Code devcontainers, run this MCP in the Windows-local user profile over stdio. Bridge cleanup requires user/admin approval; existing proxies are not removed by source edits.
- Do not introduce SSH, TCP relays, HTTP transports or policy enable switches. Loopback is not authentication or protection against administrator-created tunnels.

## Development

```text
uv sync --dev --python 3.12
uv run --python 3.12 pytest -v -ra
uv run --python 3.12 ruff check
```

Use focused tests after each behavior change. The normal suite includes instruction equivalence and MCP protocol checks; live tests require explicit selection and named fixtures as documented in `dev_rules.md`. Report unexecuted verification honestly.

## Key Files

- `src/fusion360_mcp/server.py`: Click CLI, shared server factory, resources and prompts.
- `src/fusion360_mcp/connection.py`: loopback TCP client and execution policy.
- `src/fusion360_mcp/tools.py`: retained definitions, annotations and active discovery.
- `src/fusion360_mcp/mock.py`: mock handlers, including explicit disabled-command errors.
- `src/fusion360_mcp/hints.py`: error classification, mirrored in `addon/server/hints.py`.
- `addon/server/command_handler.py`: Fusion handlers, dispatch and execution guards.
- `addon/server/socket_server.py`: loopback listener and client acceptance.
- `tests/`: unit, transport, drift, instruction, MCP protocol and opt-in live tests.

## Autodesk API Reference

Use the [API pointer index and lookup guide](../docs/fusion-api/README.md) to find
official API functions before developing tools. Search the linked TSV by qualified
symbol or member kind; do not load the whole index into context. Fetch the relevant
Autodesk pages on demand for signatures and behavior. The index contains pointers
only and is not evidence of installed-version support or MCP acceptance.

## Adding a Command or Resource

Unit-tested candidates may be registered in an isolated development MCP/add-in
profile before E2E testing. Normal production discovery remains unchanged until
protocol and live acceptance plus release eligibility are verified. No production
enable switch or arbitrary execution is permitted. Stop test sessions and clean
up temporary scripts/add-ins by recorded ownership and hashes; preserve evidence
and never delete modified or unrelated files. See `dev_rules.md` for the workflow.

## Electronics Scope Finding

Electronics development is excluded from this MCP. The inspected 2026 API was
largely preview/read-only; live checks on Fusion 2705.1.25 verified metadata edits
but no end-to-end path for component insertion, nets, placement, routing, fresh
ERC/DRC or manufacturing output. Absence of checked members does not prove that
all alternative APIs are unavailable. Do not claim unsupported authoring or infer
setters from readable properties. Electronics prototypes and tools were removed;
do not restore them without explicit scope approval and new acceptance evidence.
The general API pointer index remains reference data, not capability registration.

## Registration Workflow

Keep the reusable CAD development MCP and Fusion360MCPDev add-in for future work.
They are isolated from production on loopback port 9877 and exclude electronics.
`dev_reload_candidates` reloads only fixed, hash-owned CAD handlers, with no code
or path arguments. Cleanup applies to temporary test artifacts, not removal of
this shared development infrastructure unless explicitly requested.

1. Implement the candidate handler and mock with unit tests, without normal production registration.
2. Stage definitions and dispatch only in an isolated test session using the real MCP request handlers.
3. Pass meaningful protocol and live-Fusion E2E cases; record exact-revision evidence. Existing unchanged registrations are audited without retroactive disabling.
4. Only after acceptance, register the command/tool or resource/template. Add annotations and update registry, mock, drift and capability coverage checks together.
5. MCP command names map directly to add-in commands; no translation layer is needed. Reuse existing tests and helpers.

## Conventions

- Tool names use snake_case and match add-in command names exactly.
- All Fusion API lengths are centimeters. Name bodies, sketches and components explicitly.
- Use one operation per tool call and verify resulting state with queries/deltas. Render at logical checkpoints, not after every mutation.
- The add-in uses newline-delimited JSON over TCP. `ping` never accesses Fusion geometry.
- Every active tool has annotations and a mock handler. Mocks are not live geometry evidence.
- Never retry an ambiguous mutation blindly; inspect the design after errors.
- Use disposable designs and explicit consent for mutation acceptance tests. Never clear a user's existing design.
