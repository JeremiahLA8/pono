# STR Deal Analyzer — Cash-on-Cash underwriting

What the `/analyze-deal` skill drives. Give it a property **address or listing link**;
it researches the property + the STR revenue market, fills the workbook, and reports
the headline returns.

## Files here

- `template.xlsx` — the blank model. 5 tabs, all formulas wired. **Never edit by hand.**
  The skill copies it per property; the helper script writes only the input cells.
- `completed-examples-3880-wyllie-8c.xlsx` — a worked example (Puamana, Princeville).

## The model (5 tabs)

1. **STR Deal Analyzer** — the one sheet with inputs. Everything below is the input map.
2. **Renovation Calculator** — itemized rehab estimate; pushes a total you can feed back
   into `rehab`. Pulls sqft from the Deal Analyzer. Rates live on **Renovation Rates**.
3. **Long-Term Outlook** — 10-yr projection (income/expense growth, appreciation, sale).
4. **Sensitivity Analysis** — CoC grid across ADR (±$75) × occupancy (50–80%).

Only the Deal Analyzer holds inputs. Every other tab recalculates from it.

## Input map (spec key → cell on 'STR Deal Analyzer')

Pass these as a flat JSON spec to `scripts/fill_deal_analyzer.py`. Omit any key to
keep the template default. Percentages are decimals (0.25 = 25%).

| Spec key | Cell | Meaning |
|---|---|---|
| address | C5 | full property address |
| listing_link | C6 | Redfin/Zillow URL |
| source_note | C7 | where revenue numbers came from (AirDNA/AirROI/comps) |
| market | F6 | city / submarket |
| property_type | F7 | Home / Condo / Townhome |
| beds, baths | C8, F8 | |
| sqft | C9 | drives furnishings + reno calc |
| year_built | F9 | |
| lot_size | C10 | |
| amenities | F10 | pool, hot tub, etc. |
| notes | C11 | MLS#, reno status, STR-legality, last sale |
| purchase_price | C14 | |
| arv | F14 | after-repair value (= price if no reno) |
| down_pct | C15 | default 0.25 |
| closing_pct | C16 | default 0.01 |
| agent_comm, transaction_coordinator | C17, F17 | usually 0 (buyer side) |
| rehab | C21 | 0 if move-in; else from `renovation_budget.py` scope tier ($25/$50/$75/$100/sqft) or the Renovation Calculator |
| setup_expenses | F21 | default 3000 |
| furn_per_sqft | C22 | default 20 ($/sqft furnishing) |
| furn_override | C23 | flat furnishing $; overrides $/sqft if > 0 |
| legal | C24 | default 1000 |
| permits | F24 | STR permit/license, default 700 |
| photos | C25 | default 700 |
| interest_rate | F29 | default 0.07 |
| term_years | C30 | default 30 |
| interest_only | F30 | "Yes"/"No" |
| pmi_pct | F31 | usually 0 at 25% down |
| **adr** | C36 | **average daily rate — from AirDNA/AirROI** |
| **occupancy** | F36 | **decimal — from AirDNA/AirROI** |
| active_days | C37 | default 365 |
| gross_override | F37 | flat annual gross; overrides ADR×days×occ if > 0 |
| airbnb_pct/vrbo_pct/booking_pct/direct_pct | C41–C44 | channel mix, sums to 1.0 |
| airbnb_fee/vrbo_fee/booking_fee/processing_fee | F41–F44 | host fees (0.15/0.07/0.15/0.029) |
| turnovers_mo | C48 | cleanings/month |
| cost_per_turnover | F48 | |
| mgmt_fee_pct | C56 | StayAscend fee, default 0.15 |
| property_tax | C60 | annual |
| insurance | F60 | annual (see condo rule below) |
| hoa_annual | C61 | annual (HOA monthly × 12) |
| repairs_mo | C65 | reserves/month, default 200 |
| supplies_per_turn | C66 | default 25 |
| refunds_mo | C67 | default 50 |
| utilities_mo | C68 | see condo rule below |
| internet_mo | C69 | see condo rule below |
| landscaping_mo | C70 | see condo rule below |
| spa_mo | C71 | hot tub/pool service; 0 if HOA covers |
| tax_bracket | C85 | default 0.35 |
| land_pct | F85 | land % of value for depreciation, default 0.20 |

