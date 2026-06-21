---
name: sweep
description: End-of-chat sweep — distill the current conversation and file every save-worthy item into its correct home (memory, property files, daily log, tasks, decisions). Trigger on "/sweep", "sweep this chat", "save what matters", "what should we remember from this", or before closing a conversation. One run = nothing worth keeping gets lost.
---

# /sweep — end-of-chat memory sweep

Jeremiah's worry: durable things said in a chat vanish when the chat ends unless they get written to a file. This skill is the safety net. Run it before closing any conversation. It reads back over **this conversation**, pulls out everything worth keeping, **routes each item to its correct home** (not one big pile), previews, and on approval writes. The auto-commit Stop hook then pushes.

This is the conversation-level companion to `/daily closeout` (day-level) and the chat-history distillation pipeline (bulk historical). Use `/sweep` for the chat you're in right now.

## Modes

- **No arg (interactive)** — sweep **this** conversation, preview, write to homes on approval. The default below.
- **`nightly`** — automated batch. Runs unattended via launchd (~6:07pm Pacific, see `scripts/nightly_sweep.sh`). Scans the day's transcripts and writes **drafts only** to `review/sweep-<date>.md`. Never touches memory/context/tasks/decisions. Jeremiah approves in the morning. Spec below under **Mode: nightly**.
- **`apply`** — file the approved items out of a `review/sweep-<date>.md` draft into their real homes. Spec below under **Mode: apply**.

Everything from here to "Mode: nightly" describes the interactive default.

## The core move: route, don't dump

Saving everything to "memory" is the wrong instinct — it bloats the index and buries the signal. Each item has exactly one right home. Classify every candidate, then file it there:

| If the item is... | It goes to... |
|---|---|
| How I should *work* — a preference, correction, a confirmed way of doing things | a **memory file** in `…/memory/` + one line in `MEMORY.md` |
| A fact about a property, owner, vendor, or guest | the matching row/section in `context/properties.md` or `context/contacts.md` (and the property's project file if one exists) |
| Something that *happened* today (a purchase, a call, a fix) | today's `daily/YYYY-MM-DD.md` (My notes / Done lane) |
| A new to-do or follow-up | the right lane of `tasks/tasks.md` |
| A choice made + the reasoning | append to `decisions/log.md` |
| An external resource (URL, dashboard, ticket) | a `reference`-type memory file, or the relevant context file |

The air-fryer test: *"we bought an air fryer for the Example St property"* → operational event → today's daily log **and** a line on the `123 Example St` row in `context/properties.md` (appliance/expense). It does **not** become a memory file. But *"the operator wants every appliance purchase tracked per property"* → that's a working pattern → memory file.

## Run it

1. **Read back over the whole conversation.** Pull out every candidate fact, decision, event, task, preference, and resource.

2. **Filter out what doesn't belong.** Drop:
   - Transient chatter, greetings, thinking-out-loud that didn't land on anything.
   - Anything already recorded — check `MEMORY.md`, the relevant `context/` file, `decisions/log.md`, and `tasks/tasks.md` before adding. **Update the existing entry instead of duplicating.**
   - Anything the repo already encodes (code structure, CLAUDE.md content, git history).
   - For a would-be memory: if it only matters to this one conversation, skip it. Memory is for durable facts.

3. **Classify each survivor** into one home using the table above. If an item has two homes (the air fryer), file it in both — event to the daily log, standing fact to the property file.

4. **Preview before writing.** Show Jeremiah a grouped list: for each item, the one-line content and its destination file. Group by destination. Keep it scannable.

5. **On approval, write.** Follow each home's format exactly:
   - **Memory files** — one fact per file, kebab-case `name`, the frontmatter shape from CLAUDE.md's Memory section (`type: user | feedback | project | reference`; feedback/project get **Why:** and **How to apply:** lines). Link related memories with `[[name]]`. Add the one-line pointer to `MEMORY.md` — never put memory content in `MEMORY.md` itself.
   - **`decisions/log.md`** — match that file's existing entry format (date, decision, why, alternatives, owner).
   - **`tasks/tasks.md`** — correct lane, tag `[[property/owner]]`.
   - **Daily log** — append to **My notes** or **Done**; never overwrite that lane.
   - **`context/` files** — edit the matching row/section in place; convert relative dates to absolute.

6. **Report** what was filed and where, in one short block. The Stop hook commits and pushes.

## Mode: nightly (automated, drafts only)

This is the hands-off safety net so **no conversation is ever lost** — even one you closed without running `/sweep`. Transcripts are written to disk live as you chat, so they survive any kind of close (quit, window closed, crash). The launchd job `scripts/nightly_sweep.sh` fires ~6:07pm Pacific, finds the day's transcripts, and launches a headless Claude that runs this mode.

The runner hands you, in its prompt: today's date, the transcript directory, and an explicit list of session ids to sweep (it has already filtered out sessions in the ledger and its own prior runs). Your job:

1. **For each session id in the list**, read its transcript at `<transcript-dir>/<id>.jsonl`. These are raw JSONL — each line is a message event. Read the user/assistant message text; ignore tool-call noise. Skip a session that is empty, trivial, or is itself a nightly-sweep run (contains `NIGHTLY-SWEEP-RUN`).

2. **Distill exactly as the interactive mode does** — apply "the core move: route, don't dump." For each save-worthy item, determine its correct home (memory / property file / daily log / tasks / decisions) using the routing table above. Drop transient chatter and anything already recorded (check `MEMORY.md`, the relevant `context/` file, etc.).

3. **Write DRAFTS only — never the real homes.** Append to `review/sweep-<date>.md` (create it from the shape below if missing). For each item write: a checkbox, the one-line content, and its **proposed destination file**. Group by destination. This is a proposal for Jeremiah to approve, not a commit. **Do not write to `memory/`, `context/`, `tasks/`, or `decisions/` in this mode.**

4. **After drafting a session, append its id to the ledger** `review/.swept-sessions.txt` (one id per line) so it is never re-swept.

5. Keep it terse. If nothing in a session is worth keeping, still ledger it (so it is not re-scanned) and note nothing for it.

**`review/sweep-<date>.md` shape:**

```
# Sweep drafts — <date>

_Auto-distilled overnight. Review, then run `/sweep apply` (or say "apply today's sweep") to file the checked items. Uncheck anything you don't want._

## → memory/  (how Pono should work)
- [ ] <fact> — proposed: `memory/<slug>.md` (type: feedback) — from session <short-id>

## → context/properties.md
- [ ] <fact> — proposed: row `123 Example St` — from session <short-id>

## → daily/<date>.md
- [ ] <event> — proposed: My notes — from session <short-id>

## → tasks/tasks.md
- [ ] <todo> — proposed: 📥 Inbox — from session <short-id>

## → decisions/log.md
- [ ] <decision + why> — from session <short-id>

## ⚠️ Needs Jeremiah (ambiguous — not routed)
- [ ] <item> — why it's unclear
```

## Mode: apply (file approved drafts)

Trigger: `/sweep apply`, "apply today's sweep", "file the sweep drafts". Takes the **checked** items out of a `review/sweep-<date>.md` (default: today's; else the most recent) and writes them to their real homes.

1. Read the review file. Take only items whose checkbox is `[x]`. Ignore `[ ]` (Jeremiah declined) and anything under **⚠️ Needs Jeremiah** unless he resolved it inline.
2. For each checked item, write it to the proposed home following that home's exact format (same rules as interactive Step 5 — memory frontmatter + `MEMORY.md` pointer, decisions format, task lanes, in-place `context/` edits). Re-check it isn't already there before writing.
3. Mark each filed item `[x] ✅ filed` in the review file so a re-run is idempotent.
4. Report what was filed and where. The Stop hook commits and pushes.

## Guardrails

- **Preview is mandatory when run interactively.** Never write to `decisions/log.md`, `tasks/tasks.md`, or `context/` files without showing the preview first. Memory files too.
- **Never overwrite the daily log's My notes lane** or delete any file.
- **When an item is ambiguous — unclear if it's durable, or which property/owner it ties to — ask, don't guess.** Hold that one, file the rest.
- **Dates in Pacific** (America/Los_Angeles), per house rule. Convert "today/yesterday" to absolute dates.
- **No em dashes** in anything written. Match the voice in `references/voice.md` for any owner-facing text.
- Keep entries terse. Every home in this brain is a scan-fast artifact, not an essay.