---
name: analyze-deal
description: Underwrite a short-term-rental acquisition. Give an address or listing link; it researches the property and the STR revenue market, fills the Cash-on-Cash workbook, and reports the returns. Trigger on "/analyze-deal", "run the numbers on", "underwrite", "cash on cash on", "should I buy", or pasting a Redfin/Zillow link.
---

# /analyze-deal — STR cash-on-cash underwriting

Jeremiah gives a property **address or listing link**. You research it end to end,
fill the 5-tab Cash-on-Cash model, and report whether it pencils. Built for the
"sign 5 new properties" priority — this is the go/no-go tool and the owner pitch asset.

Engine + input map + research sources: `references/str-deal-analyzer/README.md`.
Read it before your first run.

## What one run produces

- A filled workbook at `~/Downloads/<address> - STR COC Analysis.xlsx` (all 5 tabs recalc).
- A short verdict: total cash needed, gross revenue, NOI, **cash-on-cash**, cap rate,
  DSCR, break-even occupancy, and your annual mgmt fee — plus a one-line read.

## Steps

1. **Get the input.** An address or a listing URL. If neither is clear, ask for one.

2. **Research the property.** Need: price, beds, baths, sqft, year built, lot, property
   type, MLS#, last sale, **HOA fee + what it covers**, annual property tax, amenities.
   - **Primary: HasData (Zillow).** One call returns the data, the listing description (a
     text condition signal), and photo URLs that don't 403:
     ```
     python3 scripts/listing_hasdata.py --address "<addr>" --json     # spec fragment + description
     python3 scripts/listing_hasdata.py --url "<zillow link>" --json  # skip the address search
     ```
     It auto-fills address/type/beds/baths/sqft/year/lot/price/tax/HOA — stop pasting them.
     See the README's HasData section. (HOA/tax can be blank on new-construction or thin
     listings; confirm those by hand.)
   - **Fallback (no HasData key):** listing sites often 403/429 on direct fetch — search the
     address, read the snippet, and fetch the pages that load (Hawaii Life and MLS
     aggregators usually work).

3. **Confirm STR is legal.** Find the zoning (in Hawaii, a VDA / permitted unit). If
   short-term rental is NOT allowed, stop and say so — the model is meaningless otherwise.

4. **Get the revenue numbers.** This input decides the deal, so source it, don't guess:
   - **Primary: the AirROI API.** Run it with the address + bed/bath/guest count:
     ```
     python3 scripts/airroi_lookup.py --address "<addr>" --beds 3 --baths 2 --guests 8 \
         [--has-pool] [--has-hot-tub] [--radius 2]
     ```
     It geocodes the subject, pulls active entire-home comps (baths within tolerance,
     distance + revenue outliers trimmed), **similarity-weights** them (distance × bath ×
     tenure) and **hedonically adjusts** each comp's revenue to the subject's amenity tier.
     The pool / hot-tub **premium is measured from the comps themselves** (with vs without),
     shrunk toward a prior, and falls back to the prior — and says so — when a group is too
     thin; relay which case applied. Pass `--has-pool`/`--has-hot-tub` to match the subject's
     amenities, and set `--guests` to the property's TRUE sleeps (it changes which comps
     AirROI returns). Add `--json` for a spec fragment (`gross_override`, `adr`, `occupancy`,
     `rev_p25`/`rev_median`/`rev_p75`/`rev_p80`, `source_note`). It reports a **P25 / median /
     P75 / P80 revenue band** — lead the verdict with the band, not just the point, and feed
     P25/P75 to `deal_probabilistic.py --low/--high`. **StayAscend's house base is the
     top-quintile (P80) — "the top fifth of all comps"** (they underwrite a top-20% operation,
     not the median). Use P80 as the base/mode; do NOT hand-haircut below the tool's output
     except for a named, specific reason (condition, small footprint). Always show what the
     deal needs (break-even gross) so the verdict is "can we clear the top-fifth bet," not a
     gut call. Read the comp table: localities (watch for
     sub-market bleed) and reviews (tenure = is the occupancy a real annual rate or a
     new-listing artifact). Cache a `--raw` dump and re-run offline with `--selftest` to
     iterate without repeat paid calls.
   - **Fallback (no key): AirDNA/AirROI market pages** for the submarket. Grab the
     all-property average AND top-quartile ADR/occupancy, then place the subject between
     them by bed count, condition, and location. Cross-check against comp listings.
   - Record the derivation in `source_note`. Always tell Jeremiah revenue is the swing
     input and show the upside (top-quartile / strong-comp) case alongside the base.

