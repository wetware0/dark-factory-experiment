---
name: ediprod-cli
description: "Use the edi CLI to query or update ediProd/PAVE data: incidents (CS), work items (WI), projects (PRJ), workflows, tasks, issues, files, staff, and lookups. Each command embeds complete documentation including field schemas, status codes, and real-world patterns — use `edi <command> --help` for domain reference."
---

# ediProd CLI — Skill Index

`edi` is the terminal interface for ediProd/PAVE — WiseTech's in-house incident and work management system built on CargoWise. It exposes structured access to incidents, work items, projects, workflows, tasks, automated crash records (issues), and attached documents.

## Domain Map

All three job types (WI, CS, PRJ) share the same sub-structure: each has workflows → tasks → files. Use the job number to query their workflows and files.

| Domain       | Prefix           | CLI alias      | Documentation           | Description                                            |
| ------------ | ---------------- | -------------- | ----------------------- | ------------------------------------------------------ |
| Incidents    | CS               | `incident\|cs` | `edi incident --help`   | Client-reported issues/requests from CargoWise Support |
| Work Items   | WI               | `workitem\|wi` | `edi workitem --help`   | Internal dev units: bug fixes, features, refactors     |
| Projects     | PRJ              | `project\|prj` | `edi project --help`    | Top-level delivery containers: onboarding, programs    |
| Workflows    | UUID             | `workflow\|wf` | `edi workflow --help`   | Ordered stages of work within a job                    |
| Tasks        | UUID             | `task`         | `edi task --help`       | Atomic work units within a workflow                    |
| Issues       | GUID             | `issue`        | `edi issue --help`      | Automated crash records: exceptions, stack traces      |
| Files        | ediprod:/// URL  | `file`         | `edi file --help`       | eDocs attached to jobs                                 |
| Staff        | code e.g. JDS    | `staff`        | `edi staff --help`      | WTG employees and their capabilities                   |
| Capabilities | code e.g. RATING | `capability`   | `edi capability --help` | Roles used for task assignment                         |
| Lookups      | —                | `lookup`       | `edi lookup --help`     | Reference data: product and module codes               |

**Key relationships:**

- Job (WI/CS/PRJ) → workflows (ordered) → tasks (sequential) → task notes
- Job → attachedDocuments (eDocs) + attachedIncidents + attachedWorkItems + attachedProjects + attachedIssues
- Task → assigned staff code or capability code
- Issues (automated crash records) appear as `attachedIssues` on jobs — query with `edi issue get <issueId>` and `edi issue exception get` for full exception details

## Global Flags (BEFORE the subcommand)

```bash
edi --format jsonl --fields number,title,status incident list ...
#   ^^^ global flags ^^^                          ^^^ subcommand ^^^
```

| Flag               | Description                                                  |
| ------------------ | ------------------------------------------------------------ |
| `--format <fmt>`   | Output format (see table below)                              |
| `--fields <list>`  | Comma-separated field subset — always limit to what you need |
| `--limit <n\|all>` | Max records; default 50; `all` fetches up to 1000 records    |

## Output Formats

| Format           | When to use                                                             |
| ---------------- | ----------------------------------------------------------------------- |
| _(default/toon)_ | Human display; do NOT parse — output is not machine-stable              |
| `json`           | Single `get` or scripting; full structured object                       |
| `jsonl`          | List queries + jq pipelines; one JSON per line; most efficient for bulk |
| `ids`            | IDs-only output — use to pipe into `xargs` or loops                     |
| `yaml`           | Human-readable alternative to json                                      |

**Rule of thumb:** `--format jsonl` for lists, `--format json` for single gets, `--format ids` to pipe IDs.

## Date Filters

Date filter availability is command-specific; run `edi <entity> <action> --help` to see which date fields can be filtered. Date values use ISO 8601 calendar dates (`YYYY-MM-DD`) and range filters are inclusive on both ends.

## Exit Codes

| Code | Meaning                                   |
| ---- | ----------------------------------------- |
| 0    | Success (including empty results)         |
| 1    | Unexpected error (network, parse, config) |
| 2    | Not found                                 |

Empty results in machine formats (`json`, `jsonl`, `ids`) return empty arrays or zero lines — always parseable. Default `toon` emits prose like "No X found."

## Authentication

If unauthenticated or session expired, stop using the CLI and notify the user. Do not attempt to re-authenticate within the CLI or prompt for credentials.

## Presenting Jobs to Users

Always include the `url` field as a clickable markdown link when showing a job. The `url` field is returned by `edi incident get`, `edi workitem get`, and `edi project get`.

```markdown
[CS02134514](https://ediprod.cw.wisetechglobal.com/...)
[WI00902989](https://ediprod.cw.wisetechglobal.com/...)
```

## Common Multi-Domain Patterns

### Full investigation workflow

```bash
# 1. Read the job (triage first, only fetch what you need)
edi --fields number,title,status,criticality,product,module,conversation,attachedDocuments \
  incident get CS02134514

# 2. Find tasks with left notes (e.g. root cause analysis, PR links, workarounds)
edi --format ids workflow list CS02134514 | \
  xargs -I{} edi --format jsonl --fields id,type task list {} --has-notes

# 3. Read those notes (root cause, PRs, workarounds)
edi task notes read <taskId>
```

### Pipe workflow IDs to task queries

```bash
edi --format ids workflow list WI00902989 | \
  xargs -I{} edi --format jsonl --fields id,type,staff task list {} --status OPN ASN WRK
```

### Batch read all attachments

```bash
mkdir -p /tmp/docs
edi --format json --fields attachedDocuments incident get CS02134514 | \
  jq -r '.attachedDocuments[] | .url + "\t" + .fileName' | \
  while IFS=$'\t' read -r url name; do
    edi file read "$url" > "/tmp/docs/${name}.md" 2>/dev/null && echo "Read: $name"
  done
```

### Count items by field (hotspot analysis)

```bash
edi --format jsonl --limit all --fields module incident list \
  --product ENT --created-after 2026-01-01 | \
  jq -r '.module' | sort | uniq -c | sort -rn
```
