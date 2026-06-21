#!/usr/bin/env python3
"""
Create a QuickBooks Online invoice through Ascend's own Intuit app (the same
OAuth app qb_fetch.py uses). The app holds the `com.intuit.quickbooks.accounting`
scope, which is read AND write — qb_fetch.py is read-only only by choice. This
script is the write side.

WRITE by construction: it POSTs an invoice. It does NOT send/email it — a
QBO invoice created via API is unsent (EmailStatus defaults to NotSet), i.e.
it sits in the books as a draft until you choose to send it. To delete one,
void/delete it in QBO or via the API.

Flow: refresh token -> look up the customer by display name -> resolve a
service Item to hang the lines on -> build the invoice -> preview or POST.

Usage:
  # preview only (no write) — DEFAULT:
  scripts/.venv/bin/python scripts/qb_create_invoice.py --spec scripts/qb_invoice_example.json
  # actually create the draft invoice:
  scripts/.venv/bin/python scripts/qb_create_invoice.py --spec scripts/qb_invoice_example.json --commit

Spec JSON shape:
  {
    "customer": "Example Customer LLC",
    "memo": "123 Example St - tech stack + setup",
    "item_name": "Services",            # optional; service item to book lines under
    "doc_number": "1022",               # optional; auto-assigned (next in sequence) if omitted
    "lines": [ {"desc": "...", "qty": 1, "rate": 349.99}, ... ]
  }

  NOTE: this company has CustomTxnNumbers ON, so QBO will NOT auto-number an
  API-created invoice. The script assigns the next sequential DocNumber unless
  you pin one via "doc_number".
"""
import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SECRET = os.path.join(HERE, "qb_secret.json")
TOKEN = os.path.join(HERE, "qb_token.json")
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
API = "https://quickbooks.api.intuit.com/v3/company"
MINOR = "70"


def refresh():
    cfg = json.load(open(SECRET))
    tok = json.load(open(TOKEN))
    basic = base64.b64encode(f"{cfg['client_id']}:{cfg['client_secret']}".encode()).decode()
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": tok["refresh_token"],
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=body, method="POST",
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        new = json.load(r)
    new["realm_id"] = tok["realm_id"]
    json.dump(new, open(TOKEN, "w"))
    os.chmod(TOKEN, 0o600)
    return new["access_token"], tok["realm_id"]


def query(access, realm, q):
    url = f"{API}/{realm}/query?{urllib.parse.urlencode({'query': q, 'minorversion': MINOR})}"
    req = urllib.request.Request(url, method="GET",
                                 headers={"Authorization": f"Bearer {access}",
                                          "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def find_customer(access, realm, name):
    safe = name.replace("'", "\\'")
    res = query(access, realm, f"select * from Customer where DisplayName = '{safe}'")
    rows = res.get("QueryResponse", {}).get("Customer", [])
    if not rows:
        # fall back to a LIKE search to help diagnose near-misses
        res = query(access, realm, f"select * from Customer where DisplayName LIKE '%{safe}%'")
        rows = res.get("QueryResponse", {}).get("Customer", [])
        if rows:
            names = ", ".join(f"{c['DisplayName']} (id {c['Id']})" for c in rows)
            sys.exit(f"No exact match for '{name}'. Close matches: {names}\n"
                     f"Re-run with --customer set to one of those exact names.")
        sys.exit(f"No customer found matching '{name}'. Create it in QBO first, "
                 f"or run with --create-customer to make it.")
    return rows[0]


def resolve_item(access, realm, preferred):
    res = query(access, realm, "select * from Item where Type = 'Service' maxresults 100")
    items = res.get("QueryResponse", {}).get("Item", [])
    if not items:
        sys.exit("No Service items in this company. Create one in QBO (e.g. 'Services') "
                 "to book invoice lines under.")
    by_name = {i["Name"].lower(): i for i in items}
    order = ([preferred.lower()] if preferred else []) + [
        "services", "tech stack", "tech", "sales", "consulting", "service"]
    for nm in order:
        if nm in by_name:
            return by_name[nm]
    return items[0]  # fallback: first service item


def build_invoice(cust, item, spec):
    lines = []
    total = 0.0
    for ln in spec["lines"]:
        amt = round(ln["qty"] * ln["rate"], 2)
        total += amt
        lines.append({
            "DetailType": "SalesItemLineDetail",
            "Amount": amt,
            "Description": ln["desc"],
            "SalesItemLineDetail": {
                "ItemRef": {"value": item["Id"], "name": item["Name"]},
                "Qty": ln["qty"],
                "UnitPrice": ln["rate"],
            },
        })
    inv = {
        "CustomerRef": {"value": cust["Id"], "name": cust["DisplayName"]},
        "Line": lines,
    }
    if spec.get("memo"):
        inv["CustomerMemo"] = {"value": spec["memo"]}
        inv["PrivateNote"] = spec["memo"]
    return inv, round(total, 2)


def next_doc_number(access, realm):
    """This company has CustomTxnNumbers ON, so the API does NOT auto-assign a
    DocNumber — invoices come out blank unless we set one. Compute the next
    number as (highest existing numeric DocNumber) + 1."""
    res = query(access, realm,
                "select DocNumber from Invoice where DocNumber != '' maxresults 1000")
    rows = res.get("QueryResponse", {}).get("Invoice", [])
    nums = [int(r["DocNumber"]) for r in rows
            if str(r.get("DocNumber", "")).strip().isdigit()]
    return str((max(nums) + 1) if nums else 1001)


def post_invoice(access, realm, payload):
    url = f"{API}/{realm}/invoice?{urllib.parse.urlencode({'minorversion': MINOR})}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Authorization": f"Bearer {access}",
                                          "Accept": "application/json",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True, help="Path to invoice spec JSON")
    ap.add_argument("--customer", help="Override customer display name from spec")
    ap.add_argument("--commit", action="store_true",
                    help="Actually POST the invoice. Without this, preview only.")
    args = ap.parse_args()

    spec = json.load(open(args.spec))
    cust_name = args.customer or spec["customer"]

    access, realm = refresh()
    cust = find_customer(access, realm, cust_name)
    item = resolve_item(access, realm, spec.get("item_name"))
    payload, total = build_invoice(cust, item, spec)
    doc_no = str(spec["doc_number"]) if spec.get("doc_number") else next_doc_number(access, realm)
    payload["DocNumber"] = doc_no

    print(f"Customer : {cust['DisplayName']} (id {cust['Id']})")
    print(f"DocNumber: {doc_no}{'  (from spec)' if spec.get('doc_number') else '  (auto: next in sequence)'}")
    print(f"Item ref : {item['Name']} (id {item['Id']})")
    print(f"Lines    : {len(payload['Line'])}")
    for ln in payload["Line"]:
        d = ln["SalesItemLineDetail"]
        print(f"  - {ln['Description'][:52]:52} {d['Qty']} x {d['UnitPrice']:>8.2f} = {ln['Amount']:>9.2f}")
    print(f"TOTAL    : {total:.2f}")

    if not args.commit:
        print("\n[DRY RUN] Nothing written. Re-run with --commit to create the draft invoice.")
        return

    res = post_invoice(access, realm, payload)
    inv = res["Invoice"]
    print(f"\nCREATED invoice #{inv.get('DocNumber','?')} (id {inv['Id']}) "
          f"total {inv['TotalAmt']:.2f} — UNSENT (draft).")
    print(f"Open: https://qbo.intuit.com/app/invoice?txnId={inv['Id']}")


if __name__ == "__main__":
    main()
