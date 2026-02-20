# Event GTM Enrichment Playbook

## Overview
When Matt says "run the Denver playbook" or "enrich this event list", follow this process to match event company lists against Storeleads data and HubSpot deals, then produce a ranked Excel file.

## Step 0: Ask About the Event (ALWAYS do this first)
Before diving into data, ask Matt:
1. **What's the event?** (name, location, rough cost)
2. **What's the format?** (intimate dinner, networking drinks, big conference, booth, etc.)
3. **How many brands will be there?** (10-person dinner vs. 500-person expo floor)
4. **What's the goal?** (recruiting best-fit brands, lead gen, existing relationship deepening, etc.)

This context matters for the viability assessment at the end.

## Input Files (typically in ~/Downloads/)
1. **Event CSV** - Single "Company" column with company names (may have duplicates, "NA" rows)
2. **Storeleads TAM CSV** - `data/storeleads-tam.csv` — columns: domain, categories, cluster_domains, combined_followers, country_code, domain_count, estimated_monthly_visits, estimated_yearly_sales, installed_apps_names, linkedin_url, merchant_name, plan, platform_rank, twitter_followers

## Process
1. **Parse & deduplicate** the event company list (strip whitespace, remove NA rows, deduplicate)
2. **Fuzzy match** company names to Storeleads `merchant_name` and `domain` fields. Use Python's difflib or fuzzywuzzy. IMPORTANT: Many fuzzy matches are wrong — verify high-confidence matches and discard anything uncertain.
3. **Search HubSpot deals** for each company individually using the `search_crm_objects` tool with `query` parameter. Check all deal stages.
4. **Check international presence** from `cluster_domains` field. Only count as "Sells Internationally" if 4+ unique country TLDs exist (single .co.uk domains are often just parked sites).
5. **Score and rank** companies, then output to Excel.
6. **Run the Event Viability Assessment** (see below).

## Known Name Mismatches (add to this over time)
- "Laird Superfoods" -> lairdsuperfood.com (Storeleads has "Laird Superfood" singular)

## HubSpot Deal Stage Mappings (Hub ID: 8868359)
### Pipeline: default
- qualifiedtobuy = Demo Scheduled (SQL)
- presentationscheduled = Demo Held (SQO)
- 96256085 = Onboarded (SQO)
- 998696192 = Negotiation (SQO)
- closedwon = Closed Won (Customer)
- closedlost = Closed Lost
- 996552883 = Contract in Progress (Customer/Renewal)
- 996552884 = Nurturing (Customer)

### Pipeline: 679446319
- 996552885 = SQL
- 996552886 = SQO
- 996552887 = Negotiation (SQO)
- 996552888 = Closed Won (Customer)
- 996552889 = Closed Lost

### Pipeline: 865747095 (Re-engagement)
- 1295432467 = Target (re-engagement)
- 1295432473 = Closed Lost

## Scoring Rubric
| Factor | Points | Notes |
|--------|--------|-------|
| Shopify Plus | +3 | |
| Klaviyo installed | +3 | |
| Attentive installed | +3 | |
| Sells internationally (4+ countries) | +4 | Based on cluster_domains TLDs |
| Postscript installed | -2 | Only -1 if platform_rank < 1000 AND sells internationally |
| Est. sales > $100M | +3 | |
| Est. sales > $50M | +2 | |
| Est. sales > $20M | +1 | |
| Platform rank top 100 | +2 | |
| Platform rank top 500 | +1 | |
| Not in Storeleads TAM | -5 | |

## Exclusion Rules (red highlight, marked "No")
- **Customer** (Closed-Won): No - Customer
- **Closed-Lost**: No - Closed-Lost
- **SQO** (active opportunity): No - SQO

## Pick Status Tiers
- Score >= 10: Top Pick (dark green)
- Score 6-9: Good Pick (light green)
- Score 3-5: Okay (light blue)
- Score 0-2: Low Priority (light grey)
- Score < 0: Poor Fit (grey)

## Excel Output Format
- File: `{Event_Name}_Event_Ranked.xlsx`
- Columns: Rank, Pick Status, Company, Score, Domain, Shopify Plus, Klaviyo, Attentive, Postscript, Sells Internationally, Intl Countries, Platform Rank, Est. Annual Sales, HubSpot Status, Scoring Breakdown, Match Confidence
- Frozen top row, auto-filter enabled
- Color coding: green=yes/good, red=no/excluded, yellow=postscript/warning, grey=N/A
- Excluded companies sorted to bottom with red fill and strikethrough on company name

## International TLDs to Check
.co.uk, .ca, .com.au, .de, .fr, .eu, .co.jp, .co.nz, .nl, .es, .it, .co.il, .com.ru, .se, .no, .dk, .at, .ch, .ie, .mx, .com.br, .co.in

## Speed Tips
- If Matt provides a HubSpot deals CSV export, match locally instead of 80+ API calls
- HubSpot list-based queries (ilsListIds) do NOT work for deal lists — always search by deal stage or company name
- Subagents cannot access HubSpot MCP tools — run all HubSpot queries from the main thread

---

## Part 2: Event Viability Assessment

After ranking companies, add a viability summary to help Matt decide whether the event investment is worth it. Reference the historical event performance data below.

### Historical Event Benchmarks (Jan 2025 - Feb 2026)

