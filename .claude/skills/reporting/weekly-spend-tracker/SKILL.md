---
name: weekly-spend-tracker
description: |
  Run the weekly Marketing spend tracker update by pulling SQO and Closed-Won deal data
  from HubSpot, broken down by deal type sub-category, and outputting copy-pastable rows
  for the Google Sheet.
  Triggers on: "do my weekly sheet update", "spend tracker update", "weekly SQO sheet",
  "weekly marketing tracker", "update the marketing sheet", "pull my weekly numbers",
  or references the marketing spend tracker in any way.
  Do NOT use for: weekly sales report (use weekly-sales-report), SQO attribution
  (use sqo-attribution), event enrichment (use event-enrichment)
argument-hint: optionally specify week-ending dates or number of weeks
---

# Weekly Marketing Spend Tracker Update

## What This Does
Pulls Marketing (dealtype = "PLS") deals from HubSpot for specified week-ending dates and outputs two sets of tab-separated, copy-pastable rows for the user's Google Sheet:
1. **SQO rows** — deals that entered "Demo Held - SQO" stage during each week
2. **Closed-Won rows** — deals that entered "Closed won - Customer" stage during each week

## Google Sheet Columns (same for both SQO and Closed-Won)
```
Week ending | Inbound SQO# | Inbound SQO$ | LinkedIn SQO# | LinkedIn SQO$ | Meta SQO# | Meta SQO$ | Events SQO# | Events SQO$ | DTConnect SQO# | DTConnect SQO$ | Landmark SQO# | Landmark SQO$ | GROW SQO# | GROW SQO$ | Matchmaking-other SQO# | Matchmaking-other SQO$ | Other SQO# | Other SQO$
```
For Closed-Won, the column labels say "Customers" and "Revenue" instead of "SQO" and "Pipe", but the structure is identical.

## Step 0: Determine Week-Ending Dates
Weeks always end on **Sundays**, following a consistent weekly cadence (e.g. 1/4, 1/11, 1/18, 1/25, 2/1, 2/8, ...). To find the right dates:
- Calculate the most recent Sunday relative to today
- Work backwards as needed
- If the user says "do my weekly update" with no dates, default to the **last 3 Sundays not yet completed** in the sheet
- If the user specifies weeks (e.g. "last 2 weeks", "through 3/15"), calculate the corresponding Sundays
- Always confirm the week-ending dates before pulling data

## Step 1: Get HubSpot User Details
Call `HubSpot:get_user_details` to confirm access and get the ownerId.

## Step 2: Pull SQO Deals
Search HubSpot for deals matching:
- `dealtype = "PLS"` (Marketing)
- `hs_v2_date_entered_presentationscheduled` within the date range covering all requested weeks

Properties to pull:
```
dealname, dealtype, deal_type___sub_category, amount,
hs_v2_date_entered_presentationscheduled, hs_analytics_source,
hs_analytics_source_data_1, hs_analytics_source_data_2,
hs_analytics_latest_source, hs_analytics_latest_source_data_1
```

## Step 3: Pull Closed-Won Deals
Same filter but use `hs_v2_date_entered_closedwon` instead of the SQO date field.

Properties to pull:
```
dealname, dealtype, deal_type___sub_category, amount,
hs_v2_date_entered_closedwon, closedate, hs_analytics_source,
hs_analytics_source_data_1, hs_analytics_source_data_2,
hs_analytics_latest_source, hs_analytics_latest_source_data_1
```

## Step 4: Map Sub-Categories to Sheet Columns

| HubSpot `deal_type___sub_category` | Sheet Column |
|---|---|
| `Marketing-Free-trial` | **Inbound** |
| `Marketing-Paid-Campaign` (where source = LinkedIn) | **LinkedIn** |
| `Marketing-Paid-Campaign` (where source = Meta/Facebook) | **Meta** |
| `Marketing-Events` | **Events** |
| `Marketing-DTConnect-Matchmaking` | **DTConnect** |
| `Marketing-LMV-Matchmaking` | **Landmark** |
| `Marketing-GROW-Matchmaking` | **GROW** |
| `marketing_sessionary` | **Matchmaking-other** |
| `Marketing-EXN-Matchmaking` | **Matchmaking-other** |
| `PLS-Other` or `marketing_owned` or anything else | **Other** (flag for review) |

### Important: LinkedIn vs Meta disambiguation
Deals tagged `Marketing-Paid-Campaign` need further inspection:
- Check `hs_analytics_source_data_1` and `hs_analytics_latest_source_data_1`
- If LinkedIn → **LinkedIn** column
- If Facebook/Instagram/Meta → **Meta** column
- If unclear → flag for review

## Step 5: Attribution Review
Any deal categorized as `PLS-Other`, `marketing_owned`, or with unclear sub-category **must be investigated**:

1. Pull the associated **contact** record and check their source fields
2. Pull **email** activity on the contact to look for clues (e.g. email subjects containing "DTConnect Opportunity", "Sessionary", event names, etc.)
3. List each flagged deal with:
   - Deal name and amount
   - Current sub-category
   - What the source data and email threads suggest
   - Recommended correct column
4. Ask the user whether to update the sub-category in HubSpot before finalizing the numbers

## Step 6: Output Format
Output the final data as **tab-separated rows** that can be directly pasted into Google Sheets. Format:

```
[week ending]	[Inbound#]	[Inbound$]	[LinkedIn#]	[LinkedIn$]	[Meta#]	[Meta$]	[Events#]	[Events$]	[DTConnect#]	[DTConnect$]	[Landmark#]	[Landmark$]	[GROW#]	[GROW$]	[Matchmaking-other#]	[Matchmaking-other$]	[Other#]	[Other$]
```

Rules:
- Dollar amounts formatted as `$X,XXX` (no decimals unless cents matter)
- Counts are plain integers
- One row per week-ending date
- Provide SQO rows first, then Closed-Won rows, clearly labeled
- If a category has 0 deals, show `0` and `$0`

## Step 7: Offer the Excel File
Also offer to generate an .xlsx file with the data in case the user wants to download it instead of copy-pasting.

## Reference: HubSpot Filter Values
- **Deal Type (Marketing):** `dealtype = "PLS"`
- **SQO date field:** `hs_v2_date_entered_presentationscheduled`
- **Closed-Won date field:** `hs_v2_date_entered_closedwon`
- **HubSpot portal:** `8868359`
- **Segment list for SQOs:** `objectLists/6691`
- **Segment list for Closed-Won:** `objectLists/6690`
