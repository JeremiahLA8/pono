#!/usr/bin/env python3
"""
ingest.py — make the property brain live.

Reads the fresh Hostaway pulls and distills a small, privacy-safe "live context"
snapshot per property, written to data/activity/<property-id>.json. build_state.py
merges these onto each property so the board/state show current reality with no
manual upkeep.

Source of truth stays data/properties.yaml (hand-edited). This only writes the
SEPARATE data/activity/ layer — it never touches properties.yaml.

Privacy: only guest FIRST name, dates, status, channel, and message unread flags
are kept. Never cc, email, phone, address, or message bodies.

Inputs (read-only Hostaway dumps, produced by hostaway_fetch.py; gitignored):
    scripts/hostaway_reservations.json   ({"reservations": [...]})
    scripts/hostaway_messages.json       ([conversation, ...])

Run:  python3 scripts/ingest.py        (after fetching; see refresh_live.sh)

Stdlib + PyYAML.
"""

import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROPS = ROOT / "data" / "properties.yaml"
RES = ROOT / "scripts" / "hostaway_reservations.json"
MSG = ROOT / "scripts" / "hostaway_messages.json"
ACTIVITY = ROOT / "data" / "activity"
PACIFIC = timezone(timedelta(hours=-7))

# Reservation statuses that don't represent a real upcoming/active stay.
DEAD_STATUS = {"cancelled", "declined", "expired", "inquiry",
               "inquiryPreapproved", "inquiryDenied", "inquiryTimedout", "pending"}


def norm(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())


def load_maps():
    data = yaml.safe_load(PROPS.read_text(encoding="utf-8"))
    props = data.get("properties", [])
    listing_to_prop = {}
    alias_index = {}
    for p in props:
        lid = p.get("hostaway_listing_id")
        if lid is not None:
            listing_to_prop[int(lid)] = p["id"]
        for k in set(p.get("aliases", [])) | {p["name"]}:
            alias_index[norm(k)] = p["id"]
    return props, listing_to_prop, alias_index


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return default


def ingest_reservations(listing_to_prop, today):
    """property_id -> {current, next, upcoming_checkout} (minimal, safe fields)."""
    raw = load_json(RES, {})
    rows = raw.get("reservations", raw if isinstance(raw, list) else [])
    by_prop = {}
    for r in rows:
        lid = r.get("listingMapId")
        pid = listing_to_prop.get(int(lid)) if lid is not None else None
        if not pid:
            continue
        if (r.get("status") or "").strip() in DEAD_STATUS:
            continue
        arr, dep = r.get("arrivalDate"), r.get("departureDate")
        if not arr or not dep:
            continue
        slim = {
            "guest": r.get("guestFirstName") or (r.get("guestName") or "").split(" ")[0],
            "arrival": arr,
            "departure": dep,
            "nights": r.get("nights"),
            "guests": r.get("numberOfGuests"),
            "channel": r.get("channelName") or r.get("source"),
            "status": r.get("status"),
        }
        by_prop.setdefault(pid, []).append(slim)

    out = {}
    for pid, stays in by_prop.items():
        stays.sort(key=lambda s: s["arrival"])
        current = next((s for s in stays if s["arrival"] <= today <= s["departure"]), None)
        upcoming = [s for s in stays if s["arrival"] > today]
        nxt = upcoming[0] if upcoming else None
        out[pid] = {
            "current": current,
            "next": nxt,
            # next checkout to plan a turnover around
            "upcoming_checkout": (current or nxt or {}).get("departure"),
            "upcoming_count": len(upcoming),
        }
    return out


def ingest_messages(listing_to_prop, alias_index):
    """property_id -> {unread, open_threads, last_activity}."""
    convos = load_json(MSG, [])
    if not isinstance(convos, list):
        convos = []
    # Map a conversation's listingName -> property via alias substring match.
    by_prop = {}
    for c in convos:
        pid = None
        # Primary: join on listingMapId (reliable). Fallback: listingName alias match.
        lid = c.get("listingMapId")
        if lid is not None:
            pid = listing_to_prop.get(int(lid))
        if not pid:
            lname = norm(c.get("listingName", ""))
            best = ""  # longest alias that is a substring wins (avoids 'Baker' false hits)
            for alias, apid in alias_index.items():
                if alias and alias in lname and len(alias) > len(best):
                    best, pid = alias, apid
        if not pid:
            continue
        d = by_prop.setdefault(pid, {"unread": 0, "open_threads": 0, "last_activity": None})
        d["open_threads"] += 1
        if c.get("hasUnread"):
            d["unread"] += 1
        la = c.get("lastActivity")
        if la and (d["last_activity"] is None or str(la) > str(d["last_activity"])):
            d["last_activity"] = la
    return by_prop


def main():
    now = datetime.now(PACIFIC)
    today = now.strftime("%Y-%m-%d")
    props, listing_to_prop, alias_index = load_maps()
    res = ingest_reservations(listing_to_prop, today)
    msg = ingest_messages(listing_to_prop, alias_index)

    ACTIVITY.mkdir(parents=True, exist_ok=True)
    written = 0
    for p in props:
        pid = p["id"]
        if pid not in res and pid not in msg:
            continue  # nothing live for this property (e.g. onboarding, no Hostaway)
        snap = {
            "property_id": pid,
            "generated_at": now.isoformat(),
            "source": "hostaway",
            "reservations": res.get(pid, {}),
            "messages": msg.get(pid, {}),
        }
        (ACTIVITY / f"{pid}.json").write_text(
            json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
        written += 1
    print(f"ingest: wrote {written} live snapshots to {ACTIVITY.relative_to(ROOT)} "
          f"({len(res)} with reservations, {len(msg)} with messages)")


if __name__ == "__main__":
    main()
