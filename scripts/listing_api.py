#!/usr/bin/env python3
"""
listing_api.py — pull a subject listing's data + PHOTOS + remarks from an MLS RESO Web API feed.

This is the real fix for the "listing sites 403 my photo fetch" problem. An MLS RESO Web API
feed (Bridge Interactive / Trestle / MLS Grid / Spark — all RESO-compliant) exposes:
  - the `Property` resource: price, beds/baths, sqft, year, HOA, tax, PublicRemarks (condition!)
  - the `Media` resource: direct, tokenized photo URLs that DON'T get blocked

So this script: finds the listing by address (or MLS#), returns the deal-spec fields + the
agent remarks, and downloads the photos to a folder so the renovation tier can be scored
against condition-rubric.md (read the images, apply the rubric). Remarks give a text condition
signal to cross-check the visual call.

RESO is standardized, so one OData query layer works across vendors; only the base URL + auth
differ. Set those in scripts/listing_api_secret.json (gitignored by the scripts/*.json rule):

    {
      "base_url": "https://api.bridgedataoutput.com/api/v2/OData/<dataset>",   # or Trestle/MLSGrid/Spark
      "token":    "YOUR_OAUTH2_ACCESS_TOKEN",
      "vendor":   "bridge"   # bridge | trestle | mlsgrid | spark  (affects only the media User-Agent rule)
    }

Auth notes by vendor:
  - bridge:  Bearer token (or ?access_token= server token). Single call returns all fields.
  - trestle: OAuth2 client-credentials -> short-lived Bearer token (refresh per vendor docs).
  - mlsgrid: static Bearer token; as of 2026-06-01 the MEDIA URL download MUST send the token
             as the User-Agent header too (handled below when vendor == "mlsgrid").
  - spark:   Bearer token.

Usage:
    python3 listing_api.py --address "4008 Tacoma St, Irving, TX 75062" --photos-out /tmp/4008
    python3 listing_api.py --mls 20123456 --photos-out /tmp/subj --json
    python3 listing_api.py --address "<addr>" --raw         # dump the matched Property record
"""
import argparse, json, os, re, sys, urllib.request, urllib.parse, urllib.error

SECRET = os.path.join(os.path.dirname(__file__), "listing_api_secret.json")


def load_config():
    cfg = {}
    if os.path.exists(SECRET):
        cfg = json.load(open(SECRET))
    cfg["base_url"] = os.environ.get("LISTING_API_BASE", cfg.get("base_url"))
    cfg["token"] = os.environ.get("LISTING_API_TOKEN", cfg.get("token"))
    cfg["vendor"] = (os.environ.get("LISTING_API_VENDOR", cfg.get("vendor", "bridge")) or "bridge").lower()
    if not cfg.get("base_url") or not cfg.get("token"):
        sys.exit("No MLS feed configured. Set base_url + token in scripts/listing_api_secret.json "
                 "(or LISTING_API_BASE / LISTING_API_TOKEN env vars). See the header of this file.")
    return cfg


def odata(cfg, resource, params):
    url = cfg["base_url"].rstrip("/") + "/" + resource + "?" + urllib.parse.urlencode(params, safe="$ '()=,")
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + cfg["token"],
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"RESO {resource} -> HTTP {e.code}: {e.read().decode(errors='replace')[:400]}")


def parse_address(addr):
    """'4008 Tacoma St, Irving, TX 75062' -> {num, street, city, zip} for a precise $filter."""
    out = {}
    m = re.match(r"\s*(\d+)\s+(.+)", addr)
    if m:
        out["num"] = m.group(1)
        rest = m.group(2)
    else:
        rest = addr
    parts = [p.strip() for p in rest.split(",")]
    if parts:
        # strip a trailing street-suffix token off the street name for looser matching
        out["street"] = parts[0]
    if len(parts) >= 2:
        out["city"] = parts[1]
    z = re.search(r"(\d{5})(?:-\d{4})?\s*$", addr)
    if z:
        out["zip"] = z.group(1)
    return out


def find_listing(cfg, address=None, mls=None):
    """Return the best-matching Property record (with Media expanded if the feed allows)."""
    if mls:
        flt = f"ListingId eq '{mls}'"
    else:
        a = parse_address(address)
        clauses = []
        if a.get("num"):
            clauses.append(f"StreetNumber eq '{a['num']}'")
        if a.get("zip"):
            clauses.append(f"PostalCode eq '{a['zip']}'")
        # street name: match the leading word(s) before the suffix, case-insensitively
        if a.get("street"):
            sname = a["street"].split()[0]
            clauses.append(f"contains(tolower(StreetName),'{sname.lower()}')")
        if not clauses:
            sys.exit("Could not parse the address into a filter. Try --mls <ListingId>.")
        flt = " and ".join(clauses)
    params = {"$filter": flt, "$top": "5", "$expand": "Media"}
    data = odata(cfg, "Property", params)
    recs = data.get("value", data if isinstance(data, list) else [])
    if not recs:
        # some feeds reject $expand=Media; retry without it
        params.pop("$expand", None)
        data = odata(cfg, "Property", params)
        recs = data.get("value", [])
    if not recs:
        return None
    # prefer an active listing if multiple
    recs.sort(key=lambda r: 0 if str(r.get("StandardStatus", "")).lower() == "active" else 1)
    return recs[0]


