---
name: weekly-sales-report
description: |
  Use when user asks for the weekly sales report, sales numbers, pipeline update,
  WTD/QTD metrics, or says "run" in the context of sales reporting.
  Triggers on: "run", "weekly report", "sales report", "pipeline update",
  "WTD numbers", "QTD numbers", "how are we tracking", "sales update"
  Do NOT use for: SQO attribution (use sqo-attribution), event enrichment (use event-enrichment),
  or Gong call review (use gong-review)
argument-hint: none required — uses fixed HubSpot lists
---

# Weekly Sales Report Skill

## Overview
Pull deal data from four HubSpot lists, break down by Marketing vs Partnerships, and produce a formatted WTD + QTD report with progress against quarterly targets.

## Data Sources (HubSpot Lists)

| List ID | Name | Scope |
|---------|------|-------|
| 6688 | SQOs created this week | WTD — Demo Held / SQO stage |
| 6689 | Closed Won deals this week | WTD |
| 6691 | SQOs created this quarter | QTD |
| 6690 | Closed Won deals this quarter | QTD |

## How to Query

**Use compound filters** — always filter by BOTH `ilsListIds` AND `dealtype` in the same query. This returns pre-separated data so you never need to manually sort deals by type.

Run **8 parallel queries** (4 lists × 2 deal types):

```
objectType: deals
filterGroups: [{"filters": [
  {"propertyName": "ilsListIds", "operator": "EQ", "value": "{LIST_ID}"},
  {"propertyName": "dealtype", "operator": "EQ", "value": "PLS"}
]}]
```

The 8 queries:
1. List 6688 + PLS (WTD Marketing SQOs)
2. List 6688 + Partnership (WTD Partnership SQOs)
3. List 6689 + PLS (WTD Marketing Won)
4. List 6689 + Partnership (WTD Partnership Won)
5. List 6691 + PLS (QTD Marketing SQOs)
6. List 6691 + Partnership (QTD Partnership SQOs)
7. List 6690 + PLS (QTD Marketing Won)
8. List 6690 + Partnership (QTD Partnership Won)

Pull these properties on every query:
- `dealname`, `amount`

Set `limit: 200` to avoid pagination issues.

**Pagination:** If `total` > `limit`, paginate using `offset` to get all deals. Never report partial data.

## Quarterly Targets (Q1 2026)

### Marketing (dealtype = PLS)
- **Deals:** 105
- **Pipeline:** $105K
- **Revenue:** $35K

### Partnerships (dealtype = Partnership)
- **Deals:** 60
- **Pipeline:** $60K
- **Revenue:** $30K

**Note:** Update these targets each quarter when Matt provides new numbers.

## Metrics Definitions

- **Deals** = count of deals in the list for that dealtype
- **Pipeline** = sum of `amount` for all deals in the SQO list for that dealtype
- **Revenue** = sum of `amount` for all deals in the Closed Won list for that dealtype

## Report Format

```
=== WEEK TO DATE ===

Marketing: X deals, $XK pipeline, $XK revenue
Partnerships: X deals, $XK pipeline, $XK revenue

=== QUARTER TO DATE ===

Marketing
- Deals: X/105 (X%)
- Pipeline: $XK/$105K (X%)
- Revenue: $XK/$35K (X%)
- New customers this week: [bullet list]

Partnerships
- Deals: X/60 (X%)
- Pipeline: $XK/$60K (X%)
- Revenue: $XK/$30K (X%)
- New customers this week: [bullet list]
```

## Formatting Rules
- Currency in **K notation**: $86,900 → $86.9K. Round to one decimal.
- Percentages: round to nearest whole number
- "New customers this week" = deal names from **list 6689 only** (Closed Won this week), bulleted
- If a deal has $0 or $0.1 amount, still count it as a deal but note it may need amount correction

## Process

1. **Run all 8 queries in parallel** — one call per list+dealtype combo (see "How to Query" above)
2. **Write raw API responses to temp JSON files** — immediately after receiving each query result, write the full results array to a temp file (e.g., `/tmp/wtd_mkt_sqo.json`). One file per query. This is MANDATORY — never skip this step.
3. **Sum amounts with a Python script that reads from the temp files** — the script must parse the JSON files and extract `amount` from each deal programmatically. NEVER manually transcribe amounts into an array. This was the source of a real error where 9 deals were dropped from a 105-deal list, producing a $1.5K discrepancy.
4. **Get deal counts** from the `total` field in each query response
5. **Get new customer names** from the WTD Won queries (lists 6689)
6. **Calculate % progress** against quarterly targets
7. **Output the formatted report** — go straight to the clean readout, no intermediate analysis

Example of the correct approach for step 2-3:
```python
# Step 2: Write each API response to a file
import json
# After each MCP query, write results to /tmp/
with open('/tmp/qtd_mkt_sqo.json', 'w') as f:
    json.dump(results, f)

# Step 3: Sum from files — NEVER from manually typed arrays
import json
with open('/tmp/qtd_mkt_sqo.json') as f:
    deals = json.load(f)
total = sum(float(d['properties']['amount'] or 0) for d in deals)
```

## Execution Rules
- **Subagents cannot access HubSpot MCP tools** — run all queries from the main thread
- **All 8 queries in parallel** — this is the single biggest speed lever
- **NEVER manually transcribe amounts** — always write API responses to temp JSON files and have Python read from those files. Manual transcription of large deal lists WILL produce errors. This is the #1 accuracy rule.
- **Don't overcomplicate** — no subagents, no extra analysis steps. Query → write to file → script reads files → report.
- If any query returns 0 results, report it as 0 — don't error out
- Watch for deals with `amount` = "0.1" — these are placeholder amounts from auto-created deals and should be flagged
