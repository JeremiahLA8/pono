---
name: daily
description: Create or update today's daily log — a morning brief and an end-of-day close-out. Trigger on "daily log", "what's my day", "morning brief", "close out the day", "/daily", or run by the scheduled cloud agent. Auto-detects brief vs close-out from today's file. One run = today's log moved forward.
---

# /daily — the rolling daily log

Maintains `daily/YYYY-MM-DD.md`. The daily log is the connective tissue of the second brain: it pulls the day's table from the task board and connected systems, gives Jeremiah a notes lane, and at close-out flushes decisions and new tasks back to their home files.

## Modes

The skill runs in one of two modes. **Auto-detect** unless an arg is passed:

- Arg `brief` → morning brief.
- Arg `closeout` → end-of-day close-out.
- **No arg:** if today's file is missing OR the `☀️ Morning brief` lane is still empty → run **brief**. Otherwise → run **closeout**.

**Date — always Pacific, never UTC.** Use the session `currentDate` if present. When running headless (scheduled cloud agent, no `currentDate`), the environment clock is UTC — do NOT use it. Derive today's date by running `TZ='America/Los_Angeles' date +%F` and use that. This matters most for the 6pm close-out: 6pm PT is already the next day in UTC, so a UTC date closes out the wrong (empty) file. Build the path `daily/<date>.md` from the Pacific date.

## Inputs to read every run

- `tasks/tasks.md` — the task board (This Week, Money Watch, Waiting On, Inbox)
- `context/priorities.md` — the 3 quarterly priorities, to tie the day back to them
- Yesterday's `daily/*.md` (most recent prior file) — for carryover items
- When connected & available: Gmail (needs-reply), Google Calendar (today's events), QuickBooks (overdue/large), Hostaway (today's check-ins/outs)

> **Headless note:** when this runs headless (the Mac Mini's launchd jobs, or a cloud agent), the claude.ai MCP connections (Gmail/Calendar/QB/Hostaway) are usually NOT authenticated. The Mini's brief runner (`scripts/pono_run.sh`) works around this by pre-pulling fresh data via direct-API scripts right before this skill runs. So when MCP is unavailable, read these **local dump files** instead (all under `scripts/`, all refreshed at run time):
> - **Gmail / needs-reply** → `scripts/inbox_dump.json` (4 inboxes, last 2 days)
> - **Calendar / today's events** → `scripts/calendar_dump.json` (today + 2 days, primary calendar)
> - **QuickBooks / overdue + balances** → `scripts/qb_snapshot.json`
> - **Hostaway / check-ins + guest messages** → `scripts/hostaway_dump.json` + `scripts/hostaway_messages_digest.md`
>
> Prefer live MCP if it IS available (e.g. on the laptop); fall back to these dumps otherwise. If a dump is missing or stale-dated, skip that section gracefully and note `_(not pulled — connection unavailable)_` rather than failing the run. The task-board-derived sections always work because they're local files.

---

## Mode: brief (morning)

1. If `daily/<date>.md` doesn't exist, create it from `daily/_template.md` (substitute the date and weekday).
2. Fill the **☀️ Morning brief** lane:
   - **Needs reply:** unanswered threads from Gmail that want a response today. If Gmail unavailable, pull from the `📥 Inbox` and `⏳ Waiting On` lanes of the task board instead.
   - **On the calendar:** today's events with times (ET noted for calls). If Calendar unavailable, say so.
   - **Money watch:** any item from the `💰 Money Watch` lane of the task board that's time-sensitive, plus QB overdue if available.
   - **Top 3 today:** pick the 3 highest-leverage open items from `🔥 This Week`, biased toward the quarter's priorities (cut admin 75%, second brain, sign 5 properties). One line each, with `[[links]]` preserved.
3. Carry any **carryover → tomorrow** items from yesterday's log into Top 3 or My notes as appropriate.
4. Leave **My notes** and **End of day** lanes untouched (empty scaffolding).
5. Output a short chat summary: the Top 3 and anything urgent. Match the voice in `references/voice.md` — warm, plain, short. No em dashes.

## Mode: closeout (evening)

1. Read today's `daily/<date>.md` including whatever Jeremiah wrote in **My notes**.
2. Fill the **🌙 End of day** lane:
   - **Done today:** check the task board and My notes for what got finished. Reference `[[links]]`.
   - **Decisions made:** anything in My notes that reads as a decision. For each, **append a properly-formatted entry to `decisions/log.md`** (date, decision, why, alternatives, owner — per that file's format). List them here with a pointer.
   - **New tasks captured:** anything in My notes that's a new to-do. **Add each to the right lane of `tasks/tasks.md`** (Inbox if unsorted, This Week if dated/urgent), tagging `[[property/owner]]`. List them here with a pointer.
   - **Carryover → tomorrow:** open Top-3 items that didn't move. These get pulled into tomorrow's brief.
   - **One-line journal:** a single honest sentence on how the day went.
3. **Always confirm before writing to `decisions/log.md` or `tasks/tasks.md`** when run interactively. When run by the scheduled agent, apply them and report what was filed so Jeremiah can reverse anything in the morning.
4. Output a short chat summary: what moved, what got filed, what's carrying over.

---

## Guardrails

- Never delete a daily file or overwrite the **My notes** lane.
- Keep entries terse. The daily log is a scan-in-10-seconds artifact, not an essay.
- Preserve `[[links]]` so days wire into the graph.
- If both lanes are already filled and the skill is run again, ask whether to re-brief, re-close, or append a mid-day update under My notes.
- Keep `daily/_template.md` and this skill's output format identical — if you change one, change the other.
