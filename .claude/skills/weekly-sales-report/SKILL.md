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

Use `search_crm_objects` with `ilsListIds` property filter:

```
objectType: deals
filterGroups: [{"filters": [{"propertyName": "ilsListIds", "operator": "EQ", "value": "{LIST_ID}"}]}]
```

Pull these properties on every query:
- `dealname`, `dealtype`, `amount`, `dealstage`, `pipeline`, `closedate`

**Pagination:** If `total` > `limit`, paginate using `offset` to get all deals. Never report partial data.

## Deal Type Mapping

| `dealtype` value | Report category |
|-----------------|-----------------|
| `PLS` | Marketing |
| `Partnership` | Partnerships |
| All others | Exclude from this report |

Only Marketing and Partnerships deals appear in this report. Filter out Sales, Customer, Agency, etc.

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

1. **Query all four lists** — pull all deals from 6688, 6689, 6690, 6691
2. **Filter by dealtype** — separate into PLS (Marketing) and Partnership (Partnerships)
3. **Calculate WTD metrics** — from lists 6688 (SQO) and 6689 (Closed Won)
4. **Calculate QTD metrics** — from lists 6691 (SQO) and 6690 (Closed Won)
5. **Calculate % progress** against quarterly targets
6. **List new customers** — deal names from list 6689, grouped by category
7. **Output the formatted report**

## Important Notes
- **Subagents cannot access HubSpot MCP tools** — run all queries from the main thread
- **Query all four lists in parallel** when possible to speed things up
- If any list returns 0 results, report it as 0 — don't error out
- Watch for deals with `amount` = "0.1" — these are placeholder amounts from auto-created deals and should be flagged
