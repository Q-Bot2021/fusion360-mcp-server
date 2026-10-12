# Development Rules

## Required Gates

- **[UNIT]** All newly developed executable code requires unit tests in the same change. Changed behavior requires updated tests and regression coverage. Test success, invalid input, meaningful boundaries, errors and side effects. Documentation-only edits require documentation checks, not artificial unit tests.
- **[E2E]** Every new or changed MCP tool, resource and resource template must pass both MCP protocol end-to-end tests and live local-Fusion end-to-end tests before production registration or publication of the change. Missing prerequisites, skipped tests and mock success are not live acceptance.
- **[SYNC]** `.claude/CLAUDE.md` and `.github/copilot-instructions.md` must contain identical agent-neutral instructions. Update both in the same change. CI compares complete content, normalizing only CRLF/LF line endings; do not silently repair drift in CI.

## Generic Applicability

All MCP modeling, query and document tools must be generically applicable to any
given part or design for which Fusion supports the requested operation. Use
explicit targets, parameters and entity/sketch coordinate systems, not assumptions
about a test project, fixture name, stencil layout, fixed XY orientation,
root-only component or fixed cloud project. Test fixtures may use these
conventions; production tool contracts must not require them.

Document and reject unsupported geometry, design types and API prerequisites
clearly before mutation. Preserve security policy, validation, mutation consent,
document identity checks and the prohibition on blind mutation retries. Generic
applicability does not mean every operation is valid on every entity.

Do not promote a specialized implementation by merely renaming it. Demonstrate
unit, protocol and live acceptance on meaningfully different applicable parts,
orientations and component contexts. Audit existing registrations without
retroactive disabling; keep fixed development maintenance commands explicitly
scoped as infrastructure rather than modeling capabilities.

## Audit Ledger Maintenance

Tool creation, updates, renames, promotion and removal require same-change updates
to `docs/mechanical/generic-tool-audit.tsv` and affected acceptance entries in
`docs/mechanical/tool-status.tsv`. Keep source-revision evidence and pending gates
accurate; changed behavior must reopen invalidated acceptance. Skipped tests,
mock responses and registration alone never justify a passing live gate.

Regenerate the offline report with
`python -m scripts.audit_mechanical_api docs/mechanical/audit-ledger.html --html`.
The TSV files are authoritative; do not edit generated HTML status cells by hand.
Run `tests/test_mechanical_coverage.py` to verify registry coverage and report
freshness, and `tests/test_instructions_sync.py` for synchronized guidance.

## Framework and Commands

The project uses pytest, AnyIO, the MCP Python SDK and Ruff. Configuration and development dependencies are in `pyproject.toml`. Tests are discovered under `tests/`. The package requires Python 3.10 or newer; current CI tests Python 3.12 on Ubuntu, not every supported version. Use Python 3.12 when a newer interpreter lacks dependency wheels.

```text
uv sync --dev --python 3.12
uv run --python 3.12 pytest -v -ra
uv run --python 3.12 pytest tests/test_tools.py -v
uv run --python 3.12 pytest -k disabled -v
uv run --python 3.12 pytest -m protocol_e2e -v
uv run --python 3.12 ruff check
```

Ruff checks E/F/I rules with an 88-column configuration. Lint is not behavioral testing. CI currently lints `src/` and `tests/`; run the full Ruff command locally before submitting. Do not claim success for checks not executed.

## Versioning and Builds

Use `MAJOR.MINOR.REVISION` for the release version:

- Increment the major version manually.
- Increment the minor version automatically whenever a new tool is added to the production MCP registry.
- Increment the revision automatically whenever any production-registered element is updated.
- Increment the `bNN` build number automatically each time a distributable package is built. The build number is independent of the release version.

## Test Ownership

For API research, use the [Autodesk API pointer index](docs/fusion-api/README.md).
Search by qualified symbol or action and fetch the relevant official pages on
demand. The pointer snapshot is not a substitute for current signatures,
installed-version checks, unit tests or live acceptance. Index maintenance uses
`scripts/index_fusion_api.py` and `tests/test_api_index.py`; no runtime MCP
capability is registered by this documentation index.

