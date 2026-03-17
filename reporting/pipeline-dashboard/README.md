# Dataships Sales Pipeline — Conversion Dashboard

Generates an HTML dashboard from HubSpot CRM deal data, showing conversion rates, cohort analysis, AE performance, time-to-close metrics, and channel economics (spend / CAC / ROI).

## Quick Start

```bash
python build_dashboard.py
open dataships_conversion_dashboard.html
```

No external dependencies — uses only the Python standard library.

## What It Does

Reads raw HubSpot API response files from `data/` and produces a self-contained HTML dashboard with:

- **Pipeline funnel** — stage-to-stage conversion rates (volume and revenue)
- **Conversion by deal type** — Sales, Marketing, Partnerships, Customer, Agency
- **Conversion by sub-category** — ~20 granular sub-categories with spend/CAC/ROI where data is available
- **Channel economics** — total spend, cost per SQL, CAC, and ROI (ARR-based) for tracked marketing channels
- **AE performance** — per-rep win rates with last-quarter trends
- **Monthly cohort analysis** — cohort maturity tracking with marketing spend overlay
- **Time-to-close** — median/avg days, speed vs win rate, breakdowns by deal type, AE, and cohort

## Data

The `data/` directory contains four batches of HubSpot deal records (709 deals total, created Jan 2025+). Each file is a raw API response with deal properties including stage entry timestamps (`hs_v2_date_entered_*`) for accurate funnel tracking.

## Configuration

All configuration lives at the top of `build_dashboard.py`:

- `STAGE_MAP` — maps HubSpot stage IDs to display names
- `DEALTYPE_MAP` — maps raw deal types to clean categories
- `OWNER_MAP` — maps HubSpot owner IDs to names
- `SPEND_2025` / `SPEND_2026` — monthly marketing spend by program
- `AE_EXCLUDE` — owner names excluded from AE reports

## Key Formulas

- **Win Rate** = Won / (Won + Lost) — excludes open deals from denominator
- **Won $** = MRR (monthly recurring revenue)
- **ROI** = (ARR from wins - spend) / spend, where ARR = MRR x 12
- **CAC** = total channel spend / customers won
- **Cohort maturity** = >70% resolved is "mature", 40-70% is "maturing", <40% is "immature"
