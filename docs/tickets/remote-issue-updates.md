# Remote issue update and closeout procedure

Use this procedure for any repository ticket. Local breadcrumbs, commits,
pushes, and displayed edit forms do **not** update GitHub acceptance
checkboxes or establish that an issue is complete. See
[the project ticket-management rules](../../AGENTS.md#ticket-management).

## Required access method

Use authenticated GitHub REST through PowerShell `Invoke-RestMethod` for
issue-body/checklist and state updates. Obtain authentication from the
existing Git credential helper as described below. Do not substitute the
GitHub MCP `issue_write` tool: it can display an interactive form without
performing an update.

REST can also read issues and comments and post resolution comments.
GitKraken MCP `issues_get_detail` and `issues_add_comment` are established
alternatives for reading and posting comments, respectively. Discover MCP
tools before invoking them; availability can change between sessions.

If the documented method fails, report closeout as blocked rather than
silently switching write methods. On **HTTP 401 Unauthorized**, stop and ask
the user for an alternative access method. Do not retry with another
credential or transport. A tool-specific 404 does not establish that an issue
is absent; verify the repository identity and use the documented REST read.

If an MCP edit form was already displayed, do not count it as a write or
submit that stale form after REST has updated the issue.

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
5. Serialize the complete updated body with `ConvertTo-Json`, then `PATCH`
   the issue endpoint with `-ContentType 'application/json'`.
6. Make a separate `GET`. Verify the exact intended body and checklist,
   including the expected checked and unchecked counts for this ticket.
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
5. `PATCH` the issue with `state: closed` and `state_reason: completed`.
   Do not use `Fixes`/`Closes` commit references to bypass these gates; use
   `Refs #<number>` until the remote checklist and resolution are in place.
6. Perform fresh reads confirming `closed` / `completed`, the expected
   checklist, and the resolution comment.
7. Record the verified outcome and comment URL in the ticket breadcrumbs,
   parent plan, and dashboard. Commit, push, and merge/publish those records.
   Report failed remote operations as blocked, never complete.

## REST request reference

Set the API base from the verified repository:
`https://api.github.com/repos/<owner>/<repo>`.
Replace `<number>` with the actual issue number and `<comment-id>` with the
ID returned when the resolution comment was posted.

| Purpose | Method | Endpoint | JSON payload |
| --- | --- | --- | --- |
| Read current issue body/state | `GET` | `/issues/<number>` | None |
| Update acceptance criteria | `PATCH` | `/issues/<number>` | `{"body":"<complete updated issue body>"}` |
| Reopen for an added requirement | `PATCH` | `/issues/<number>` | `{"state":"open"}` |
| Read a page of comments | `GET` | `/issues/<number>/comments?per_page=100&page=<page>` | None |
| Post a resolution comment | `POST` | `/issues/<number>/comments` | `{"body":"<resolution and evidence>"}` |
| Verify a posted comment directly | `GET` | `/issues/comments/<comment-id>` | None |
| Close after all gates pass | `PATCH` | `/issues/<number>` | `{"state":"closed","state_reason":"completed"}` |

## Credential handling

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

## Historical evidence

The [migration ticket breadcrumbs](ticket3.md) record the original working
REST and MCP operations, evidence commits, and resolution permalinks.
Those ticket-specific IDs, acceptance counts, branch names, and reopen
history are examples, not defaults for subsequent tickets.
