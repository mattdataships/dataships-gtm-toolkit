---
name: sqo-attribution
description: |
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
Analyze marketing attribution for deals in the SQO list. Pull deal + contact data, review all context (emails, meetings, source properties, events), determine correct attribution using last-touch logic, and update HubSpot after Matt's approval.

## Default List
- **SQO List ID:** 6780
- URL: https://app.hubspot.com/contacts/8868359/objectLists/6780/filters
- Use this unless Matt specifies a different list

## HubSpot Property
- **Property to read and update:** `deal_type___sub_category` (label: "Deal Type - Sub Category")
- This is an enumeration field — only use valid values listed below

## Process

### Step 1: Pull Deals from the SQO List
Use `search_crm_objects` with `ilsListIds` property filter:
```
objectType: deals
filterGroups: [{"filters": [{"propertyName": "ilsListIds", "operator": "EQ", "value": "6780"}]}]
```

Properties to pull on deals:
- `dealname`, `dealstage`, `deal_type___sub_category`, `amount`
- `hs_analytics_source`, `hs_analytics_source_data_1`, `hs_analytics_source_data_2`
- `hs_analytics_latest_source`, `hs_analytics_latest_source_data_1`, `hs_analytics_latest_source_data_2`
- `most_recent_converting_event`, `associated_event`
- `pipeline`

### Step 2: Pull Associated Contacts
For each deal, get associated contacts. Then pull contact properties:
- `email`, `firstname`, `lastname`
- `hs_analytics_source`, `hs_analytics_source_data_1`
- `hs_analytics_latest_source`, `hs_analytics_latest_source_data_1`
- `associated_event_s_`, `most_recent_converting_event`

### Step 3: Review Engagement Context
For each deal, check:
- **Emails on the DEAL object** (critical — DTConnect emails often only appear here)
- **Emails on the CONTACT object**
- **Meetings** on both objects
- **Notes** if present

Look for attribution keywords in email subjects, bodies, and meeting titles.

### Step 4: Determine Attribution (Last-Touch Logic)
Most recent signal wins. Work through this decision tree:

#### LinkedIn Ads
- **Match if:** Email contains "$100 gift card" keyword OR `hs_analytics_source` = PAID_SOCIAL with `source_data_1` = LinkedIn
- **Value:** `Marketing-Paid-Campaign`

#### Meta Ads
- **Match if:** `hs_analytics_source` = PAID_SOCIAL with `source_data_1` containing Meta/Facebook/Instagram
- **Value:** `Marketing-Paid-Campaign`

#### Landmark (LMV)
- **Match if:** Any email/meeting contains "landmark" or "scott zakheim" (case-insensitive)
- **Value:** `Marketing-LMV-Matchmaking`

#### DTConnect
- **Match if:** Any email/meeting contains "dtconnect" (case-insensitive). CRITICAL: Check emails on the DEAL object — DTConnect emails often only appear there, not on the contact.
- **Value:** `Marketing-DTConnect-Matchmaking`

#### EXN
- **Match if:** Any email/meeting contains "exn" (case-insensitive)
- **Value:** `Marketing-EXN-Matchmaking`

#### Events
- **Match if:** Contact has a value in `associated_event_s_` or `most_recent_converting_event` AND no other attribution signal is present
- **Value:** `Marketing-Events`

#### Inbound
- **Match if:** `hs_analytics_source` is DIRECT_TRAFFIC, ORGANIC_SEARCH, ORGANIC_SOCIAL, or REFERRALS. Also YouTube discovery.
- **Value:** `Marketing-Free-trial` (label: "Marketing-Inbound")

#### Fallback
- If no clear signal, flag for manual review

### Step 5: Present Results
Show Matt:

1. **Deal-by-deal table:**
   | Deal | Current Attribution | Recommended Attribution | Signal | Confidence |

2. **Summary by channel:**
   | Channel | Count | Total $ |

3. **Deals needing updates** (where current ≠ recommended)

### Step 6: Ask for Approval
Say: **"Do you approve these attribution updates?"**

Wait for explicit "yes" / confirmation before updating anything.

### Step 7: Update HubSpot
Only after Matt approves:
- Use `manage_crm_objects` to update `deal_type___sub_category` on each approved deal
- Show confirmation of each update

## Valid `deal_type___sub_category` Values (Marketing-relevant)

| Value (internal) | Label |
|-----------------|-------|
| `Marketing-Paid-Campaign` | Marketing-Paid Campaign |
| `Marketing-LMV-Matchmaking` | Marketing-LMV-Matchmaking |
| `Marketing-DTConnect-Matchmaking` | Marketing-DTConnect-Matchmaking |
| `Marketing-EXN-Matchmaking` | Marketing-EXN-Matchmaking |
| `Marketing-GROW-Matchmaking` | Marketing-GROW-Matchmaking |
| `Marketing-Events` | Marketing-Events |
| `Marketing-Free-trial` | Marketing-Inbound |
| `Marketing-Outbound` | Marketing-Outbound |
| `marketing_owned` | Marketing-Owned |
| `marketing-additional-store` | Marketing-Additional Store |
| `marketing_sessionary` | Marketing-Sessionary |
| `PLS-Other` | Marketing-All |
| `Marketing - Closed Lost Re-engage` | Marketing - Closed Lost Re-engage |
| `Matchmaking-Sessionary` | Matchmaking-Sessionary |

## All Valid Values (full enum for reference)

Agency-From Event, Agency-From Outbound, Customer-Additional Store, Customer-Downsell, Customer-Free-trial, Customer-Reactivation, Customer-Referral, Customer-Renewal, Customer-Renewal including SMS, Customer-Renewal-Churned, Customer-Upsell, Customer-Uptier, Digital Influencer-From Event, Digital Influencer-From Outbound, Marketing - Closed Lost Re-engage, Marketing-All, Marketing-DTConnect-Matchmaking, Marketing-Events, Marketing-EXN-Matchmaking, Marketing-GROW-Matchmaking, Marketing-Inbound, Marketing-LMV-Matchmaking, Marketing-Outbound, Marketing-Owned, Marketing-Additional Store, Marketing-Sessionary, Marketing-Paid Campaign, Partnership-Additional Store, Partnership-Free Trial, Partnerships - Closed Lost Re-engage, Partnerships-Co Marketing, Partnerships-Co Marketing (tech), Partnerships-Event, Partnerships-Event (Tech), Partnerships-Referral, Partnerships-Referral (Tech), Sales - Closed Lost Re-engage, Sales-Additional Store, Sales-AE Generated, Sales-BDR Generated, Sales-Email, Sales-Free Trial, Sales-Owned, Sales-HappyStack, Tech Partner-From Event, Tech Partner-From Outbound, Matchmaking-Sessionary

## Important Notes
- **Subagents cannot access HubSpot MCP tools** — run all queries from the main thread
- **Always check emails on BOTH contact AND deal** — this is the #1 source of missed DTConnect attribution
- **Last-touch wins** — if a deal has both a LinkedIn ad source AND a Landmark email, the most recent signal determines attribution
- **List query syntax:** `{"propertyName": "ilsListIds", "operator": "EQ", "value": "6780"}` — this works for deals