**Non-cell key — `reasoning`:** an optional list capturing the analyst's thought process; it
drives the **"Pono Notes"** sheet appended at the end of the workbook (not an input cell). Each
entry is `{"topic": "...", "detail": "..."}` (or a `[topic, detail]` pair, or a plain string).
Fill it as you underwrite — one entry per non-obvious input (why this revenue base, why this
rehab tier, what's sourced vs. assumed, the gates/caveats) — so anyone opening the file can see
*why* a value was entered. If omitted, the sheet falls back to `source_note` + `notes`.

## Research checklist — what to gather before filling

**From the listing (Redfin / Zillow / Trulia / Xome / Hawaii Life / RE/MAX):**
price, beds, baths, sqft, year built, lot, property type, MLS#, last sale,
**HOA/maintenance fee + what it includes**, annual property tax, amenities.

**STR-legality:** confirm the property is in a zone where short-term rental is legal
(in Hawaii: a Visitor Destination Area / VDA, or a permitted/grandfathered unit). If it
is NOT legal STR, say so loudly — the whole model is moot. Note it in `notes`.

**Revenue (the input that decides the deal):**
- **Primary: AirROI API** via `scripts/airroi_lookup.py` (see below). Address-level ADR /
  occupancy / annual revenue + real comps. This is the default source now.
- Public fallback (no key): AirROI / AirDNA market pages for the submarket — get the
  **all-property average** ADR/occupancy AND the **top-quartile** numbers, then place the
  subject between them by bedroom count, condition, and location. Note it in `source_note`.
- Cross-check with **actual comp listings** (VRBO/Airbnb) of the same bed count nearby.

### AirROI API (revenue feed)

Setup once: sign up at https://www.airroi.com/api/getting-started, deposit $10 (pay-as-you-go,
~$0.01-$1.00/call, credits never expire), then save the key:

```
scripts/airroi_secret.json   ->   {"api_key": "YOUR_KEY"}
```

That path is gitignored by the `scripts/*.json` rule — never commit it. The script also
reads `AIRROI_API_KEY` from the env as a fallback.

Run:
```
python3 scripts/airroi_lookup.py --address "<addr>" --beds 3 --baths 2 --guests 8
python3 scripts/airroi_lookup.py --address "<addr>" --beds 3 --baths 2 --json   # spec fragment
python3 scripts/airroi_lookup.py --address "<addr>" --beds 3 --baths 2 --raw    # full API dump
```

Endpoint used: **`GET /listings/comparables`** (address + bedrooms + baths + guests → up to
25 nearby listings with trailing-12-month performance). There is **no** revenue-calculator
endpoint on this plan (`POST /calculator` 404s), and comps are better anyway: real listings
you can name in a pitch, and `ttm_adjusted_occupancy` strips blocked-but-unbooked days.

How the script derives a base: it filters to the **active cohort** (matching bed count,
entire-home, **baths within `--bath-tol` (default 1)**, >= 20 reviews, adjusted occupancy
>= 45%, timeshares excluded), **trims distance + revenue outliers** (with a floor so a small
cohort is never gutted), then **similarity-weights** the survivors. It geocodes the subject
(US Census → Nominatim) and weights each comp by **distance × bath-proximity × tenure**
(reviews), and **hedonically adjusts** each comp's revenue to the subject's amenity tier — a
pool/hot-tub comp is discounted when the subject lacks them.

The amenity premium is no longer a fixed guess: it's **measured from the comps returned**
(median revenue with-amenity vs without), **shrunk toward a prior** by sample size, and only
used when each group has >= 2 comps — otherwise it falls back to the prior (`PRIOR_PREMIUM`)
and says so in the output. The script also reports a **revenue range**: a weighted
**P25 / median / P75 / P80** band of amenity-adjusted revenue.

**StayAscend's house base is the top-quintile (P80) — the "top fifth of all comps."** They
underwrite assuming a top-20% operation (their management premium over median Airbnb hosts),
not the median. So lead with **P80** (and the weighted figure) as the base, NOT a hand-haircut
below the tool's output. Median is the "mediocre operator" floor; P80 is the StayAscend case.
Only haircut below the tool's numbers for a *named, specific* reason (condition, small
footprint), never as blanket caution. Note: for a no-amenity subject the weighted P80 is
amenity-adjusted *down* (the top earners are often pool homes), so it can read a bit below the
raw top-fifth of all comps — show both when they diverge.

