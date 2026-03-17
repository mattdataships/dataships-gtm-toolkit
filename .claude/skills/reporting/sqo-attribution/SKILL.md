---
name: sqo-attribution
description: |
  SQO Attribution Skill
  Use when user asks about SQO attribution, weekly SQO report, marketing attribution,
  deal attribution analysis, or channel attribution.
  Triggers on: "SQO report", "attribution report", "run attribution", "weekly SQOs",
  "check attribution", "deal attribution", "channel attribution"
  Do NOT use for: event enrichment (use event-enrichment), Gong call review (use gong-review),
  or general HubSpot deal lookups
argument-hint: optional list ID override (default: 6780)
---

# SQO Attribution Skill

## Overview
Analyze marketing attribution for deals in the SQO list. Pull deal + contact data, review all context (emails, meetings, source properties, engagement history), determine correct attribution using the decision framework below, and update HubSpot after Matt's approval.

## Default List
- **SQO List ID:** 6780
- URL: https://app.hubspot.com/contacts/8868359/objectLists/6780/filters
- Use this unless Matt specifies a different list

## HubSpot Property
- **Property to read and update:** `deal_type___sub_category` (label: "Deal Type - Sub Category")
- This is an enumeration field — only use valid values listed in the taxonomy section below

---

## Process

### Step 1: Pull Deals from the SQO List
Use `search_crm_objects` with `ilsListIds` property filter:
```
objectType: deals
filterGroups: [{"filters": [{"propertyName": "ilsListIds", "operator": "EQ", "value": "6780"}]}]
```

Properties to pull on deals:
- `dealname`, `dealstage`, `deal_type___sub_category`, `amount`, `pipeline`
- `hs_analytics_source`, `hs_analytics_source_data_1`, `hs_analytics_source_data_2`
- `hs_analytics_latest_source`, `hs_analytics_latest_source_data_1`, `hs_analytics_latest_source_data_2`
- `most_recent_converting_event`, `associated_event`

### Step 2: Pull Associated Contacts
For each deal, get associated contacts. Then pull contact properties:
- `email`, `firstname`, `lastname`, `createdate`
- `how_did_you_hear_about_us` (free text — critical for attribution)
- `hs_analytics_source`, `hs_analytics_source_data_1`, `hs_analytics_source_data_2`
- `hs_analytics_latest_source`, `hs_analytics_latest_source_data_1`, `hs_analytics_latest_source_data_2`
- `associated_event_s_`, `most_recent_converting_event`

**Do NOT use** `where_did_you_hear_about_dataships_`, `how_you_found_us`, or `pls_referral_source` — these are not attribution properties.

### Step 3: Review Engagement Context
For each deal, check:
- **Emails on the DEAL object** (critical — DTConnect/EXN emails often only appear here)
- **Emails on the CONTACT object**
- **Meetings** on both objects
- **Notes** if present

Look for attribution keywords in email subjects, bodies, and meeting titles.

### Step 4: Check Contact Creation Context
- If the contact was created **3+ months ago** from an import, the import has little bearing on attribution UNLESS it is clearly an event import (identifiable by the import name on the record).
- If the contact was created recently and the creation source aligns with the deal context, it's a strong signal.

---

## Attribution Decision Framework

### Priority 1: Defer to Pre-Existing Sub-Category
If `deal_type___sub_category` is already set to a specific channel (not a generic catch-all like `PLS-Other` or `Marketing-Free-trial`), **defer to it** unless you see significant reason to override. Many deals are tagged automatically at creation from the source channel.

### Priority 2: Money-Touched Channels Win
If budget touched the channel — paid media, events, sponsorships, affiliate/matchmaking — prioritize credit to that channel over organic/inbound signals. The logic: if we paid to get them there, that's the attribution.

### Priority 3: Last-Touch with Context
Build a comprehensive picture from all signals, then apply these rules:

#### Affiliate / Matchmaking Platforms
Check emails on BOTH the deal and contact objects. These are high-confidence signals:

| Signal | Value |
|--------|-------|
| Email/meeting contains "dtconnect" | `Marketing-DTConnect-Matchmaking` |
| Email/meeting contains "exn" | `Marketing-EXN-Matchmaking` |
| Email/meeting contains "landmark" or "scott zakheim" | `Marketing-LMV-Matchmaking` |
| Email/meeting contains "grow" (matchmaking context) | `Marketing-GROW-Matchmaking` |
| Deal name or emails contain "sessionary" | `marketing_sessionary` |
| Email/meeting contains "validify" | `Marketing-Validify` |

#### Paid Media
Use UTM source data (`hs_analytics_source`, `source_data_1`, `source_data_2`) and `how_did_you_hear_about_us`:

| Signal | Value |
|--------|-------|
| `hs_analytics_source` = PAID_SOCIAL + `source_data_1` = LinkedIn, OR `how_did_you_hear_about_us` = "LinkedIn" | `Marketing-LinkedIn-Ads` |
| `hs_analytics_source` = PAID_SOCIAL + `source_data_1` contains Meta/Facebook/Instagram | `Marketing-Meta-Ads` |
| `hs_analytics_source` = PAID_SEARCH + Google context | `Marketing-Google-Ads` |
| Display/programmatic UTMs | `Marketing-Display-Programmatic` |
| `how_did_you_hear_about_us` mentions a podcast, newsletter sponsorship, or paid content placement (e.g., "Chew on This", "CTC") | `Marketing-Paid-Sponsorship` |

