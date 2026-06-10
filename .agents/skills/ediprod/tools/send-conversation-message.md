# send-conversation-message

Posts an internal user message to an incident conversation visible to staff only. Customers cannot see these messages.

## When To Use

- Leaving an internal investigation note on an incident
- Recording status, triage, or handoff context that should not be customer-facing

Use this tool for incident conversations only. The job ID must be a valid incident number starting with `CS`.

## Message Guidelines

- Write a free text message with basic formatting only.
- Do not rely on Markdown formatting.
- Keep the message under 250 words for readability in the conversation UI.
- Provide exactly one of `message` or `file`.
- When using `file`, it must point to an existing UTF-8 file.
- For detailed supporting information, attach a document with `file upload` and reference it in the message.

## Input

```yaml
jobId:
  type: string
  required: true
  description: Incident identifier (CS...).
message:
  type: string
  required: false
  description: Internal message text to post.
file:
  type: string
  required: false
  description: Read internal message text from a UTF-8 file.
```

> Conversation messages are supported only for incidents. Messages sent by this tool are always internal user messages.
> Provide exactly one of `message` or `file`. If `file` does not exist, the tool returns `File not found: <path>`.

## Output

Posts the message and returns confirmation, or validation/not-found text.

## Examples

```
send-conversation-message(jobId: "CS02134514", message: "Internal investigation note")
send-conversation-message(jobId: "CS02134514", file: "./note.md")
```