`--json` emits `gross_override` (the weighted, amenity-adjusted revenue) + `adr` + calendar
`occupancy` + **`rev_p25` / `rev_median` / `rev_p75` / `rev_p80`** (feed these to
`deal_probabilistic.py --low/--mode/--high`; use P80 as the mode for StayAscend's base). Flags: `--has-pool`/`--has-hot-tub` (subject
amenities), `--radius N` (hard mile cap), `--bath-tol N` (bath filter width),
`--selftest <raw.json>` (re-run offline on a cached `--raw` dump — no API call, no geocode).
Still apply a small condition haircut by hand. Gotchas: AirROI 404s on float params (coerced
to ints); `--guests` changes which comps AirROI returns, so set it to the property's true
sleeps; the pull can cross sub-markets (check the localities line); `--selftest` has no
geocode so distance weighting is off (cohort/premiums/range still valid).

### HasData / Zillow (listing photos + data) — DEFAULT

`scripts/listing_hasdata.py` is the default way to pull the SUBJECT listing's data, description,
and photos. HasData scrapes Zillow on our behalf, so it needs **no MLS authorization** (the RESO
route below does) and the photo URLs it returns are zillowstatic CDN links that **don't 403**.
One call gets everything `fill_deal_analyzer` needs plus a text condition signal.

Setup once: sign up at https://hasdata.com, save the key (gitignored by `scripts/*.json`):

```
scripts/hasdata_secret.json   ->   {"api_key": "YOUR_KEY"}
```

Also reads `HASDATA_API_KEY` from the env as a fallback.

```
python3 scripts/listing_hasdata.py --address "<addr>" --json              # spec fragment + description
python3 scripts/listing_hasdata.py --address "<addr>" --photos-out /tmp/x # + download photos
python3 scripts/listing_hasdata.py --url "<zillow link>" --raw            # dump the raw property record
```

Flow: `--address` hits the Zillow **search** endpoint. A full street address makes Zillow
redirect to the detail page, so HasData returns one full-fidelity `property` and the script
reuses it (one billed call). A looser keyword returns a list; the script scores it on street
number + zip + token overlap and takes the best, then fetches that property. Pass `--url` to
skip the search entirely.

Field mapping handles Zillow's inconsistent nesting: beds/baths/sqft/year/tax/HOA are read from
`resoData`, `area`, `atAGlanceFacts`, or (for duplexes that only state beds in prose) the
`description`. `--json` emits the deal-spec keys (`address`, `property_type`, `beds`, `baths`,
`sqft`, `year_built`, `lot_size`, `purchase_price`, `property_tax`, `hoa_annual`, `listing_link`)
plus `mls`, `status`, `remarks` (the description), and `n_photos`. Gotchas: HOA/tax can be blank
on new-construction or thin listings (confirm by hand); HasData bills per call (cache a `--raw`
dump while iterating); the search match is heuristic, so eyeball the matched URL it prints.

### MLS RESO Web API (listing photos + data) — alternative

`scripts/listing_api.py` pulls the SUBJECT listing's photos, agent remarks, and property data
from an MLS RESO Web API feed. It's the gold standard for data quality but requires **MLS
authorization** (a participant/subscriber relationship + signed data license + OAuth2 creds),
which StayAscend doesn't have — so HasData above is the default. Feed vendors (all
RESO-compliant): **Bridge Interactive**
(free for approved devs), **Trestle** (CoreLogic), **MLS Grid**, **Spark/FBS**. Requires MLS
authorization (a participant/subscriber relationship + signed data license + OAuth2 creds).

Config (gitignored by `scripts/*.json`): `scripts/listing_api_secret.json` =
`{"base_url": "...", "token": "...", "vendor": "bridge|trestle|mlsgrid|spark"}`.

```
python3 scripts/listing_api.py --address "<addr>" --photos-out /tmp/<addr>   # data + remarks + download photos
python3 scripts/listing_api.py --mls <ListingId> --json                      # spec fragment + remarks
```

It queries the `Property` resource (price, beds/baths, sqft, year, HOA, tax, `PublicRemarks`)
and the `Media` resource (photo URLs), maps fields to deal-spec keys, and downloads photos so
the renovation tier can be scored against `condition-rubric.md`. `PublicRemarks` is a text
condition signal — cross-check it against the visual call. Vendor auth differs only slightly
(Bridge/MLS Grid/Spark = static Bearer token; Trestle = OAuth2 client-credentials; MLS Grid
also requires the token as the media-download `User-Agent` as of 2026-06-01 — handled in the
script). Once configured, this also auto-fills beds/baths/sqft/tax so you stop pasting them.

## Expense rules that matter (don't double-count)