**Note on `how_did_you_hear_about_us` interpretation:**
- "LinkedIn" → `Marketing-LinkedIn-Ads` (we run paid there)
- "Google" → `Marketing-Organic-Search` (we are NOT spending on Google Ads as of Mar 2026)
- Unknown brand/company names (CTC, Tydo, etc.) → likely `Marketing-Paid-Sponsorship` or `Marketing-Co-Marketing` — **ask Matt to clarify** before assigning
- "Referral" + a name you don't recognize → same as above, ask Matt
- "Newsletter" → `Marketing-Newsletter` (also look for marketing email clicks preceding conversion on the record to confirm)
- "Podcast" → `Marketing-Paid-Sponsorship`

#### Events
| Signal | Value |
|--------|-------|
| Contact has `associated_event_s_` or `most_recent_converting_event`, OR event import on record | `Marketing-Events` |
| Event was partner-hosted (dinner, meetup, co-sponsored) | `Partnerships-Event` |

#### Inbound Channels
Use original/latest source UTMs to distinguish:

| Signal | Value |
|--------|-------|
| `hs_analytics_source` = ORGANIC_SEARCH, or "Google" in how_did_you_hear | `Marketing-Organic-Search` |
| `hs_analytics_source` = DIRECT_TRAFFIC | `Marketing-Direct-Traffic` |
| `hs_analytics_source` = REFERRALS | `Marketing-Referral-Traffic` |
| `hs_analytics_source` = ORGANIC_SOCIAL (no paid signal) | `Marketing-Organic-Social` |
| Marketing email clicks preceding conversion (look for click activity on marketing emails on the contact/deal record before the demo was booked) | `Marketing-Newsletter` |
| Webinar attendee | `Marketing-Webinar` |
| Co-branded content or joint campaign with a partner | `Marketing-Co-Marketing` |
| Marketing sequence to known contacts in DB, no clearer upstream source | `Marketing-Lifecycle-Sequence` |
| Cold outreach via LinkedIn by marketing team | `Marketing-LinkedIn-Outbound` |
| Other marketing-run outbound | `Marketing-Outbound` |

#### Sourcing Nuance: Sequences
- **Key signal:** If `hs_analytics_latest_source_data_1` contains `hello.dataships.io/meetings/demo-dataships/marketing` or similar marketing calendar booking links, the contact booked through a sequence. Cross-reference with `hs_email_last_open_date` and `hs_email_last_click_date` near the deal creation date to confirm.
- If a deal was driven by a **co-marketing or paid sponsorship campaign** that then triggered a lifecycle sequence → credit the **original paid source** (co-marketing or paid sponsorship)
- If a deal came via **organic content download or RB2B trigger** then got a sequence → credit **the sequence** (`Marketing-Lifecycle-Sequence` or `Marketing-Outbound`)
- If you see sequences/emails preceding meetings with no other paid signal → `Marketing-Lifecycle-Sequence` or `Marketing-Outbound`

#### Partnerships
| Signal | Value |
|--------|-------|
| Partner referral (agency, consultant, etc.) | `Partnerships-Referral` |
| Tech partner referral | `Partnerships-Referral (Tech)` |
| Agency sourced via outbound | `Agency-From Outbound` |
| Digital influencer sourced via outbound | `Digital-Influencer-From-Outbound` |

#### Sales
| Signal | Value |
|--------|-------|
| AE self-sourced the deal | `Sales - AE Generated` |

#### Customer
| Signal | Value |
|--------|-------|
| Existing customer referred them | `Customer - Referral` |
| Upsell | `Customer - Upsell` |
| Uptier | `Customer - Uptier` |
| Renewal | `Customer - Renewal` |
| Reactivation (churned customer returning) | `Customer-Reactivation` |

#### Fallback
- If no clear signal, flag for manual review and present your best guess with reasoning

---

## Valid `deal_type___sub_category` Values (New Taxonomy)

### Marketing — Inbound
| Internal Value | Label |
|---------------|-------|
| `Marketing-Organic-Search` | Marketing-Organic Search |
| `Marketing-Direct-Traffic` | Marketing-Direct Traffic |
| `Marketing-Referral-Traffic` | Marketing-Referral Traffic |
| `Marketing-Newsletter` | Marketing-Newsletter |
| `Marketing-Lifecycle-Sequence` | Marketing-Lifecycle Sequence |
| `Marketing-Co-Marketing` | Marketing-Co-Marketing |
| `Marketing-Organic-Social` | Marketing-Organic Social |
| `Marketing-Webinar` | Marketing-Webinar |
| `Marketing-LinkedIn-Outbound` | Marketing-LinkedIn Outbound |
| `Marketing-Outbound` | Marketing-Outbound |