5. **Apply the expense rules** from the README so you don't double-count: condo HOA
   inclusions zero out internet/landscaping/spa and shrink utilities; condo insurance is
   HO-6-sized not SFR-sized; use the investor/STR property-tax tier.
   - **Research local service costs — don't default them.** For any property with a yard or a
     pool/hot tub, `WebSearch` the market's **weekly** rates and use them:
     - **Landscaping** (`landscaping_mo`): weekly lawn/landscaping service in the metro,
       sized to the lot. StayAscend runs **weekly** service on STRs (curb appeal = bookings).
     - **Pool + hot tub** (`spa_mo`): weekly pool service + hot tub chemical/service in the
       metro. StayAscend runs **weekly** cleaning on both (guest-ready every turn).
     Search e.g. "weekly pool service cost per month <city> <state>" and "weekly lawn service
     cost per month <city>". Record the figure + source in the `reasoning` log; if search is
     unavailable, use a labeled metro estimate and flag it as pending a live quote.

6. **Default the financing** to 25% down / 7% / 30yr unless Jeremiah set terms. Default
   purchase price to list unless he gave an offer price.

   **Renovation:** don't guess `rehab`. Determine the scope tier **from the listing photos**,
   then size it with `scripts/renovation_budget.py --sqft <N> --tier light|moderate|heavy|full`
   — the **$25 / $50 / $75 / $100 per-sqft model** (`rehab = sqft × tier rate`, all-in
   construction, NOT furnishing). Determine the tier like this:
   - **Preferred: HasData.** `python3 scripts/listing_hasdata.py --address "<addr>"
     --photos-out /tmp/<addr>` (or `--url <link>`) downloads the photos and prints the listing
     description (a text condition signal) — no MLS authorization, no 403s. If you already ran
     it in step 2, just add `--photos-out`. Cross-check the description against the visual call.
   - **Alternative (if an MLS feed is configured):** `python3 scripts/listing_api.py --address
     "<addr>" --photos-out /tmp/<addr>` pulls photos + agent remarks + data from the MLS RESO
     feed. Requires MLS authorization; HasData is the default since that bar isn't met.
   - **Last resort:** collect the listing's photo URLs by hand and download with
     `python3 scripts/listing_photos.py --urls <u1> <u2> ... --out /tmp/<addr>`, or have
     Jeremiah paste the link / photos.
   - **Read the saved images** and score condition against
     `references/str-deal-analyzer/condition-rubric.md` (kitchen + baths + flooring drive it).
   - Report the tier, the rehab $, the **room-by-room evidence**, and a **confidence level**,
     and flag it for confirmation — photos oversell and condition is the swing risk. If photos
     are missing/stale/exterior-only, say LOW confidence and prefer the higher tier.
   Match the revenue tier to the *post-reno* condition (don't stack top-quintile revenue on a
   gut job), and remember rehab is modeled as pure cash cost — it grows the CoC denominator,
   adds no revenue, and isn't financed.

7. **Fill and compute.** Write a flat JSON spec (keys in the README map) and run:
   ```
   python3 scripts/fill_deal_analyzer.py /tmp/spec.json --out "$HOME/Downloads/<FULL address> - STR COC Analysis.xlsx"
   ```
   Use the **full property address** in the filename — street, city, state, ZIP (e.g.
   "3129 New Haven St, Irving, TX 75062 - STR COC Analysis.xlsx"), matching the database
   convention. Simplest: omit `--out` entirely — the script defaults the filename to the spec's
   `address` field, so a full `address` value gives a full-address title automatically.
   **Always include a `reasoning` list** in the spec — one entry (`{"topic","detail"}`) per
   non-obvious input: why this revenue base, why this rehab tier, what's sourced vs. assumed,
   the gates/caveats. It renders as the **"Pono Notes"** sheet at the end of the workbook so
   Jeremiah can see *why* any value was entered without asking. See the README's `reasoning` note.
   The script writes the input cells and prints the headline metrics (it recomputes the
   formula chain in Python because there's no headless Excel recalc on the mini; the saved
   file still recalculates when opened).