- **Condo / HOA:** read what the HOA fee covers. If it includes water/sewer/trash/cable/
  internet/pool, then set `internet_mo`, `landscaping_mo`, `spa_mo` to 0 and `utilities_mo`
  to electric-only (~$150). Otherwise you double-count against the HOA line.
- **Condo insurance:** the HOA master policy covers the structure, so the owner only needs an
  HO-6 + STR liability rider (~$1,500–2,500/yr), not a full SFR policy (~$4,000+).
- **Property tax:** STR/non-owner-occupied tiers are higher than owner-occupied. Use the
  investor/vacation-rental rate, not the homeowner rate.
- **Pool + landscaping service:** don't default `spa_mo` / `landscaping_mo` — `WebSearch` the
  market's **weekly** rates (StayAscend runs weekly service on both for guest-readiness) and
  size to the lot/pool. Record the figure + source in the `reasoning` log; if search is down,
  use a labeled metro estimate and flag it pending a live quote.

## Renovation budget (scope tiers)

`scripts/renovation_budget.py` sets the `rehab` input from a SCOPE TIER keyed off square
footage — the **$25 / $50 / $75 / $100 per-sqft model** (StayAscend standard):

| Tier | $/sqft | Scope |
|---|---|---|
| light | $25 | cosmetic refresh — paint, LVP in main areas, fixtures |
| moderate | $50 | standard STR conversion — flooring + paint, kitchen + bath updates, some mechanical |
| heavy | $75 | extensive remodel — kitchen + baths, flooring, HVAC, electrical, windows/doors |
| full | $100 | full gut / high-end — to the studs, premium finishes |

`rehab = sqft × tier rate`. All-in **construction** cost — NOT furnishing (`furn_per_sqft`
is the separate ~$18-30/sqft furniture line; don't double-count). Override with `--rate N`
for a contractor takeoff; use the workbook's Renovation Calculator tab for a line-item estimate.

```
python3 scripts/renovation_budget.py --spec deal.json --all          # budget at every tier
python3 scripts/renovation_budget.py --sqft 1727 --tier moderate --json   # -> {"rehab": 86350}
```

**Two caveats the model can't see:** (1) rehab is **pure cost** — it grows cash invested (the
CoC denominator) but adds NO revenue and doesn't touch debt, so it only lowers CoC. Match the
revenue tier to the *post-reno* condition: don't stack top-quintile revenue on a property that
needs a gut. (2) The model assumes rehab is **paid in cash**; financing it (rehab loan, or
cash-out refi on forced ARV) changes the cash-in and debt and isn't modeled yet.

## Amenity build-out scenarios

`scripts/deal_scenarios.py` runs a deal across hot-tub / pool build-outs. For each
combination it folds the **build cost** (from the Renovation Rates: hot tub $7-22k,
plunge $25-50k, fiberglass pool $45-85k, gunite $60-110k, + 12% contingency + permit)
into the cash invested, applies a revenue lift, adds the upkeep, and prints CoC / cash
flow / DSCR. The `condo_ok` flag warns when an amenity isn't feasible on a condo (private
pools need private land; hot tubs need HOA approval).

```
python3 scripts/deal_scenarios.py                 # 3880 Wyllie #8C base
python3 scripts/deal_scenarios.py --spec s.json   # any base spec
python3 scripts/deal_scenarios.py --scope low     # low/mid/high build cost + lift
```

Key lesson it surfaces: a build-out adds to the **denominator** (cash invested) at the same
time it lifts revenue, so amenities rarely rescue a deal on their own — they pair with a
price cut.

**Revenue lift = ONE premium per amenity (`rev_lift`), not ADR × occupancy.** A comp-measured
premium already blends both, so compounding separate ADR and occupancy lifts double-counts (the
bug that once turned a ~13% pool+hot-tub lift into +44%). The `AMENITIES` defaults are
**conservative and market-agnostic — a fallback only**. Pool value is highly market-dependent
(big in inland/desert summers, soft in beach/community-pool markets), so:
- **Prefer deriving the with-amenity revenue straight from amenity-matched comps** (most comps in
  a pool-heavy submarket already have one — normalize those to the subject and read the band).
- When you have a comp-measured premium, **override per-deal** via the spec's
  `amenity_lifts` = `{ "hot_tub": 0.04, "pool_fiber": 0.09, ... }`. The footer reports which
  source was used. Keep the strip premium (no-pool base) and the add premium (build-out)
  **consistent** — if pools strip at ~9%, they add back at ~9%, not +44%.

