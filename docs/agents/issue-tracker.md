# Issue tracker: GitHub

Issues for this repository live at
`https://github.com/Q-Bot2021/fusion360-mcp-server`.
Confirm the repository identity from this repository's `git remote -v` before
remote writes.

## Read and write

- Use the available GitHub or GitKraken read tools, or authenticated GitHub
  REST, to read issues and comments.
- Publish new tickets and native sub-issue relationships to
  `Q-Bot2021/fusion360-mcp-server` using authenticated GitHub REST and the
  existing Git credential helper; do not print or persist credentials.
- For issue-body, checklist, state, and closeout writes, follow [the repository
  procedure](../tickets/remote-issue-updates.md). Read the current issue
  immediately before a write and verify the result with a fresh read.
- Do not use GitHub MCP `issue_write` for issue-body/checklist/state changes; a
  displayed form is not proof of a write.
- Post resolution comments using the repository procedure and verify the
  posted comment and issue association.
- Pull requests are not a request surface by default.

## Triage

Use the label mapping in [triage-labels.md](triage-labels.md). Ask the user
before creating any label missing from GitHub.
