# Pono — an AI Company Brain

Pono is an AI operating system that runs a live short-term-rental management company. It pulls knowledge out of the tools a business already uses, keeps that knowledge current, and turns it into executable skills an AI agent runs to do real operational work: underwriting acquisitions, drafting invoices, handling guest communication, and keeping a self-updating second brain.

This is the idea Y Combinator described in its Summer 2026 Request for Startups as the "company brain." I had been running one in production for months before that post went up.

---

## About this repo

This is a **public showcase** of Pono. The production system runs on real client data: owner contracts, financials, guest records, and connected APIs (QuickBooks, Hostaway, Gmail, Google Drive). **None of that is in this repo.**

I extracted the *engineering* — the agent skills, the automation scripts, the architecture — and stripped every piece of client and business data so it could be shared openly. So what you see here is the machinery, not the data it runs on. The live system does the real work behind money-safe guardrails.

I built this with no CS degree (pretty much Claude'd it all).

---

## What it does

Pono is not a chatbot over documents. It does the work.

- **Underwrites acquisitions** — a calibrated revenue model that corrects for known biases in market data (ADR inflation on luxury comps), runs scenarios, and fills a cash-on-cash workbook. See [`scripts/deal_scenarios.py`](scripts/deal_scenarios.py) and [`scripts/airroi_lookup.py`](scripts/airroi_lookup.py).
- **Drafts invoices into QuickBooks** — reads the task board, matches owners to QB customers, builds line items with detailed reasons, previews, then writes. Draft-only, never sends.
- **Handles guest communication** — pulls guest messages from the booking channels, drafts replies in the company voice.
- **Keeps a living knowledge base** — a nightly pipeline distills the day's activity into a structured second brain: daily logs, decisions, property files, tasks.

## How it's built

```
  Sources                Ingestion              Brain                 Action
  ---------              ---------              -----                 ------
  Gmail        ─┐                          ┌─ daily logs        ┌─ draft invoices (QBO)
  QuickBooks   ─┤        live API          ├─ decisions log     ├─ draft guest replies
  Hostaway     ─┼──▶  pre-pulls + nightly ─┼─ property files  ──┼─ underwrite deals
  Google Drive ─┤        distillation       ├─ task board        ├─ send reports (PDF)
  Meeting notes─┘                          └─ skills (SOPs)      └─ scheduled reminders
```

- **Executable skills** — operating procedures written as skill files an agent runs directly. Not docs about how the work is done; the thing that does the work. See [`skills/`](skills/).
- **Scheduled, always-on** — runs on a dedicated server with cron jobs for live data refresh, nightly distillation, and reminders.
- **Money-safe guardrails** — it drafts but never sends payments, verifies values before finalizing, signs guest messages as the company not the operator, and holds any row it can't resolve cleanly instead of guessing.

## Stack

- **Python** for the integration and automation layer (QuickBooks, Hostaway, Gmail, Google Drive, pricing APIs)
- **Agent skills** as the operating layer — markdown SOPs with embedded logic the agent executes
- **Shell + cron** for scheduling on an always-on host
- **Markdown second brain** as the knowledge store — version-controlled, human-readable, agent-queryable

## What's in here

| Path | What it shows |
|---|---|
| [`scripts/`](scripts/) | The integration + automation layer — API auth, deal underwriting, invoice drafting, data ingestion |
| [`skills/`](skills/) | Executable agent skills — the operating procedures the AI runs |
| [`references/`](references/) | The operator methodology behind how the system is designed |

---

Built by Jeremiah Lwin. The live system runs StayAscend / Ascend Vacation Rentals.
