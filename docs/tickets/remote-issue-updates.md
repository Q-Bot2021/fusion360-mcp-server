# Remote issue update and closeout procedure

Use this procedure for any repository ticket. Local breadcrumbs, commits,
pushes, and displayed edit forms do **not** update GitHub acceptance
checkboxes or establish that an issue is complete. See
[the project ticket-management rules](../../AGENTS.md#ticket-management).

## Primary path: secondary GitHub MCP without forms

Use the official **`github-secondary` MCP** first for ticket operations.
Discover the named tools before calling them; this connection's name does
not make it the fallback. Authenticated GitHub REST is the fallback below,
not the primary GitHub MCP or GitKraken.

The connection must execute writes directly, without asking the user to
complete an issue form. Configure the official remote server with:

```json
"X-MCP-Features": "mcp_apps_disable_form_deferral"
```

Place this in the secondary server's `headers`, alongside its existing
Authorization reference, then reload that connection. Preserve other enabled
feature flags if present. For the official local server use
`--features mcp_apps_disable_form_deferral`. See
[GitHub's configuration guide](https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md).
Send complete operation parameters; there is no per-call `no_form` argument.
Authentication setup and host-required tool approval are separate from forms.

If a form appears, the write is pending, not successful. Cancel/dismiss it,
reconcile the remote issue, and use the REST fallback without submitting a
form. If cancellation cannot be confirmed, report the operation blocked rather
than risking a delayed duplicate. Never submit a stale form after fallback.
Only fresh remote read-back establishes completion.

### MCP operation reference

Always supply the verified `owner` and `repo` where the schema requires them:

- Identity: `get_me`; list/search: `list_issues`, `search_issues`. Paginate
  using each tool's schema; search indexing is not authoritative read-back.
- Read: `issue_read` with `get`, `get_comments`, `get_labels`,
  `get_parent`, or `get_sub_issues`.
- Create: `issue_write(method: create, title, body, ...)`. Record the returned
  issue URL/number and IDs immediately; a response may contain only ID and URL.
- Edit: `issue_write(method: update, issue_number, ...)`. Supply only intended
  fields; `body` replaces the entire body. Use explicit empty arrays when
  clearing labels or assignees.
- Comments: `add_issue_comment`; edit a conversation comment with
  `update_issue_comment(comment_id, body)`. Record its numeric ID and URL.
  Read paginated comments to confirm exact content and issue association.
- State: `issue_write(method: update, issue_number, state: open)` to reopen;
  use `state: closed, state_reason: completed` only after the closeout gates.
- Hierarchy: `sub_issue_write` with `add`, `remove`, or `reprioritize`.
  `sub_issue_id` is the numeric database ID, not the issue number or GraphQL
  node ID. `replace_parent: true` explicitly moves an existing child.
  `issue_write(method: create, parent_issue_number: ...)` can create and attach
  a child. Verify both directions and child order.
- Discover supported issue types/fields with `list_issue_types` and
  `list_issue_fields` before using them; personal repositories may expose none.
- Blocking dependencies and comment deletion are REST fallback operations when
  absent from discovery. Permanent issue deletion uses GraphQL, not REST;
  reserve destructive cleanup for explicitly authorized test-owned issues.

## Fallback and errors

Use authenticated REST through PowerShell `Invoke-RestMethod` when a required
MCP tool is unavailable, the connection cannot execute without forms, or a
recoverable transport failure prevents completion. Report the failed primary
operation and fallback used. Re-read remote state before fallback or retries:
an interrupted response can follow a successful mutation.

On **HTTP 401 Unauthorized**, stop and ask for an alternative access method;
do not automatically try another credential or transport. On permission 403,
inspect repository selection and effective token grants; the
`X-Accepted-GitHub-Permissions` response header states endpoint requirements,
not actual token grants. Report authorization/policy blockers instead of
silently broadening permissions. A read success does not establish write access.

For rate-limited 403/429, honor `Retry-After` or rate-reset headers with bounded
backoff. Treat 422 as a payload problem, not a transient retry. For timeouts or
5xx, inspect the issue/comment before repeating any write. A tool-specific 404
does not establish absence; confirm target and access through a direct read.
Serialize mutations and pace sustained batches per
[GitHub's API guidance](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api).

## Establish the target

Immediately before remote writes:

1. Re-read this procedure.
2. Confirm the repository owner/name from the intended project's Git remote.
   Obtain the issue number from the task or ticket breadcrumbs; never use
   placeholder repository identities or assume another project's remote.
3. Fetch the current issue and confirm its number, title, state, and acceptance
   criteria. Read predecessor evidence and confirm any blockers are resolved.
4. Continue the existing ticket branch when resuming work. Do not reopen or
   mutate a completed issue simply to test this procedure.

For creation, choose a unique operation marker and check the paginated
repository list for matching tickets before POST or retry. Record created
identifiers immediately; lists can briefly lag direct issue reads.
Create native parent/child links and explicit blockers, then read back every
relationship before recording local breadcrumbs.

## Update acceptance criteria

1. Commit and push the implementation and validation evidence.
2. Fetch the latest issue body. Require the exact expected task text and
   checkbox state before modifying it. Change only criteria supported by
   published evidence; leave unmet criteria unchecked and explain blockers.
3. Preserve all other sections. An issue-body update replaces the complete
   body, so do not reconstruct it from local notes or a stale copy.
4. Check for intervening changes immediately before writing and stop on
   conflicting content. This read-before-write check reduces, but does not
   eliminate, concurrent-edit races.
5. Send the complete updated body through secondary MCP
   `issue_write(method: update)`. For fallback, serialize with `ConvertTo-Json`
   and `PATCH` with `-ContentType 'application/json'`.
6. Make a separate `issue_read(get)` or REST `GET`. Verify the exact body and
   checklist, including expected checked and unchecked counts for this ticket.
   Do not treat a successful request or displayed form as verification.

For a genuinely new acceptance requirement, add an unchecked task and
explicitly reopen a closed issue if needed. Verify the new task and open
state before continuing implementation. Do not silently check newly added
requirements.

## Publish, resolve, and close

1. Merge the ticket implementation into `main` and push. Preserve concurrent
   work and verify that the implementation commit is contained in remote
   `main`, not merely in a local branch or the remote ticket branch.
2. Post a resolution comment containing:
   - the outcome and links to the published implementation commit and evidence;
   - validation commands/results, including checks not run and their reasons;
   - remaining provisional decisions, limitations, and follow-up tickets.
3. Read the posted comment back using its returned ID and verify its body,
   issue association, and permalink. If checking a comment list, paginate it:
   absence from one page is not proof that a comment does not exist.
4. Before closure, fetch the issue again. Verify its acceptance criteria are
   complete, the resolution comment exists, and remote `main` includes the
   implementation. Stop if any condition is unmet.
5. Use secondary MCP `issue_write(method: update)` with `state: closed` and
   `state_reason: completed` (REST fallback: `PATCH` the issue).
   Do not use `Fixes`/`Closes` commit references to bypass these gates; use
   `Refs #<number>` until the remote checklist and resolution are in place.
6. Perform fresh reads confirming `closed` / `completed`, the expected
   checklist, and the resolution comment.
7. Record the verified outcome and comment URL in the ticket breadcrumbs,
   parent plan, and dashboard. Commit, push, and merge/publish those records.
   Report failed remote operations as blocked, never complete.

## REST fallback reference

Set the API base from the verified repository:
`https://api.github.com/repos/<owner>/<repo>`.
Replace `<number>` with the actual issue number and `<comment-id>` with the
ID returned when the resolution comment was posted.

| Purpose | Method | Endpoint | JSON payload |
| --- | --- | --- | --- |
| Create a ticket | `POST` | `/issues` | `{"title":"<title>","body":"<body>"}` |
| Read current issue body/state | `GET` | `/issues/<number>` | None |
| Update acceptance criteria | `PATCH` | `/issues/<number>` | `{"body":"<complete updated issue body>"}` |
| Reopen for an added requirement | `PATCH` | `/issues/<number>` | `{"state":"open"}` |
| Read a page of comments | `GET` | `/issues/<number>/comments?per_page=100&page=<page>` | None |
| Post a resolution comment | `POST` | `/issues/<number>/comments` | `{"body":"<resolution and evidence>"}` |
| Edit a conversation comment | `PATCH` | `/issues/comments/<comment-id>` | `{"body":"<updated comment>"}` |
| Verify a posted comment directly | `GET` | `/issues/comments/<comment-id>` | None |
| Close after all gates pass | `PATCH` | `/issues/<number>` | `{"state":"closed","state_reason":"completed"}` |

For dependency fallback, POST `/issues/<number>/dependencies/blocked_by` with
`{"issue_id": <numeric blocker ID>}`, then GET that path to verify.
DELETE `/issues/<number>/dependencies/blocked_by/<numeric blocker ID>` removes
the dependency. Comment deletion is DELETE `/issues/comments/<comment-id>`.
Verify absence after removals.

If hierarchy fallback is needed, POST `/issues/<parent-number>/sub_issues`
with `{"sub_issue_id": <numeric child ID>}`; detach with DELETE
`/issues/<parent-number>/sub_issue` and the same body (singular `sub_issue`).
GET the parent's `/sub_issues` and child's `/parent` to verify.

Permanent deletion, when authorized, is a GraphQL `deleteIssue` mutation
using the issue's `node_id`. Deleted issues returned HTTP 410 in the sandbox;
an empty list alone is insufficient verification. Closure is acceptable
cleanup when deletion is unavailable and the owner has authorized it.

## REST credential handling

From the intended repository's working directory, set process-local
`GIT_TERMINAL_PROMPT=0` and `GCM_INTERACTIVE=Never`. Supply this request to
`git credential fill` through standard input:

```text
protocol=https
host=github.com

```

Capture the returned `key=value` lines in memory and parse them into a
hashtable; **never print them**. Fail explicitly if the helper fails or
returns no credential. Use its `password` field as the bearer credential.
Set these REST headers:

- `Authorization`: `Bearer ` followed by the in-memory credential;
- `Accept`: `application/vnd.github+json`;
- `X-GitHub-Api-Version`: `2022-11-28`.

Use `ConvertTo-Json` for request bodies and `-ContentType 'application/json'`
for writes. Fail explicitly if any expected task, comment, checklist,
published commit, or state is missing.

Clear credential/header hashtables and the captured helper output in a
`finally` block. This limits retention; it is not a secure-memory-erasure
guarantee. Never include helper output, authorization headers, tokens, or
credential dumps in logs, transcripts, scripts, screenshots, or commits.
Do not store credentials or change persistent execution/security policy.

## Verification evidence

On 2026-10-19, a fresh MCP protocol connection using the secondary server's
configured endpoint, credential, and no-form header passed all discovered
issue-tool names in the `Q-Bot2021/Agent_Instructions` sandbox: identity,
list/search, read, create/update, add/edit comments and reactions, types/fields
discovery, and sub-issue add/remove/reorder/reparent. Title/body/checklist,
labels/assignees (including clearing), and close/reopen were read back.
REST covered create/edit/comment/close/reopen, blockers, and comment deletion;
GraphQL deleted owned fixtures. An invalid MCP create failed explicitly without
a form or mutation. Independent reads confirmed reactions and exact edits.
No forms were submitted in that no-form protocol test. Earlier form-enabled
attempts are not unattended evidence. Host reload is required to use the saved
header; the previously loaded host tool path was not certified by this test.
Custom field/type and milestone mutations, other repository tools, and
fault-injection/load tests were outside this acceptance scope. Target-project
read access was verified; production tickets were not mutated for testing.