## Permit costs (per market)

`scripts/permit_costs.py` holds researched, source-cited permit-fee data per market and
computes the **building permit fee** from a construction valuation. `deal_scenarios.py`
uses it so amenity permits are real numbers (a Kauai hot-tub permit is ~$188, not the
flat $700 the template assumed). Human-readable cache per market:
`references/str-deal-analyzer/permit-costs/<market>.md`.

```
python3 scripts/permit_costs.py --market kauai-hi --info            # STR rules + tax + examples
python3 scripts/permit_costs.py --market kauai-hi --valuation 22000 # one build's permit
```

Two permit types it tracks:
- **STR operating permit** — the right to operate (VDA/NCU status, registration, renewal).
  Confirm STR-legality first; it's the go/no-go gate, not just a cost.
- **Building permit** — for reno/amenity builds; scales with construction value.

### Researching a NEW market (when a deal is outside Kauai)

1. Find the **county** the property is in.
2. Web-research, in order: (a) STR/vacation-rental legality + registration/renewal fee,
   (b) the county **building permit fee schedule** by construction valuation + plan-review %,
   (c) any STR-specific lodging taxes (usually guest pass-through). County `.gov` fee
   appendices are the source of truth; they're often PDFs — fetch and parse them.
3. Add a `MARKETS["<market>"]` entry to `permit_costs.py` (brackets + surcharges + STR notes)
   and write `permit-costs/<market>.md` with sources and a "needs a phone call" list.
4. Until a market is added, `deal_scenarios.py` falls back to a flat $700 permit and labels it.

Honest limits: exact STR registration fees and 2026 figures sometimes sit behind a
"call the department" wall. Capture what's published, compute what's formula-based
(building permits), and flag the rest rather than inventing a number.

## Property-tax tier, lodging tax & checks

`scripts/permit_costs.py` also computes the **vacation-rental property-tax tier** (an STR is
taxed ~4.4x the owner-occupied rate on Kauai): `--assessed <value>`. Set the spec's
`property_tax` from the vacation-rental class and `permit_market` to the market key;
`fill_deal_analyzer` then prints **manager economics** (StayAscend's fee revenue), a
**lodging-tax** context line (GET/TAT ~18.5%, guest pass-through), and **checks** (condo
warrantability, property-tax-tier validation).

## Probabilistic cash flow

`scripts/deal_probabilistic.py --spec <spec> --low L --mode M --high H` runs a Monte Carlo on
revenue (use the AirROI P25 / median / P75) and reports the **probability of positive cash
flow** + CoC P10/median/P90. Lead with this on marginal deals.

## Reconciliation (Excel == Python)

`compute()` in `fill_deal_analyzer.py` is authoritative for reported numbers; the workbook is
the interactive deliverable. The standalone package's `tests/test_reconcile.py` evaluates the
live Excel formulas (pycel) and asserts they equal `compute()`, so the two can't silently drift.

## How returns read (rules of thumb)

- **Cash-on-cash:** target ≥ 8% to call it a cash-flow deal. Negative = it costs you to hold.
- **DSCR:** < 1.0 means rental income doesn't cover debt; a DSCR lender won't fund it.
- **Cap rate:** the unlevered yield. Low cap + high price = an appreciation/lifestyle play,
  not cash flow.
- **Break-even occupancy** above ~70% in a market that averages 50–60% is a red flag.

## Running it

```
python3 scripts/fill_deal_analyzer.py spec.json --out "/path/Address - STR COC Analysis.xlsx"
```

Writes the input cells into a copy of the template and prints the computed headline
metrics (the script recomputes the formula chain in Python because there's no headless
Excel recalc available).

**Output the user actually sees:** openpyxl writes the model's formulas but leaves their
cached results empty, so the live tabs read blank in Quick Look (and sometimes Numbers) until
something recalculates. To make the numbers visible everywhere, the script:
- bakes a **"Summary (Pono)" front sheet** of LITERAL computed values (CoC, DSCR, cash needed,
  furnishings, revenue, NOI) — shows in any viewer, including Quick Look preview;
- sets **`fullCalcOnLoad`** so the live tabs recalc the moment Excel/Numbers opens the file;
- runs a **`_verify()`** pass that re-opens the saved file and confirms every input landed and
  the snapshot is populated (prints `VERIFY: ✓` or lists what's missing).

The live tabs remain fully interactive — edit any input and they recalc; the Summary sheet is a
fill-time snapshot, so re-run the script after manual edits to refresh it.