7b. **Save it to the Google deal database.** Every workbook also goes to the shared "STR Search"
   Drive database (one subfolder per market). Upload with the venv Python (the default one lacks
   the Google libs), letting the script resolve/create the market folder:
   ```
   scripts/.venv/bin/python scripts/gdrive_upload.py --market "<Market Name>" \
       "$HOME/Downloads/<address> - STR COC Analysis.xlsx"
   ```
   Match `--market` to the existing folder names (e.g. "Irving Texas", "Hawaii", "UofO"); a new
   market is created automatically. Re-running a deal UPDATES the same file (no duplicates). The
   STR Search root is `1FgvmjxzrordrY4lVFGAO32xCvVVr-x8H`. Report the returned Drive link.

8. **Report the verdict.** Lead with cash-on-cash and monthly cash flow. Flag DSCR < 1.0,
   break-even occupancy above market, and whether it's a cash-flow deal or an
   appreciation/lifestyle play. Note every assumption you made vs. sourced.

9. **Optional: amenity build-outs.** If the deal is marginal or Jeremiah asks "what if we
   add a hot tub / pool", run `python3 scripts/deal_scenarios.py --spec <spec.json> --market <mkt>`.
   It folds each amenity's build cost (Renovation Rates) + a real building permit into the
   cash invested, applies a revenue lift, and shows CoC for each combo. Respect the
   `condo_ok` feasibility flag: private pools aren't feasible on a condo; a hot tub needs
   HOA approval. Remind Jeremiah the build cost grows the denominator, so amenities usually
   pair with a price cut.

10. **Permit costs + property-tax tier (per market).** `scripts/permit_costs.py` computes
    building permit fees, holds STR-registration + lodging-tax data, and computes the
    **vacation-rental property-tax tier** (`--assessed <value>`). Set the spec's
    `permit_market` (e.g. `kauai-hi`) and `property_tax` from the vacation-rental class, NOT
    the seller's owner-occupied bill — `fill_deal_analyzer` warns if it looks wrong. If the
    deal is **outside a researched market**, research it first (STR legality + registration,
    building-permit schedule, lodging taxes, property-tax tiers), add a `MARKETS` entry and
    `permit-costs/<market>.md`. Confirm STR-legality before anything else — it's the gate.

11. **Probabilistic cash flow.** `scripts/deal_probabilistic.py --spec <spec> --low L --mode M
    --high H` samples revenue (use the AirROI P25 / median / P75, haircut as needed) and
    reports the probability of positive cash flow + the CoC range. Lead the verdict with
    this when a deal is marginal — "negative 95% of the time" is clearer than a point estimate.

Note: `fill_deal_analyzer` (step 7) now also prints **manager economics** (StayAscend's
management fee revenue) and a **checks** block (condo warrantability, lodging-tax context,
property-tax-tier validation). Relay those in the report. The full pipeline runs in one
command via the standalone package's `analyze.py`.

## Guardrails

- **Never invent revenue.** Source it or clearly label the estimate and its basis.
- **Never claim STR-legal without finding the zoning.** Unknown = say unknown.
- **Show your assumptions.** Separate sourced facts from your defaults in the report.
- **Don't overwrite a prior analysis** — each run writes a fresh, address-named file.
- This faces an investment decision. When a key fact can't be sourced, say so and give
  the range, don't paper over it with a confident single number.

## Log it

When Jeremiah acts on an analysis (offers, passes, signs), suggest a one-line entry in
`decisions/log.md` with the address and the deciding metric.