| Event | Format | Spend | All-In (w/ 15% T&E) | Contacts | Deals | Won ARR | ROI | Contact->Deal % | CAC | Avg Deal ARR |
|-------|--------|-------|---------------------|----------|-------|---------|-----|----------------|-----|-------------|
| Camp Commerce | Mid-size commerce, networking | $27,500 | $31,625 | 52 | 8 | $103,932 | 3.78x | 15.4% | $5,500 | $21,764 |
| SF Instant Dinner | Intimate dinner | $2,376 | $2,733 | -- | 1 | $7,200 | 3.03x | -- | $2,376 | $7,200 |
| CTC Summit | Mid-size, heavy networking | $15,000 | $17,250 | 33 | 9 | $39,600 | 2.64x | 27.3% | $7,500 | $26,267 |
| Shoptalk | Large conference/booth | $28,225 | $32,459 | 82 | 9 | $12,444 | 0.44x | 11.0% | $14,113 | $16,048 |
| League of Originals | Mid-size exclusive | $33,304 | $38,300 | 57 | 4 | $0 (open) | pending | 7.0% | -- | $14,466 |
| Klaviyo Boston | Conference | $5,232 | $6,017 | 10 | 0 | $0 | 0x | 0% | -- | -- |
| DTC Live London | Large conference | $5,232 | $6,017 | 310 | 0 | $0 | 0x | 0% | -- | -- |
| Lead Foremost 50 | Exclusive/curated | $16,000 | $18,400 | 31 | 1 | $0 (open) | pending | 3.2% | -- | $9,000 |

**Portfolio Totals:** $133,619 spend -> $204,804 closed-won ARR. 1.51x all-in ROI (with T&E). $125,664 still in open pipeline.

### Key Insight: Event Format Matters More Than Size
- **Best ROI: Intimate/networking events** -- Camp Commerce (3.78x), SF Dinner (3.03x), CTC Summit (2.64x). These are smaller, relationship-focused, high-quality attendee lists.
- **Worst ROI: Big conferences** -- Shoptalk (0.44x), Klaviyo Boston (0x), DTC Live London (0x). High spend, low conversion, diluted attention.
- **Average deal ARR across all events:** ~$15,500
- **Blended CAC:** ~$13,400 (but intimate events achieve $2,400-$7,500 CAC)
- **Overall win rate:** 30.3% (deal->closed-won)

### Viability Assessment Template
After ranking, produce a summary like this:

```
EVENT VIABILITY: [Event Name]
Format: [intimate dinner / networking drinks / conference booth / etc.]
Comparable past event: [closest match from historical data]

Company Quality:
  - Total companies: X
  - Targetable (not excluded): X
  - Top/Good Picks: X (Y% of targetable)
  - Okay+: X

Projected Outcomes (using comparable event conversion rates):
  - Expected deals: X (based on [comparable]'s Z% contact->deal rate)
  - Expected pipeline ARR: $X (at $15.5K avg deal ARR)
  - Expected closed-won ARR: $X (at 30% win rate)
  - Projected ROI: X.Xx (expected ARR / all-in cost)

Break-even: Need to close X deals to cover $Y all-in cost

Verdict: [GO / WORTH IT / MARGINAL / PASS]
  - GO: Projected ROI > 2x and format matches proven winners
  - WORTH IT: Projected ROI 1-2x or strong strategic value
  - MARGINAL: ROI near 1x, depends on execution
  - PASS: ROI < 1x with no strategic upside
```

### Format-Specific Conversion Rates (use these for projections)
- **Intimate dinner/drinks (< 20 brands):** 25-30% contact->deal rate (use CTC Summit/SF Dinner benchmarks)
- **Curated networking event (20-60 brands):** 15% contact->deal rate (use Camp Commerce benchmark)
- **Large conference (60+ brands):** 7-11% contact->deal rate (use Shoptalk/League benchmark)
- **Pure conference/booth (no curated access):** 0-5% (use Klaviyo Boston benchmark)

### Deal Cost Modeling

Events may have different cost structures. Always ask Matt for the cost details and model accordingly.

**Common structures:**
1. **Flat fee** -- Simple: all-in cost = fee + 15% T&E
2. **Base + % of wins** -- e.g., $5K base + 5% of Year 1 ARR on closed deals. Model this across scenarios since all-in cost scales with success.
3. **Sponsorship tiers** -- Booth + add-ons. Sum all line items.

**Always produce a scenario table like this:**

```
| Scenario | Deals Won | Won ARR | Base Cost | Variable Cost | All-In | Net ARR | ROI |
|----------|-----------|---------|-----------|---------------|--------|---------|-----|
| Conservative (1 win) | 1 | $15.5K | $X | $Y | $Z | ... | ...x |
| Base case (2 wins) | 2 | $31K | $X | $Y | $Z | ... | ...x |
| Upside (3 wins) | 3 | $46.5K | $X | $Y | $Z | ... | ...x |
| Zero wins | 0 | $0 | $X | $0 | $X | -$X | 0x |
```

**Scenario calibration by format:**
- Intimate (< 20 brands): Assume 25-30% of attendees -> deal. So 10 brands = 2-3 deals expected.
- Curated (20-60): Assume 15%. So 40 brands = 6 deals expected.
- Large conference (60+): Assume 7-11%. So 80 brands = 6-9 deals expected, but lower win rate.

**Use $15,500 as default avg deal ARR** and **30% deal->closed-won win rate** unless Matt provides updated numbers.

**Break-even calculation:** All-in cost / avg deal ARR = deals needed to break even. Always state this clearly.

**Key framing for Matt:**
- Variable cost structures (base + %) are almost always favorable -- the cost only goes up when you're winning.
- For intimate events at < $5K base cost, break-even is typically a fraction of one deal. These are nearly risk-free.
- For $15K+ events, scrutinize whether the format and company quality justify it -- compare to historical events at similar spend levels.
- The biggest ROI lever is always **who's in the room**, not the event cost. A $5K event with 10 Top Picks beats a $30K conference with 500 random companies.