| Test Area | Existing Home | What It Establishes |
| --- | --- | --- |
| Schemas, annotations, active registry | `tests/test_tools.py` | Tool definition contracts and disabled visibility |
| Mock handlers | `tests/test_mock.py` | Deterministic simulated results, not Fusion behavior |
| Routing and formatting | `tests/test_server.py`, `tests/test_feedback.py` | Request helpers, errors, hints, deltas and images |
| TCP transport | `tests/test_connection.py`, `tests/test_socket_server.py` | Loopback JSON exchange, retries, endpoint policy |
| Add-in mirrors and API usage | `tests/test_addon_sync.py`, `tests/test_addon_api_usage.py` | Drift guards, static checks and isolated executable guards |
| Geometry and units | `tests/test_hole_geometry.py`, `tests/test_parameter_units.py` | Pure computation and unit conversions |
| Instruction equivalence | `tests/test_instructions_sync.py` | Equal instructions, context links and mandatory policies |
| MCP protocol | `tests/test_protocol_e2e.py`, `tests/test_candidate_e2e.py` | Initialized SDK sessions, real request handlers and isolated candidate routing |
| Live Fusion | `tests/test_fusion_e2e.py` | Explicit, read-only local API acceptance with named fixtures |

Reuse nearby tests and helpers. Mock external dependencies at their boundaries, not the behavior being tested. Static AST checks supplement executable tests; they do not prove Fusion behavior. `scripts/smoke_envelope.py` prints helper-level examples and is not an MCP or live E2E test. A socket echo server tests transport, not CAD correctness.

## Before Registration

### Development Registration and Production Promotion

Unit-tested candidates may be registered before E2E acceptance only in an isolated
development MCP server/add-in profile. The production CLI and normal discovery
must not expose them. Development registration is not production acceptance.
Use the same request handlers and local transport to obtain protocol and live
evidence, then promote eligible candidates to production in a separately reviewed
change. Disabled code execution and loopback policies apply to both profiles.
Preview-dependent candidates stay local/non-production even when tests pass.

Use the isolated candidate-test pattern in `tests/test_candidate_e2e.py`.
The reusable CAD development MCP is retained: `tests.development_mcp` and the
separate `Fusion360MCPDev` add-in on numeric loopback port 9877. Its private event
and handler modules are isolated from production. `dev_reload_candidates` accepts
no arguments and reloads only fixed, hash-owned CAD handler modules on Fusion's
main thread; it never accepts Python, paths or module names or reloads transport.
Stage reviewed source with `scripts.install_development_addin`, then reload.
Bootstrap or schema changes may still require restarting the add-in/client.
Electronics development is excluded; electronics callbacks and fixtures remain
removed. Removing a domain does not remove the shared development infrastructure.
There is no production CLI/environment enable switch or arbitrary execution
exception for development testing.

### Temporary Test Cleanup

Record ownership and content hashes when staging temporary scripts/add-ins.
After testing, stop their servers/events, remove temporary installed scripts and
retire obsolete one-off runner source. Preserve reports needed for acceptance.
Cleanup must refuse changed files, symlinks and escaped paths and leave unrelated
files/designs untouched. Keep reusable fixture source and unit tests; remove its
temporary installation when the session ends. Use recorded content hashes for
ownership verification and document any cleanup still pending. The retained
development MCP/add-in is reusable infrastructure, not a temporary one-off script;
do not uninstall it at session end unless explicitly requested. Stop its running
test session when appropriate, while preserving the installation and client entry.

1. Implement the candidate handler and mock with unit tests, without adding the candidate to the normal production registry.
2. Stage its definition and dispatch in an isolated test process/session. `build_server()` constructs the same request handlers as the CLI; the SDK memory-session helper supports test-only registry injection. See `tests/test_candidate_e2e.py`. Test-only patches must not be shipped as production flags.
3. Use an SDK client to initialize MCP, discover the staged tool/resource/template, invoke it with meaningful valid and invalid inputs, and assert returned content, error envelopes and intended state. Merely calling `_send`, rebuilding expected strings or passing empty arguments to permissive mocks is insufficient.
4. Repeat the capability's actual workflow through MCP stdio and the locally installed Fusion add-in. Verify expected geometry, units, names, parameters, resource data, file contents or CAM state as applicable. Add capability-specific live cases; the existing read-only smoke suite is not acceptance for every tool.
5. Record passing evidence for the exact revision, then register/publish the tool or resource and update schemas, annotations, mock dispatch, drift checks and coverage inventory together. Reviewer approval requires both E2E layers. Never bypass disabled execution or loopback policy to obtain test coverage.