### Marketing — Paid Media
| Internal Value | Label |
|---------------|-------|
| `Marketing-Google-Ads` | Marketing-Google Ads |
| `Marketing-LinkedIn-Ads` | Marketing-LinkedIn Ads |
| `Marketing-Meta-Ads` | Marketing-Meta Ads |
| `Marketing-Display-Programmatic` | Marketing-Display/Programmatic |
| `Marketing-Paid-Sponsorship` | Marketing-Paid Sponsorship |
| `Marketing-Paid-Campaign` | Marketing-Paid Campaign |

### Marketing — Events
| Internal Value | Label |
|---------------|-------|
| `Marketing-Events` | Marketing-Events |

### Marketing — Affiliate / Matchmaking
| Internal Value | Label |
|---------------|-------|
| `Marketing-DTConnect-Matchmaking` | Marketing-DTConnect |
| `Marketing-EXN-Matchmaking` | Marketing-EXN |
| `Marketing-GROW-Matchmaking` | Marketing-GROW |
| `Marketing-LMV-Matchmaking` | Marketing-LMV |
| `marketing_sessionary` | Marketing-Sessionary |
| `Marketing-Validify` | Marketing-Validify |

### Partnerships
| Internal Value | Label |
|---------------|-------|
| `Partnerships-Referral` | Partnerships-Referral |
| `Partnerships-Referral (Tech)` | Partnerships-Referral (Tech) |
| `Partnerships-Event` | Partnerships-Event |
| `Partnerships-Event (Tech)` | Partnerships-Event (Tech) |
| `Partnerships-co-marketing` | Partnerships-Co Marketing |
| `Partnerships-Co Marketing (tech)` | Partnerships-Co Marketing (tech) |
| `Agency-From Event` | Agency-From Event |
| `Agency-From Outbound` | Agency-From Outbound |
| `Digital-Influencer-From-Event` | Digital Influencer-From Event |
| `Digital-Influencer-From-Outbound` | Digital Influencer-From Outbound |

### Sales
| Internal Value | Label |
|---------------|-------|
| `Sales - AE Generated` | Sales-AE Generated |

### Customer
| Internal Value | Label |
|---------------|-------|
| `Customer - Referral` | Customer-Referral |
| `Customer - Upsell` | Customer-Upsell |
| `Customer - Uptier` | Customer-Uptier |
| `Customer - Renewal` | Customer-Renewal |
| `Customer-Reactivation` | Customer-Reactivation |

### Legacy / Deprecated (avoid using — remap if found)
| Internal Value | Maps To |
|---------------|---------|
| `Marketing-Free-trial` | Remap to specific inbound channel (default: `Marketing-Organic-Search`) |
| `PLS-Other` | Killed — must be recategorized |
| `marketing_owned` | `Marketing-Lifecycle-Sequence` |
| `Outbound - Cold Calling` | `Marketing-LinkedIn-Outbound` |
| `Outbound - Senders` | `Marketing-Outbound` |
| `sales_owned` | `Marketing-Lifecycle-Sequence` |
| `Sales-HappyStack` | Killed — deprecated |
| `marketing-additional-store` | NEVER USE — additional store is not an attribution category |
| `Customer - Additional Store` | NEVER USE — additional store is not an attribution category |
| `partnership-additional-store` | NEVER USE — additional store is not an attribution category |
| `sales-aditionalstore` | NEVER USE — additional store is not an attribution category |
| `Customer-Downsell` | Killed |
| `Customer-Free-trial` | Deal flag |
| `Sales-Free-trial` | Deal flag |
| `Partnership-Free-trial` | Deal flag |
| `Marketing - Closed Lost Re-engage` | Deal flag |
| `Sales - Closed Lost Re-engage` | Deal flag |
| `Partnerships - Closed Lost Re-engage` | Deal flag |

---

## Step 5: Present Results
Show Matt:

1. **Deal-by-deal table** (always include clickable deal links):
   | Deal | Link | Current Sub-Category | Recommended Sub-Category | Key Signals | Confidence |

2. **Summary by channel:**
   | Channel | Count | Total $ |

3. **Deals needing updates** (where current ≠ recommended)

4. **Deals needing clarification** (unknown brand names in how_did_you_hear, ambiguous signals)

## Step 6: Ask for Approval
Say: **"Do you approve these attribution updates?"**

Wait for explicit "yes" / confirmation before updating anything.

## Step 7: Update HubSpot
Only after Matt approves:
- Use `manage_crm_objects` to update `deal_type___sub_category` on each approved deal
- Show confirmation of each update

---

## Important Notes
- **Subagents cannot access HubSpot MCP tools** — run all queries from the main thread
- **Always check emails on BOTH contact AND deal** — DTConnect/EXN emails often only appear on the deal object
- **Pre-existing sub-category usually wins** — defer to it unless you see significant reason to override
- **Money-touched channels get priority** — if paid media, events, sponsorships, or affiliate drove the lead, credit goes there even if organic signals also exist
- **Ask Matt about unknown brand names** — if `how_did_you_hear_about_us` mentions a name you don't recognize, ask whether it's a paid sponsorship or co-marketing before assigning
- **List query syntax:** `{"propertyName": "ilsListIds", "operator": "EQ", "value": "6780"}`
