# Issue tracker: GitHub

Issues for this repository live at
`https://github.com/Q-Bot2021/fusion360-mcp-server`.
Confirm the repository identity from this repository's `git remote -v` before
remote writes.

## Read and write

- **Primary:** discover and call the official `github-secondary` MCP tools
  without user forms for reads, creation, edits, comments, state changes,
  labels/assignments, and native sub-issues. "Secondary" names the connection,
  not its priority; use it before other GitHub connections.
- **Fallback:** authenticated GitHub REST for unavailable MCP operations or
  recoverable transport/form failures, following [the remote issue
  procedure](../tickets/remote-issue-updates.md). It owns no-form setup,
  credential/error handling, reconciliation, and operation-specific tools.
- Read that procedure before publishing or changing tickets. Send complete
  parameters, reconcile ambiguous outcomes before retrying or switching paths,
  and verify every write with fresh remote reads.
- Use a native sub-issue for parent/child structure and an explicit blocking
  dependency for ordering; links in a body alone establish neither.
- Post and read back the resolution comment before closing a completed issue.
- Pull requests are not a request surface by default.

## Triage

Use the label mapping in [triage-labels.md](triage-labels.md). Ask the user
before creating any label missing from GitHub.
