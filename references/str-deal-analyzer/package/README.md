# STR Deal Analyzer

A self-contained engine for underwriting short-term-rental acquisitions to **cash-on-cash**.
Feed it a property's facts + a comp-derived revenue figure; it fills a 5-tab Excel model and
reports the returns (CoC, cap rate, DSCR, NOI, break-even, manager economics), plus amenity
build-out scenarios and a revenue Monte Carlo.

This bundle is the compute engine + the live-data pullers + the workbook template. It runs
offline for the math; API keys are needed only for the live comp/listing pulls.

## What's in here

```
analyze.py              one-command pipeline: spec.json -> workbook + full report
fill_deal_analyzer.py   writes the workbook, recalculates it, prints the headline metrics
deal_scenarios.py       amenity build-out grid (hot tub / pool combos)
deal_probabilistic.py   revenue Monte Carlo -> P(cash flow > 0) + CoC band
airroi_lookup.py        pull + calibrate + weight real STR comps (AirROI)
listing_hasdata.py      pull the subject listing's data + photos (HasData/Zillow)
permit_costs.py         per-market building-permit + property-tax-tier layer
renovation_budget.py    scope-tier rehab sizing ($/sqft)
config.py               your API keys + template path (edit this)
assets/                 template.xlsx, condition rubric, example spec, permit data
docs/METHODOLOGY.md     the full method + spec key -> cell map
tests/test_smoke.py     end-to-end sanity check on the example spec
CHANGELOG.md            what changed in this accuracy pass
```

## Setup

```bash
pip install -r requirements.txt          # just openpyxl
# add your keys (optional — only for live pulls):
#   edit config.py, or set AIRROI_API_KEY / HASDATA_API_KEY in the environment
```

## Run it

```bash
# the math (no keys needed) — fill the workbook from a finished spec:
python3 analyze.py assets/example.spec.json

# add the amenity build-out grid and a revenue Monte Carlo:
python3 analyze.py assets/example.spec.json --scenarios --low 79000 --mode 110000 --high 147000

# live data pulls (need keys):
python3 listing_hasdata.py --address "<addr>" --json --photos-out /tmp/x
python3 airroi_lookup.py --address "<addr>" --beds 5 --baths 4 --guests 12
```

The workbook saves to `~/Downloads/<address> - STR COC Analysis.xlsx` by default. Its live tabs
recalculate on open; a **Summary** snapshot and a **Pono Notes** reasoning sheet show values in
any viewer.

## The spec

A flat JSON object — see `assets/example.spec.json` and the key→cell map in
`docs/METHODOLOGY.md`. Two non-cell keys worth knowing:
- `reasoning`: a list of `{"topic","detail"}` entries → renders as the **Pono Notes** sheet.
- `amenity_lifts`: per-amenity revenue premiums (e.g. `{"pool_fiber": 0.09, "hot_tub": 0.04}`)
  → overrides the conservative defaults in the build-out grid with your comp-measured numbers.

## Accuracy notes

See `CHANGELOG.md`. The headline: revenue is the swing input — it's ADR-calibrated, comp-weighted,
normalized to the subject, and based on the **top-quintile (P80)** of comps. Amenity lifts are a
single comp-grounded premium (no ADR×occupancy double-count). The engine prints what it sourced
vs. assumed; confirm the soft inputs (revenue, condition/rehab, taxes, insurance) before acting.