def media_urls(cfg, rec):
    """Photo URLs for a Property record — from the expanded Media, or a follow-up Media query."""
    med = rec.get("Media") or []
    if not med:
        key = rec.get("ListingKey") or rec.get("ListingId")
        if key:
            data = odata(cfg, "Media", {"$filter": f"ResourceRecordKey eq '{key}'",
                                        "$orderby": "Order", "$top": "50"})
            med = data.get("value", [])
    photos = [m for m in med if str(m.get("MediaCategory", "Photo")).lower() in ("photo", "")]
    photos.sort(key=lambda m: m.get("Order", 0))
    return [m.get("MediaURL") for m in photos if m.get("MediaURL")]


def download(cfg, urls, out, cap=12):
    os.makedirs(out, exist_ok=True)
    # MLS Grid (2026-06-01): media URL requests MUST carry the OAuth token as the User-Agent.
    ua = cfg["token"] if cfg["vendor"] == "mlsgrid" else \
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) str-deal-analyzer"
    saved = []
    for i, u in enumerate(urls[:cap], 1):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=30) as r:
                ctype = r.headers.get("Content-Type", "").split(";")[0].lower()
                ext = {"image/png": ".png", "image/webp": ".webp"}.get(ctype, ".jpg")
                data = r.read()
            path = os.path.join(out, f"{i:02d}{ext}")
            open(path, "wb").write(data)
            saved.append(path)
            print(f"  [{i:>2}] {os.path.basename(path)}  ({len(data)//1024} KB)")
        except Exception as e:
            print(f"  [{i:>2}] {type(e).__name__} — {str(u)[:70]}")
    return saved


def spec_fragment(rec):
    """Map RESO Property fields to deal-spec keys (the ones fill_deal_analyzer uses)."""
    g = rec.get
    hoa = (g("AssociationFee") or 0)
    frag = {
        "address": g("UnparsedAddress"),
        "beds": g("BedroomsTotal"), "baths": g("BathroomsTotalInteger"),
        "sqft": g("LivingArea"), "year_built": g("YearBuilt"),
        "purchase_price": g("ListPrice"),
        "property_tax": g("TaxAnnualAmount"),
        "hoa_annual": round(hoa * 12) if hoa else 0,
    }
    return {k: v for k, v in frag.items() if v not in (None, "")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--address")
    ap.add_argument("--mls", help="ListingId / MLS number")
    ap.add_argument("--photos-out", default=None, help="download photos to this folder")
    ap.add_argument("--max", type=int, default=12)
    ap.add_argument("--json", action="store_true", help="print a deal-spec fragment + remarks")
    ap.add_argument("--raw", action="store_true", help="dump the matched Property record")
    args = ap.parse_args()
    if not args.address and not args.mls:
        sys.exit("Pass --address or --mls.")
    cfg = load_config()

    rec = find_listing(cfg, args.address, args.mls)
    if not rec:
        print("No matching listing found. Try --mls <ListingId> or check the feed's coverage.")
        return
    if args.raw:
        print(json.dumps(rec, indent=2)[:6000])
        return

    remarks = rec.get("PublicRemarks") or ""
    frag = spec_fragment(rec)
    urls = media_urls(cfg, rec)

    if args.json:
        print(json.dumps({**frag, "mls": rec.get("ListingId"),
                          "status": rec.get("StandardStatus"),
                          "remarks": remarks, "n_photos": len(urls)}, indent=2))
    else:
        print(f"Listing: {rec.get('UnparsedAddress')}  (MLS {rec.get('ListingId')}, "
              f"{rec.get('StandardStatus')})")
        print(f"  {frag.get('beds')}bd/{frag.get('baths')}ba  {frag.get('sqft')} sqft  "
              f"built {frag.get('year_built')}  list ${frag.get('purchase_price'):,}" if frag.get('purchase_price') else "")
        print(f"  photos available: {len(urls)}")
        print(f"\n  REMARKS (condition signal):\n  {remarks[:600]}")

    if args.photos_out and urls:
        print(f"\nDownloading {min(len(urls), args.max)} photos -> {args.photos_out}")
        saved = download(cfg, urls, args.photos_out, args.max)
        print(f"\n{len(saved)} photos saved. Next: Read them, score against "
              f"condition-rubric.md, then renovation_budget.py --sqft {frag.get('sqft','<N>')} --tier <result>.")


if __name__ == "__main__":
    main()
