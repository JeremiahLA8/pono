#!/usr/bin/env python3
"""
Hostaway API client for Jeremiah's AIOS.

Pulls the real portfolio picture from Hostaway: listings, reservations,
and (optionally) consolidated revenue — the stuff QuickBooks does NOT have.

Setup (one-time):
  1. In Hostaway: Settings -> Hostaway API -> create an API key.
  2. Save the two values to scripts/hostaway_secret.json (gitignored):
       { "account_id": "12345", "api_key": "your-long-api-key" }
  3. Run this script. It exchanges them for an access token (cached to
     scripts/hostaway_token.json) and fetches data.

Usage:
  scripts/.venv/bin/python scripts/hostaway_fetch.py listings
  scripts/.venv/bin/python scripts/hostaway_fetch.py reservations --days 90
  scripts/.venv/bin/python scripts/hostaway_fetch.py messages --days 30
  scripts/.venv/bin/python scripts/hostaway_fetch.py messages --days 30 --digest
  scripts/.venv/bin/python scripts/hostaway_fetch.py all --days 90

Read-only by design — this script only calls GET endpoints. (The API key
itself can write, so keep hostaway_secret.json private — it's gitignored.)
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SECRET = os.path.join(HERE, "hostaway_secret.json")
TOKEN = os.path.join(HERE, "hostaway_token.json")
BASE = "https://api.hostaway.com/v1"


def _post(url, data, headers):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _get(url, headers):
    # READ-ONLY GUARD: this client only ever performs GET data calls.
    # The single POST in this file is the auth token exchange (_post, below),
    # which does not modify Hostaway data. There are intentionally no
    # create/update/delete functions here. Do not add any.
    req = urllib.request.Request(url, headers=headers, method="GET")
    assert req.get_method() == "GET", "Hostaway client is read-only"
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def get_token():
    if os.path.exists(TOKEN):
        return json.load(open(TOKEN))["access_token"]
    if not os.path.exists(SECRET):
        sys.exit(
            f"\nMissing {SECRET}\nCreate it with your Hostaway credentials:\n"
            '  { "account_id": "12345", "api_key": "your-api-key" }\n'
            "Find them in Hostaway: Settings -> Hostaway API.\n"
        )
    cfg = json.load(open(SECRET))
    resp = _post(
        f"{BASE}/accessTokens",
        {
            "grant_type": "client_credentials",
            "client_id": str(cfg["account_id"]),
            "client_secret": cfg["api_key"],
            "scope": "general",
        },
        {"Content-Type": "application/x-www-form-urlencoded", "Cache-control": "no-cache"},
    )
    if "access_token" not in resp:
        sys.exit(f"Auth failed: {json.dumps(resp)[:400]}")
    json.dump(resp, open(TOKEN, "w"))
    os.chmod(TOKEN, 0o600)
    print("Authorized Hostaway; token cached.")
    return resp["access_token"]


def paged(path, token, extra=None, cap=2000):
    """Fetch all pages of a list endpoint."""
    headers = {"Authorization": f"Bearer {token}", "Cache-control": "no-cache"}
    out, offset, limit = [], 0, 100
    while len(out) < cap:
        params = {"limit": limit, "offset": offset}
        if extra:
            params.update(extra)
        data = _get(f"{BASE}/{path}?{urllib.parse.urlencode(params)}", headers)
        batch = data.get("result", []) or []
        out.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return out


def _conv_activity(c):
    """Most recent activity timestamp on a conversation (sent or received)."""
    return max(c.get("messageReceivedOn") or "", c.get("messageSentOn") or "")


def fetch_messages(token, days, max_convos, per_convo, listing=None):
    """Pull guest conversations and their messages (GET-only).

    Returns a list of {conversation metadata + messages[]}, newest activity first.
    By default limited to conversations active within `days` and capped at
    `max_convos`. If `listing` (a listingMapId) is given, pulls ALL-TIME threads
    for that one property instead (no date cutoff, no convo cap).
    """
    from datetime import datetime, timedelta

    headers = {"Authorization": f"Bearer {token}", "Cache-control": "no-cache"}
    convos = paged("conversations", token)
    convos.sort(key=_conv_activity, reverse=True)

    if listing is not None:
        recent = [c for c in convos if c.get("listingMapId") == listing]
    else:
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        recent = [c for c in convos if _conv_activity(c)[:10] >= cutoff][:max_convos]

    out = []
    for c in recent:
        cid = c.get("id")
        msgs = paged(f"conversations/{cid}/messages", token, cap=per_convo)
        msgs.sort(key=lambda m: m.get("date") or "")
        out.append({
            "conversationId": cid,
            "guest": c.get("recipientName"),
            "guestEmail": c.get("guestEmail"),
            "listingMapId": c.get("listingMapId"),
            "listingName": (msgs[-1].get("listingName") if msgs else None),
            "reservationId": c.get("reservationId"),
            "channel": c.get("type"),
            "hasUnread": bool(c.get("hasUnreadMessages")),
            "lastActivity": _conv_activity(c),
            "messages": [
                {
                    "date": m.get("date"),
                    "incoming": bool(m.get("isIncoming")),
                    "body": (m.get("body") or "").strip(),
                }
                for m in msgs[-per_convo:]
            ],
        })
    return out


def render_digest(convos):
    """Readable markdown digest of recent guest messages — unread first."""
    lines = ["# Hostaway — recent guest messages", ""]
    unread = [c for c in convos if c["hasUnread"]]
    lines.append(f"**{len(convos)} active conversations · {len(unread)} with unread**")
    lines.append("")
    for c in sorted(convos, key=lambda x: (not x["hasUnread"], x["lastActivity"]), reverse=False):
        flag = "🔴 UNREAD" if c["hasUnread"] else ""
        who = c["guest"] or "Guest"
        listing = c["listingName"] or "—"
        lines.append(f"## {who} · {listing} {flag}".rstrip())
        lines.append(f"_{c['channel']} · conv {c['conversationId']} · last {c['lastActivity']}_")
        for m in c["messages"][-6:]:
            speaker = "Guest" if m["incoming"] else "Us"
            body = " ".join(m["body"].split())
            if len(body) > 240:
                body = body[:240] + "…"
            lines.append(f"- **{speaker}** ({m['date']}): {body}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["listings", "reservations", "messages", "all"])
    ap.add_argument("--days", type=int, default=90, help="Activity window (reservations: arriving; messages: last activity).")
    ap.add_argument("--max-convos", type=int, default=60, help="Cap on conversations pulled (messages).")
    ap.add_argument("--per-convo", type=int, default=20, help="Messages kept per conversation (messages).")
    ap.add_argument("--listing", type=int, default=None, help="listingMapId — pull ALL-TIME threads for one property (ignores --days/--max-convos).")
    ap.add_argument("--digest", action="store_true", help="Also write a readable markdown digest.")
    ap.add_argument("--out", default=os.path.join(HERE, "hostaway_dump.json"))
    args = ap.parse_args()

    token = get_token()
    result = {}

    if args.what in ("listings", "all"):
        listings = paged("listings", token)
        result["listings"] = listings
        print(f"Listings: {len(listings)}")

    if args.what in ("reservations", "all"):
        res = paged("reservations", token, extra={"sortOrder": "arrivalDate", "limit": 100})
        result["reservations"] = res
        print(f"Reservations: {len(res)}")

    if args.what in ("messages", "all"):
        convos = fetch_messages(token, args.days, args.max_convos, args.per_convo, listing=args.listing)
        result["conversations"] = convos
        nmsg = sum(len(c["messages"]) for c in convos)
        nunread = sum(1 for c in convos if c["hasUnread"])
        print(f"Conversations: {len(convos)} ({nunread} unread) · {nmsg} messages")
        if args.what == "messages":
            suffix = f"_{args.listing}" if args.listing else ""
            mout = os.path.join(HERE, f"hostaway_messages{suffix}.json")
            json.dump(convos, open(mout, "w"), indent=1)
            print(f"Wrote {mout}")
        if args.digest:
            dpath = os.path.join(HERE, "hostaway_messages_digest.md")
            open(dpath, "w").write(render_digest(convos))
            print(f"Wrote {dpath}")

    if args.what != "messages":
        json.dump(result, open(args.out, "w"), indent=1)
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