For resource candidates, stage the actual proposed resource definition and reader in the isolated server, not a duplicate approximation of its handler. Test both enumeration and `resources/read`; template cases must include concrete named URIs and encoded names. Do not add a network transport just for testing.

## Live Test Safety

Normal runs visibly skip `fusion_e2e`. Explicit live runs fail if no live tests are selected, Fusion cannot be reached, a required fixture is absent or assertions fail. Do not skip a capability after requesting live acceptance.

On a local Windows/macOS Fusion host, open a disposable test design containing named body and component fixtures, start the updated add-in, then run:

```text
uv run --python 3.12 pytest -m fusion_e2e --run-fusion-e2e --fusion-test-body AcceptanceBody --fusion-test-component AcceptanceComponent -v
```

The supplied suite only reads data. Future mutation cases require explicit user consent and a disposable design, one operation per tool call, named test-owned objects and assertions after each step. Never run `delete_all` against an existing user design. Export into approved temporary directories. Use representative safe manufacturing fixtures and required Fusion workspaces. Clean up only test-owned objects and close sockets/processes; preserve useful failure evidence. Never use `execute_code`.

Use numeric IPv4 loopback only. Tests may select a different local port when supported; they must not connect to a remote Fusion host. Restart the installed add-in after copying changed source; repository edits alone do not update the running add-in.

## Evidence and Existing Coverage

For each new/changed capability, include its name/URI, source revision, test cases and commands, Fusion version/platform, fixture prerequisites, assertions, pass/fail and relevant artifacts in the PR. A skipped or pending result does not authorize registration. Linux CI cannot certify real Fusion execution; a maintainer must review local evidence before accepting registration changes. Required CI branch protection is an administrator setting, not something instruction text alone enforces.

Existing unchanged registrations remain available. Their historical live coverage is unverified until evidenced; the current migration does not retrospectively hide them. Track missing cases as backlog rather than presenting mock coverage as live acceptance.

| Capability Inventory | Protocol Coverage | Live Coverage |
| --- | --- | --- |
| All active tool names from `get_tool_list()` | Discovery checked; invocation cases currently cover `ping`, `get_object_info`, `extrude` errors and disabled/unknown calls | Only `ping`, `get_scene_info` and named object/resource reads have supplied live cases; execution evidence pending |
| `fusion360://status`, `fusion360://design`, `fusion360://parameters` | Discovery and reads checked through stdio | Supplied read-only cases; execution evidence pending |
| `fusion360://body/{name}`, `fusion360://component/{name}` | Enumeration and concrete/encoded name reads checked | Supplied cases require named fixtures; execution evidence pending |
| Remaining active tools | Unit/mock/transport coverage is not per-tool E2E; audit backlog | Capability-specific workflows and execution evidence required |
| `execute_code` | Absent from discovery; forged requests and lower-level calls rejected | Disabled, never an acceptance candidate |

Derive current tool names from the registry rather than copying stale counts. Extend the inventory when adding cases and attach exact-revision results; no blanket claim of E2E coverage is permitted.

## Synchronization and Review

Both agent instruction files link here and require these gates. `tests/test_instructions_sync.py` detects one-sided edits, missing context links and omitted policy clauses. Keep `AGENTS.md` guidance consistent, without requiring that larger document to be an identical copy.

Before submission: run focused tests, the normal full suite and Ruff; inspect the diff; identify live checks still pending; review new/changed registration evidence. Retained disabled source is not an invitation to re-enable arbitrary code or remote networking. Other CAD/import/export capabilities are not a general sandbox, and loopback does not prevent administrator-created tunnels.