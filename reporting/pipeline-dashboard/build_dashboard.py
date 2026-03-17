#!/usr/bin/env python3
"""
Dataships Sales Pipeline - Conversion Rate Dashboard Builder
Reads raw HubSpot API response files, processes all deals, and generates an HTML dashboard.
"""

import json
import os
import sys
from datetime import datetime, timezone
from collections import defaultdict, OrderedDict

# ============================================================
# CONFIG
# ============================================================

STAGE_MAP = {
    "qualifiedtobuy": "Demo Scheduled (SQL)",
    "presentationscheduled": "Demo Held (SQO)",
    "96256085": "Onboarded (SQO)",
    "998696192": "Negotiation (SQO)",
    "closedwon": "Closed Won",
    "closedlost": "Closed Lost",
}

STAGE_ORDER = [
    "Demo Scheduled (SQL)",
    "Demo Held (SQO)",
    "Onboarded (SQO)",
    "Negotiation (SQO)",
    "Closed Won",
    "Closed Lost",
]

# For funnel: only forward stages (exclude Closed Lost)
FUNNEL_STAGES = [
    "Demo Scheduled (SQL)",
    "Demo Held (SQO)",
    "Onboarded (SQO)",
    "Negotiation (SQO)",
    "Closed Won",
]

DEALTYPE_MAP = {
    "Outbound Outreach": "Sales",
    "Partnership": "Partnerships",
    "PLS": "Marketing",
    "existingbusiness": "Customer",
    "Dataships Partner (partner pipe)": "Agency",
}

OWNER_MAP = {
    "53945653": "Michael Storan",
    "56659012": "Ryan McErlane",
    "76250718": "Christian Freitas",
    "78477603": "Jeff Prober",
    "78702499": "Rafael Iribarrem",
    "80739670": "Satru Rahmat",
    "81467379": "Derek Booth",
    "81966961": "Liam Fitter",
    "83152168": "Rayna Tyler",
    "85266780": "Chris Roberson",
    "85314689": "Tariq Ellahi",
    "86801135": "Maria Turner",
    "87679132": "Matt Howard",
    "87679133": "Zach Faerber",
    "87709163": "Dess Everhart",
    "145194751": "Matthew Gottron",
    "1018045949": "Tyrone Kane",
    "505060147": "Conor Mahony",
    "632110502": "Shane Getkate",
}

ACTIVE_OWNER_IDS = set(OWNER_MAP.keys())

# ============================================================
# SPEND DATA
# ============================================================
# Grace period: exclude spend from the last N days when computing CAC/ROI.
# Deals take ~33 days median to close (won deals), P75 ~57 days.
# Using 60-day window so recently-deployed spend doesn't inflate CAC before
# deals have had time to convert.
SPEND_MATURITY_DAYS = 60

# Monthly spend by program. LinkedIn + Vouchers grouped (2025), LinkedIn + Tremendous grouped (2026).
# Contractors, Swag/Gift, Experiments excluded. Where no data, omit (= N/A).

# 2025 monthly spend: {month: {program: amount}}
SPEND_2025 = {
    "2025-01": {"LinkedIn": 4006.43, "Vouchers": 0, "Meta": 0, "Events": 0, "GROW": 0, "Landmark": 0, "DTConnect": 0},
    "2025-02": {"LinkedIn": 4533.13, "Vouchers": 650, "Meta": 0, "Events": 0, "GROW": 0, "Landmark": 0, "DTConnect": 0},
    "2025-03": {"LinkedIn": 4352.67, "Vouchers": 1600, "Meta": 0, "Events": 28225, "GROW": 0, "Landmark": 0, "DTConnect": 0},
    "2025-04": {"LinkedIn": 7489.22, "Vouchers": 1950, "Meta": 0, "Events": 0, "GROW": 2000, "Landmark": 0, "DTConnect": 0},
    "2025-05": {"LinkedIn": 9394.56, "Vouchers": 1577.24, "Meta": 1017.48, "Events": 0, "GROW": 2000, "Landmark": 0, "DTConnect": 0},
    "2025-06": {"LinkedIn": 10351.72, "Vouchers": 1422, "Meta": 774.80, "Events": 0, "GROW": 0, "Landmark": 0, "DTConnect": 0},
    "2025-07": {"LinkedIn": 15734.51, "Vouchers": 1872, "Meta": 624.31, "Events": 15000, "GROW": 8500, "Landmark": 0, "DTConnect": 0},
    "2025-08": {"LinkedIn": 15033, "Vouchers": 2050, "Meta": 274.54, "Events": 27500, "GROW": 0, "Landmark": 0, "DTConnect": 0},
    "2025-09": {"LinkedIn": 15010, "Vouchers": 1900, "Meta": 0, "Events": 8375.50, "GROW": 0, "Landmark": 0, "DTConnect": 0},
    "2025-10": {"LinkedIn": 16408.30, "Vouchers": 2766, "Meta": 0, "Events": 5232, "GROW": 0, "Landmark": 6666, "DTConnect": 10000},
    "2025-11": {"LinkedIn": 16408.30, "Vouchers": 2766, "Meta": 0, "Events": 33304, "GROW": 0, "Landmark": 6666, "DTConnect": 10000},
    "2025-12": {"LinkedIn": 16408.30, "Vouchers": 2766, "Meta": 2000, "Events": 0, "GROW": 0, "Landmark": 0, "DTConnect": 20000},
}

# 2026 weekly spend (week ending date) — aggregate to monthly
# Jan 2026 weeks: 1/4, 1/11, 1/18, 1/25
# Feb 2026 weeks: 2/1, 2/8
SPEND_2026 = {
    "2026-01": {
        "LinkedIn": 2281.94 + 5090.18 + 3022.94 + 7687.06,  # weekly sums
        "Tremendous": 0 + 900 + 700 + 100,
        "Meta": 0 + 0 + 1237.88 + 581.96,
        "Events": 0 + 0 + 3350 + 0,
        "DTConnect": 0 + 9000 + 11000 + 30000,
        "Landmark": 0 + 0 + 7300 + 6666,
        "GROW": 0 + 0 + 0 + 0,
        "Matchmaking-other": 0 + 0 + 0 + 3000,
    },
    "2026-02": {
        "LinkedIn": 6280.53 + 9022.36,  # 2 weeks so far
        "Tremendous": 500 + 0,
        "Meta": 167 + 379.49,
        "Events": 20000 + 0,
        "DTConnect": 11000 + 12000,
        "Landmark": 0 + 316.67,
        "GROW": 0 + 0,
        "Matchmaking-other": 0 + 0,
    },
}

def get_monthly_spend():
    """
    Build a mapping of YYYY-MM -> {sub_category: spend_amount}.
    Maps spend programs to deal sub-categories.
    LinkedIn + Vouchers/Tremendous + Meta → Marketing-Paid-Campaign
    Events → Marketing-Events
    GROW → Marketing-GROW-Matchmaking
    DTConnect → Marketing-DTConnect-Matchmaking
    Landmark → Marketing-LMV-Matchmaking
    """
    result = {}

    for month, programs in SPEND_2025.items():
        paid_campaign = programs.get("LinkedIn", 0) + programs.get("Vouchers", 0) + programs.get("Meta", 0)
        month_spend = {}
        if paid_campaign > 0:
            month_spend["Marketing-Paid-Campaign"] = paid_campaign
        if programs.get("Events", 0) > 0:
            month_spend["Marketing-Events"] = programs["Events"]
        if programs.get("GROW", 0) > 0:
            month_spend["Marketing-GROW-Matchmaking"] = programs["GROW"]
        if programs.get("DTConnect", 0) > 0:
            month_spend["Marketing-DTConnect-Matchmaking"] = programs["DTConnect"]
        if programs.get("Landmark", 0) > 0:
            month_spend["Marketing-LMV-Matchmaking"] = programs["Landmark"]
        if month_spend:
            result[month] = month_spend

    for month, programs in SPEND_2026.items():
        paid_campaign = programs.get("LinkedIn", 0) + programs.get("Tremendous", 0) + programs.get("Meta", 0)
        month_spend = {}
        if paid_campaign > 0:
            month_spend["Marketing-Paid-Campaign"] = paid_campaign
        if programs.get("Events", 0) > 0:
            month_spend["Marketing-Events"] = programs["Events"]
        if programs.get("GROW", 0) > 0:
            month_spend["Marketing-GROW-Matchmaking"] = programs["GROW"]
        if programs.get("DTConnect", 0) > 0:
            month_spend["Marketing-DTConnect-Matchmaking"] = programs["DTConnect"]
        if programs.get("Landmark", 0) > 0:
            month_spend["Marketing-LMV-Matchmaking"] = programs["Landmark"]
        if month_spend:
            result[month] = month_spend

    return result


def compute_spend_metrics(deals, monthly_spend, maturity_days=SPEND_MATURITY_DAYS):
    """
    Compute spend metrics per sub-category (total spend, CAC, cost per SQL, ROI).
    Uses a maturity window: spend from the last `maturity_days` days is excluded from
    CAC/ROI calculations because deals haven't had time to close yet.

    Returns:
        result: dict of sub_category -> metrics (with both total and matured spend)
        monthly_totals: dict of month -> total spend (all months)
        matured_monthly_totals: dict of month -> total spend (matured months only)
    """
    from collections import defaultdict
    from datetime import timedelta

    # Determine the cutoff month: months AFTER this are "immature" (too recent)
    cutoff_date = datetime.now() - timedelta(days=maturity_days)
    cutoff_month = cutoff_date.strftime("%Y-%m")

    # Aggregate spend per sub-category: total (all time) and matured (before cutoff)
    total_spend_by_subcat = defaultdict(float)
    matured_spend_by_subcat = defaultdict(float)
    for month, subcats in monthly_spend.items():
        for sc, amount in subcats.items():
            total_spend_by_subcat[sc] += amount
            if month <= cutoff_month:
                matured_spend_by_subcat[sc] += amount

    # Compute deal metrics per sub-category
    by_subcat = defaultdict(list)
    for d in deals:
        by_subcat[d["sub_category"]].append(d)

    result = {}
    for sc, spend in total_spend_by_subcat.items():
        matured_spend = matured_spend_by_subcat.get(sc, 0)
        sc_deals = by_subcat.get(sc, [])
        total_deals = len(sc_deals)
        won = sum(1 for d in sc_deals if d["stage"] == "Closed Won")
        lost = sum(1 for d in sc_deals if d["stage"] == "Closed Lost")
        won_rev = sum(d["amount_for_revenue"] for d in sc_deals if d["stage"] == "Closed Won")
        win_rate = (won / (won + lost) * 100) if (won + lost) > 0 else None

        # Cost per SQL uses total spend (all-time investment per lead)
        cost_per_sql = (spend / total_deals) if total_deals > 0 else None

        # CAC and ROI use MATURED spend only (gives channels time to convert)
        cac = (matured_spend / won) if won > 0 and matured_spend > 0 else None
        arr_from_wins = won_rev * 12
        roi = ((arr_from_wins - matured_spend) / matured_spend * 100) if matured_spend > 0 else None

        result[sc] = {
            "total_spend": spend,
            "matured_spend": matured_spend,
            "total_deals": total_deals,
            "won": won,
            "lost": lost,
            "won_mrr": won_rev,
            "won_arr": arr_from_wins,
            "win_rate": win_rate,
            "cost_per_sql": cost_per_sql,
            "cac": cac,
            "roi": roi,
        }

    # Monthly spend totals (for cohort table) — both total and matured
    monthly_totals = {}
    matured_monthly_totals = {}
    for month, subcats in monthly_spend.items():
        month_total = sum(subcats.values())
        monthly_totals[month] = month_total
        if month <= cutoff_month:
            matured_monthly_totals[month] = month_total

    return result, monthly_totals, matured_monthly_totals


# Raw API result files — v2 with stage entry dates (hs_v2_date_entered_*)
# Resolve paths relative to this script's directory
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

RAW_FILES_V2 = [
    os.path.join(_SCRIPT_DIR, "data", "deals_batch_1.json"),
    os.path.join(_SCRIPT_DIR, "data", "deals_batch_2.json"),
    os.path.join(_SCRIPT_DIR, "data", "deals_batch_3.json"),
    os.path.join(_SCRIPT_DIR, "data", "deals_batch_4.json"),
]

OUTPUT_HTML = os.path.join(_SCRIPT_DIR, "dataships_conversion_dashboard.html")


def parse_api_file(filepath):
    """Parse a raw HubSpot API response file (JSON array wrapper with text field)."""
    try:
        with open(filepath, "r") as f:
            raw = json.load(f)

        # The file is a JSON array with one object that has a "text" field containing the actual JSON
        if isinstance(raw, list) and len(raw) > 0:
            text_content = raw[0].get("text", "")
            if isinstance(text_content, str):
                data = json.loads(text_content)
            else:
                data = text_content
        elif isinstance(raw, dict):
            data = raw
        else:
            return []

        return data.get("results", [])
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return []


def process_deal(raw_deal):
    """Convert a raw HubSpot deal record into our clean format."""
    props = raw_deal.get("properties", {})

    stage_raw = props.get("dealstage", "")
    stage = STAGE_MAP.get(stage_raw, stage_raw)

    dealtype_raw = props.get("dealtype", "")
    dealtype = DEALTYPE_MAP.get(dealtype_raw, dealtype_raw or "Unknown")

    sub_cat = props.get("deal_type___sub_category", "") or "Unknown"

    # Rename sub-categories
    SUB_CAT_RENAME = {
        "Marketing-Free-trial": "Marketing-Inbound",
        "Marketing-Free-Trial": "Marketing-Inbound",
    }
    sub_cat = SUB_CAT_RENAME.get(sub_cat, sub_cat)

    owner_id = props.get("hubspot_owner_id", "")
    owner_name = OWNER_MAP.get(str(owner_id), "Other/Inactive")
    is_active_owner = str(owner_id) in ACTIVE_OWNER_IDS

    amount_raw = props.get("amount", "")
    try:
        amount = float(amount_raw) if amount_raw else 0
    except (ValueError, TypeError):
        amount = 0

    # Treat $0.10 placeholder amounts as $0 for revenue calculations
    if amount <= 0.1:
        amount_for_revenue = 0
    else:
        amount_for_revenue = amount

    createdate = props.get("createdate", "")
    closedate = props.get("closedate", "")
    is_closed = int(props.get("hs_is_closed_count", "0") or "0")

    # Create month cohort from createdate
    create_month = ""
    if createdate:
        try:
            dt = datetime.fromisoformat(createdate.replace("Z", "+00:00"))
            create_month = dt.strftime("%Y-%m")
        except:
            pass

    # Compute days to close for closed deals
    days_to_close = None
    if is_closed and createdate and closedate:
        try:
            dt_create = datetime.fromisoformat(createdate.replace("Z", "+00:00"))
            dt_close = datetime.fromisoformat(closedate.replace("Z", "+00:00"))
            days_to_close = max(0, (dt_close - dt_create).total_seconds() / 86400)
        except:
            pass

    # Stage entry dates — tells us which stages a deal actually passed through
    stage_entry_dates = {
        "Demo Scheduled (SQL)": props.get("hs_v2_date_entered_qualifiedtobuy"),
        "Demo Held (SQO)": props.get("hs_v2_date_entered_presentationscheduled"),
        "Onboarded (SQO)": props.get("hs_v2_date_entered_96256085"),
        "Negotiation (SQO)": props.get("hs_v2_date_entered_998696192"),
        "Closed Won": props.get("hs_v2_date_entered_closedwon"),
        "Closed Lost": props.get("hs_v2_date_entered_closedlost"),
    }
    # Build set of stages this deal actually entered
    stages_entered = set()
    for stage_name, date_val in stage_entry_dates.items():
        if date_val:
            stages_entered.add(stage_name)

    return {
        "id": props.get("hs_object_id", raw_deal.get("id", "")),
        "stage": stage,
        "stage_raw": stage_raw,
        "dealtype": dealtype,
        "sub_category": sub_cat,
        "owner_id": str(owner_id),
        "owner_name": owner_name,
        "is_active_owner": is_active_owner,
        "amount": amount,
        "amount_for_revenue": amount_for_revenue,
        "createdate": createdate,
        "closedate": closedate,
        "is_closed": is_closed,
        "create_month": create_month,
        "days_to_close": days_to_close,
        "stages_entered": stages_entered,
    }


def stage_index(stage_name):
    """Return numeric index for stage ordering."""
    try:
        return FUNNEL_STAGES.index(stage_name)
    except ValueError:
        if stage_name == "Closed Lost":
            return -1  # Lost deals
        return -2


def reached_stage(deal, target_stage):
    """
    Determine if a deal has reached at least the target stage.
    Uses hs_v2_date_entered_* stage entry dates for accurate tracking —
    especially critical for Closed Lost deals where we now know exactly
    which stages they passed through before going cold.
    """
    stages_entered = deal.get("stages_entered", set())

    # If we have stage entry data, use it directly
    if stages_entered:
        return target_stage in stages_entered

    # Fallback for deals without stage entry dates (e.g. legacy data)
    target_idx = stage_index(target_stage)
    current_stage = deal["stage"]

    if current_stage == "Closed Won":
        return True

    if current_stage == "Closed Lost":
        return target_idx == 0

    current_idx = stage_index(current_stage)
    return current_idx >= target_idx


def compute_funnel(deals):
    """
    Compute funnel conversion rates.
    Returns list of dicts with stage, count, revenue, conversion rates.
    """
    total = len(deals)
    if total == 0:
        return []

    total_revenue = sum(d["amount_for_revenue"] for d in deals)

    results = []
    for i, stage in enumerate(FUNNEL_STAGES):
        count = sum(1 for d in deals if reached_stage(d, stage))
        revenue = sum(d["amount_for_revenue"] for d in deals if reached_stage(d, stage))

        # Conversion from top of funnel
        conv_from_top = (count / total * 100) if total > 0 else 0
        rev_conv_from_top = (revenue / total_revenue * 100) if total_revenue > 0 else 0

        # Stage-to-stage conversion
        if i == 0:
            conv_stage = 100.0
            rev_conv_stage = 100.0
        else:
            prev_stage = FUNNEL_STAGES[i - 1]
            prev_count = sum(1 for d in deals if reached_stage(d, prev_stage))
            prev_revenue = sum(d["amount_for_revenue"] for d in deals if reached_stage(d, prev_stage))
            conv_stage = (count / prev_count * 100) if prev_count > 0 else 0
            rev_conv_stage = (revenue / prev_revenue * 100) if prev_revenue > 0 else 0

        results.append({
            "stage": stage,
            "count": count,
            "revenue": revenue,
            "conv_from_top": conv_from_top,
            "conv_stage_to_stage": conv_stage,
            "rev_conv_from_top": rev_conv_from_top,
            "rev_conv_stage_to_stage": rev_conv_stage,
        })

    # Add closed lost info
    lost_count = sum(1 for d in deals if d["stage"] == "Closed Lost")
    lost_revenue = sum(d["amount_for_revenue"] for d in deals if d["stage"] == "Closed Lost")
    results.append({
        "stage": "Closed Lost",
        "count": lost_count,
        "revenue": lost_revenue,
        "conv_from_top": (lost_count / total * 100) if total > 0 else 0,
        "conv_stage_to_stage": 0,
        "rev_conv_from_top": (lost_revenue / total_revenue * 100) if total_revenue > 0 else 0,
        "rev_conv_stage_to_stage": 0,
    })

    # Add "Still Open" (not closed won or lost)
    open_count = sum(1 for d in deals if d["stage"] not in ("Closed Won", "Closed Lost"))
    open_revenue = sum(d["amount_for_revenue"] for d in deals if d["stage"] not in ("Closed Won", "Closed Lost"))
    results.append({
        "stage": "Still Open",
        "count": open_count,
        "revenue": open_revenue,
        "conv_from_top": (open_count / total * 100) if total > 0 else 0,
        "conv_stage_to_stage": 0,
        "rev_conv_from_top": (open_revenue / total_revenue * 100) if total_revenue > 0 else 0,
        "rev_conv_stage_to_stage": 0,
    })

    return results


def compute_cohort_analysis(deals):
    """
    Group deals by create_month, then compute funnel for each cohort.
    Returns OrderedDict of month -> funnel data.
    """
    cohorts = defaultdict(list)
    for d in deals:
        if d["create_month"]:
            cohorts[d["create_month"]].append(d)

    # Sort by month
    sorted_months = sorted(cohorts.keys())
    result = OrderedDict()
    for month in sorted_months:
        cohort_deals = cohorts[month]
        funnel = compute_funnel(cohort_deals)

        won_count = sum(1 for d in cohort_deals if d["stage"] == "Closed Won")
        lost_count = sum(1 for d in cohort_deals if d["stage"] == "Closed Lost")
        open_count = sum(1 for d in cohort_deals if d["stage"] not in ("Closed Won", "Closed Lost"))
        total_rev = sum(d["amount_for_revenue"] for d in cohort_deals)
        won_rev = sum(d["amount_for_revenue"] for d in cohort_deals if d["stage"] == "Closed Won")

        result[month] = {
            "total": len(cohort_deals),
            "won": won_count,
            "lost": lost_count,
            "open": open_count,
            "total_revenue": total_rev,
            "won_revenue": won_rev,
            "win_rate_volume": (won_count / (won_count + lost_count) * 100) if (won_count + lost_count) > 0 else None,
            "win_rate_revenue": (won_rev / total_rev * 100) if total_rev > 0 else None,
            "funnel": funnel,
            "pct_resolved": ((won_count + lost_count) / len(cohort_deals) * 100) if len(cohort_deals) > 0 else 0,
        }

    return result


def format_currency(val):
    if val >= 1000000:
        return f"${val/1000000:,.1f}M"
    elif val >= 1000:
        return f"${val/1000:,.1f}K"
    else:
        return f"${val:,.0f}"


def format_pct(val):
    if val is None:
        return "—"
    return f"{val:.1f}%"


# ============================================================
# MAIN
# ============================================================

def main():
    print("Loading deal data from raw API files...")

    all_raw_deals = []
    seen_ids = set()

    # Load from v2 raw API files (with stage entry dates)
    for filepath in RAW_FILES_V2:
        if os.path.exists(filepath):
            deals = parse_api_file(filepath)
            print(f"  Loaded {len(deals)} deals from {os.path.basename(filepath)}")
            all_raw_deals.extend(deals)
        else:
            print(f"  MISSING: {filepath}")

    print(f"\nTotal raw records loaded: {len(all_raw_deals)}")

    # Process and deduplicate
    all_deals = []
    for raw in all_raw_deals:
        deal = process_deal(raw)
        deal_id = str(deal["id"])
        if deal_id not in seen_ids:
            seen_ids.add(deal_id)
            all_deals.append(deal)

    print(f"Unique deals after dedup: {len(all_deals)}")

    # Filter to Jan 2025+ created only
    deals = [d for d in all_deals if d["create_month"] >= "2025-01"]
    print(f"Deals created Jan 2025+: {len(deals)}")

    if not deals:
        print("ERROR: No deals found! Check file paths.")
        sys.exit(1)

    # ============================================================
    # COMPUTE ALL ANALYTICS
    # ============================================================

    # 1. Overall funnel
    overall_funnel = compute_funnel(deals)
    total_deals = len(deals)
    total_revenue = sum(d["amount_for_revenue"] for d in deals)
    won_deals = [d for d in deals if d["stage"] == "Closed Won"]
    lost_deals = [d for d in deals if d["stage"] == "Closed Lost"]
    open_deals = [d for d in deals if d["stage"] not in ("Closed Won", "Closed Lost")]

    # 2. By Deal Type
    by_dealtype = defaultdict(list)
    for d in deals:
        by_dealtype[d["dealtype"]].append(d)
    dealtype_funnels = {dt: compute_funnel(dl) for dt, dl in sorted(by_dealtype.items())}

    # 3. By Sub-Category
    by_subcat = defaultdict(list)
    for d in deals:
        by_subcat[d["sub_category"]].append(d)
    subcat_funnels = {sc: compute_funnel(dl) for sc, dl in sorted(by_subcat.items())}

    # 4. By AE (active only, exclude non-AE roles)
    AE_EXCLUDE = {"Matthew Gottron", "Shane Getkate", "Other/Inactive"}
    by_ae = defaultdict(list)
    for d in deals:
        if d["is_active_owner"]:
            by_ae[d["owner_name"]].append(d)
        else:
            by_ae["Other/Inactive"].append(d)
    ae_funnels = {ae: compute_funnel(dl) for ae, dl in sorted(by_ae.items()) if ae not in AE_EXCLUDE}

    # 4b. Last quarter AE stats (Q4 2025 = Oct-Dec 2025)
    # Determine "last quarter" dynamically: the most recent fully completed quarter
    now = datetime.now()
    current_quarter = (now.month - 1) // 3 + 1
    current_year = now.year
    # Go back one quarter
    if current_quarter == 1:
        lq_year = current_year - 1
        lq_q = 4
    else:
        lq_year = current_year
        lq_q = current_quarter - 1
    lq_start_month = (lq_q - 1) * 3 + 1
    lq_months = [f"{lq_year}-{m:02d}" for m in range(lq_start_month, lq_start_month + 3)]
    lq_label = f"Q{lq_q} {lq_year}"

    # Filter deals to last quarter by create_month
    lq_deals = [d for d in deals if d["create_month"] in lq_months]
    by_ae_lq = defaultdict(list)
    for d in lq_deals:
        if d["is_active_owner"]:
            by_ae_lq[d["owner_name"]].append(d)
        else:
            by_ae_lq["Other/Inactive"].append(d)

    ae_lq_stats = {}
    for ae_name in ae_funnels.keys():
        ae_lq_deals = by_ae_lq.get(ae_name, [])
        won_lq = sum(1 for d in ae_lq_deals if d["stage"] == "Closed Won")
        lost_lq = sum(1 for d in ae_lq_deals if d["stage"] == "Closed Lost")
        total_lq = len(ae_lq_deals)
        open_lq = total_lq - won_lq - lost_lq
        wr_lq = (won_lq / (won_lq + lost_lq) * 100) if (won_lq + lost_lq) > 0 else None
        won_rev_lq = sum(d["amount_for_revenue"] for d in ae_lq_deals if d["stage"] == "Closed Won")
        ae_lq_stats[ae_name] = {
            "total": total_lq,
            "won": won_lq,
            "lost": lost_lq,
            "open": open_lq,
            "win_rate": wr_lq,
            "won_revenue": won_rev_lq,
        }

    # 5. Cohort analysis
    cohort_data = compute_cohort_analysis(deals)

    # 5b. Spend / CAC / ROI analysis
    monthly_spend = get_monthly_spend()
    spend_metrics, monthly_spend_totals, matured_monthly_totals = compute_spend_metrics(deals, monthly_spend)

    # 6. Stage distribution summary
    stage_dist = defaultdict(int)
    stage_rev = defaultdict(float)
    for d in deals:
        stage_dist[d["stage"]] += 1
        stage_rev[d["stage"]] += d["amount_for_revenue"]

    # 7. Time-to-close analytics
    import statistics

    def ttc_stats(deal_list):
        """Compute time-to-close statistics for a list of deals."""
        days = [d["days_to_close"] for d in deal_list if d["days_to_close"] is not None]
        if not days:
            return {"count": 0, "avg": None, "median": None, "p25": None, "p75": None, "min": None, "max": None}
        days_sorted = sorted(days)
        n = len(days_sorted)
        return {
            "count": n,
            "avg": statistics.mean(days),
            "median": statistics.median(days),
            "p25": days_sorted[n // 4] if n >= 4 else days_sorted[0],
            "p75": days_sorted[(3 * n) // 4] if n >= 4 else days_sorted[-1],
            "min": min(days),
            "max": max(days),
        }

    ttc_won = ttc_stats(won_deals)
    ttc_lost = ttc_stats(lost_deals)

    # TTC by deal type
    ttc_by_dealtype = {}
    for dt, dl in by_dealtype.items():
        won_in_type = [d for d in dl if d["stage"] == "Closed Won"]
        lost_in_type = [d for d in dl if d["stage"] == "Closed Lost"]
        ttc_by_dealtype[dt] = {
            "won": ttc_stats(won_in_type),
            "lost": ttc_stats(lost_in_type),
            "all_closed": ttc_stats(won_in_type + lost_in_type),
        }

    # TTC by AE (filtered — exclude non-AE roles)
    ttc_by_ae = {}
    for ae, dl in by_ae.items():
        if ae in AE_EXCLUDE:
            continue
        won_in_ae = [d for d in dl if d["stage"] == "Closed Won"]
        lost_in_ae = [d for d in dl if d["stage"] == "Closed Lost"]
        ttc_by_ae[ae] = {
            "won": ttc_stats(won_in_ae),
            "lost": ttc_stats(lost_in_ae),
            "all_closed": ttc_stats(won_in_ae + lost_in_ae),
        }

    # Speed buckets analysis: do faster deals win more?
    closed_deals = [d for d in deals if d["days_to_close"] is not None]
    speed_buckets = [
        ("0-7 days", 0, 7),
        ("8-14 days", 8, 14),
        ("15-30 days", 15, 30),
        ("31-60 days", 31, 60),
        ("61-90 days", 61, 90),
        ("90+ days", 91, 9999),
    ]
    speed_analysis = []
    for label, lo, hi in speed_buckets:
        bucket = [d for d in closed_deals if lo <= d["days_to_close"] <= hi]
        won_b = sum(1 for d in bucket if d["stage"] == "Closed Won")
        lost_b = sum(1 for d in bucket if d["stage"] == "Closed Lost")
        total_b = won_b + lost_b
        wr = (won_b / total_b * 100) if total_b > 0 else None
        rev_won = sum(d["amount_for_revenue"] for d in bucket if d["stage"] == "Closed Won")
        rev_total = sum(d["amount_for_revenue"] for d in bucket)
        speed_analysis.append({
            "label": label,
            "total": total_b,
            "won": won_b,
            "lost": lost_b,
            "win_rate": wr,
            "rev_won": rev_won,
            "rev_total": rev_total,
        })

    # TTC by cohort month
    ttc_by_cohort = {}
    for month, cdata in cohort_data.items():
        cohort_deals_list = [d for d in deals if d["create_month"] == month]
        won_in_cohort = [d for d in cohort_deals_list if d["stage"] == "Closed Won"]
        lost_in_cohort = [d for d in cohort_deals_list if d["stage"] == "Closed Lost"]
        ttc_by_cohort[month] = {
            "won": ttc_stats(won_in_cohort),
            "lost": ttc_stats(lost_in_cohort),
        }

    # ============================================================
    # BUILD HTML
    # ============================================================

    print("\nBuilding HTML dashboard...")

    # Helper to build a funnel table HTML
    def funnel_table_html(funnel_data, total_count, total_rev, show_stage_conv=True):
        rows = ""
        for f in funnel_data:
            stage = f["stage"]
            if stage in ("Still Open", "Closed Lost"):
                css_class = "info-row" if stage == "Still Open" else "lost-row"
                rows += f"""<tr class="{css_class}">
                    <td>{stage}</td>
                    <td>{f['count']:,}</td>
                    <td>{format_pct(f['conv_from_top'])}</td>
                    <td>—</td>
                    <td>{format_currency(f['revenue'])}</td>
                    <td>{format_pct(f['rev_conv_from_top'])}</td>
                    <td>—</td>
                </tr>"""
            else:
                rows += f"""<tr>
                    <td><strong>{stage}</strong></td>
                    <td>{f['count']:,}</td>
                    <td>{format_pct(f['conv_from_top'])}</td>
                    <td>{format_pct(f['conv_stage_to_stage'])}</td>
                    <td>{format_currency(f['revenue'])}</td>
                    <td>{format_pct(f['rev_conv_from_top'])}</td>
                    <td>{format_pct(f['rev_conv_stage_to_stage'])}</td>
                </tr>"""

        return f"""<table class="data-table">
            <thead>
                <tr>
                    <th>Stage</th>
                    <th>Deals</th>
                    <th>% of Top</th>
                    <th>Stage→Stage</th>
                    <th>Pipeline $</th>
                    <th>% of Top $</th>
                    <th>Stage→Stage $</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>"""

    # Build comparison table for deal types / AEs
    def comparison_table_html(funnels_dict, label="Segment", spend_data=None):
        """Build a compact comparison table showing key metrics across segments.
        If spend_data is provided, adds Spend, CAC, and ROI columns."""
        has_spend = spend_data is not None
        rows = ""
        for name, funnel in sorted(funnels_dict.items(), key=lambda x: -len([d for f in x[1] for d in [f] if f["stage"] == "Demo Scheduled (SQL)"])):
            total = 0
            won = 0
            won_rev = 0
            total_rev = 0
            demo_held = 0
            onboarded = 0
            negotiation = 0
            lost = 0

            for f in funnel:
                if f["stage"] == "Demo Scheduled (SQL)":
                    total = f["count"]
                    total_rev = f["revenue"]
                elif f["stage"] == "Demo Held (SQO)":
                    demo_held = f["count"]
                elif f["stage"] == "Onboarded (SQO)":
                    onboarded = f["count"]
                elif f["stage"] == "Negotiation (SQO)":
                    negotiation = f["count"]
                elif f["stage"] == "Closed Won":
                    won = f["count"]
                    won_rev = f["revenue"]
                elif f["stage"] == "Closed Lost":
                    lost = f["count"]

            win_rate = (won / (won + lost) * 100) if (won + lost) > 0 else None
            sql_to_won = (won / total * 100) if total > 0 else 0
            rev_conv = (won_rev / total_rev * 100) if total_rev > 0 else 0

            spend_cells = ""
            if has_spend:
                sm = spend_data.get(name)
                if sm:
                    spend_cells += f"<td>{format_currency(sm['total_spend'])}</td>"
                    spend_cells += f"<td>{format_currency(sm['matured_spend'])}</td>"
                    spend_cells += f"<td>{format_currency(sm['cost_per_sql']) if sm['cost_per_sql'] else '—'}</td>"
                    spend_cells += f"<td>{format_currency(sm['cac']) if sm['cac'] else '—'}</td>"
                    roi_val = sm['roi']
                    if roi_val is not None:
                        roi_class = "good" if roi_val > 100 else "warn" if roi_val > 0 else "bad"
                        spend_cells += f'<td class="{roi_class}">{roi_val:+.0f}%</td>'
                    else:
                        spend_cells += "<td>—</td>"
                else:
                    spend_cells += "<td class='na-cell'>N/A</td>" * 5

            rows += f"""<tr>
                <td><strong>{name}</strong></td>
                <td>{total:,}</td>
                <td>{format_pct((demo_held/total*100) if total > 0 else 0)}</td>
                <td>{format_pct((onboarded/total*100) if total > 0 else 0)}</td>
                <td>{format_pct((negotiation/total*100) if total > 0 else 0)}</td>
                <td>{won:,}</td>
                <td>{lost:,}</td>
                <td class="{'good' if win_rate and win_rate > 30 else 'warn' if win_rate and win_rate > 15 else 'bad'}">{format_pct(win_rate)}</td>
                <td>{format_pct(sql_to_won)}</td>
                <td>{format_currency(total_rev)}</td>
                <td>{format_currency(won_rev)}</td>
                <td>{format_pct(rev_conv)}</td>
                {spend_cells}
            </tr>"""

        spend_headers = ""
        if has_spend:
            spend_headers = f"""
                    <th>Total<br>Spend</th>
                    <th>Matured<br>Spend</th>
                    <th>Cost per<br>SQL</th>
                    <th>CAC<br>({SPEND_MATURITY_DAYS}d)</th>
                    <th>ROI<br>({SPEND_MATURITY_DAYS}d)</th>"""

        return f"""<table class="data-table compact">
            <thead>
                <tr>
                    <th>{label}</th>
                    <th>Total<br>Deals</th>
                    <th>→Demo<br>Held</th>
                    <th>→Onboard</th>
                    <th>→Negot.</th>
                    <th>Won</th>
                    <th>Lost</th>
                    <th>Win Rate<br>(Closed)</th>
                    <th>SQL→Won<br>(All)</th>
                    <th>Pipeline $</th>
                    <th>Won $<br>(MRR)</th>
                    <th>Rev Conv</th>
                    {spend_headers}
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>"""

    # Cohort table
    def cohort_table_html(cohort_data, monthly_spend_totals=None, matured_monthly_totals=None):
        has_spend = monthly_spend_totals is not None
        rows = ""
        for month, data in cohort_data.items():
            # Format month nicely
            try:
                dt = datetime.strptime(month, "%Y-%m")
                month_label = dt.strftime("%b %Y")
            except:
                month_label = month

            pct_resolved = data["pct_resolved"]
            maturity_class = "mature" if pct_resolved > 70 else "maturing" if pct_resolved > 40 else "immature"

            # Get funnel stage counts
            funnel = data["funnel"]
            demo_held_pct = 0
            onboarded_pct = 0
            neg_pct = 0

            for f in funnel:
                if f["stage"] == "Demo Held (SQO)":
                    demo_held_pct = f["conv_from_top"]
                elif f["stage"] == "Onboarded (SQO)":
                    onboarded_pct = f["conv_from_top"]
                elif f["stage"] == "Negotiation (SQO)":
                    neg_pct = f["conv_from_top"]

            spend_cell = ""
            cac_cell = ""
            if has_spend:
                month_spend = monthly_spend_totals.get(month)
                is_matured = matured_monthly_totals is not None and month in matured_monthly_totals
                if month_spend is not None and month_spend > 0:
                    spend_cell = f"<td>{format_currency(month_spend)}</td>"
                    # CAC uses matured spend only — if month is too recent, show "pending"
                    if not is_matured:
                        cac_cell = "<td class='na-cell' title='Spend too recent — within grace window'>pending</td>"
                    elif data['won'] > 0:
                        cohort_cac = month_spend / data['won']
                        cac_cell = f"<td>{format_currency(cohort_cac)}</td>"
                    else:
                        cac_cell = "<td>—</td>"
                else:
                    spend_cell = "<td class='na-cell'>N/A</td>"
                    cac_cell = "<td class='na-cell'>N/A</td>"

            rows += f"""<tr class="{maturity_class}">
                <td><strong>{month_label}</strong></td>
                <td>{data['total']:,}</td>
                <td>{format_pct(demo_held_pct)}</td>
                <td>{format_pct(onboarded_pct)}</td>
                <td>{format_pct(neg_pct)}</td>
                <td>{data['won']:,}</td>
                <td>{data['lost']:,}</td>
                <td>{data['open']:,}</td>
                <td>{format_pct(data['pct_resolved'])}</td>
                <td>{format_pct(data['win_rate_volume'])}</td>
                <td>{format_currency(data['total_revenue'])}</td>
                <td>{format_currency(data['won_revenue'])}</td>
                <td>{format_pct(data['win_rate_revenue'])}</td>
                {spend_cell}
                {cac_cell}
            </tr>"""

        spend_headers = ""
        if has_spend:
            spend_headers = """
                    <th>Mktg<br>Spend</th>
                    <th>Cohort<br>CAC</th>"""

        return f"""<table class="data-table cohort">
            <thead>
                <tr>
                    <th>Cohort</th>
                    <th>Created</th>
                    <th>→Demo<br>Held</th>
                    <th>→Onboard</th>
                    <th>→Negot.</th>
                    <th>Won</th>
                    <th>Lost</th>
                    <th>Open</th>
                    <th>%&nbsp;Resolved</th>
                    <th>Win Rate<br>(Vol)</th>
                    <th>Pipeline $</th>
                    <th>Won $</th>
                    <th>Win Rate<br>(Rev)</th>
                    {spend_headers}
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>"""

    # Compute some headline metrics
    won_count = len(won_deals)
    lost_count = len(lost_deals)
    open_count = len(open_deals)
    win_rate_closed = (won_count / (won_count + lost_count) * 100) if (won_count + lost_count) > 0 else 0
    won_revenue = sum(d["amount_for_revenue"] for d in won_deals)
    avg_deal_size_won = (won_revenue / won_count) if won_count > 0 else 0

    # Mature cohorts only (>70% resolved) for "true" win rate
    mature_cohorts = {m: d for m, d in cohort_data.items() if d["pct_resolved"] > 70}
    mature_won = sum(d["won"] for d in mature_cohorts.values())
    mature_lost = sum(d["lost"] for d in mature_cohorts.values())
    mature_win_rate = (mature_won / (mature_won + mature_lost) * 100) if (mature_won + mature_lost) > 0 else 0
    mature_won_rev = sum(d["won_revenue"] for d in mature_cohorts.values())
    mature_total_rev = sum(d["total_revenue"] for d in mature_cohorts.values())
    mature_rev_rate = (mature_won_rev / mature_total_rev * 100) if mature_total_rev > 0 else 0
    mature_months = ", ".join(sorted(mature_cohorts.keys())) if mature_cohorts else "N/A"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dataships Sales Pipeline — Conversion Rate Dashboard</title>
    <style>
        :root {{
            --bg: #0f1117;
            --card: #1a1d27;
            --border: #2a2d3a;
            --text: #e4e4e7;
            --text-muted: #9ca3af;
            --accent: #6366f1;
            --accent-light: #818cf8;
            --green: #22c55e;
            --green-bg: rgba(34,197,94,0.1);
            --red: #ef4444;
            --red-bg: rgba(239,68,68,0.1);
            --yellow: #eab308;
            --yellow-bg: rgba(234,179,8,0.1);
            --blue: #3b82f6;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 24px;
        }}

        .header {{
            text-align: center;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
        }}

        .header h1 {{
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 8px;
            background: linear-gradient(135deg, var(--accent-light), var(--blue));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .header .subtitle {{
            color: var(--text-muted);
            font-size: 14px;
        }}

        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}

        .kpi-card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }}

        .kpi-card .kpi-value {{
            font-size: 32px;
            font-weight: 700;
            color: var(--accent-light);
        }}

        .kpi-card .kpi-value.green {{ color: var(--green); }}
        .kpi-card .kpi-value.red {{ color: var(--red); }}
        .kpi-card .kpi-value.yellow {{ color: var(--yellow); }}

        .kpi-card .kpi-label {{
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 4px;
        }}

        .kpi-card .kpi-detail {{
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 2px;
        }}

        .section {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
        }}

        .section h2 {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 4px;
            color: var(--text);
        }}

        .section .section-desc {{
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 16px;
        }}

        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}

        .data-table th {{
            background: rgba(99,102,241,0.1);
            color: var(--accent-light);
            font-weight: 600;
            text-align: left;
            padding: 10px 12px;
            border-bottom: 2px solid var(--border);
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}

        .data-table td {{
            padding: 8px 12px;
            border-bottom: 1px solid var(--border);
        }}

        .data-table tr:hover {{
            background: rgba(99,102,241,0.05);
        }}

        .data-table tr.lost-row {{
            background: var(--red-bg);
        }}

        .data-table tr.info-row {{
            background: rgba(59,130,246,0.08);
        }}

        .data-table .good {{ color: var(--green); font-weight: 600; }}
        .data-table .warn {{ color: var(--yellow); font-weight: 600; }}
        .data-table .bad {{ color: var(--red); font-weight: 600; }}

        .data-table.compact td {{ padding: 6px 8px; font-size: 12px; }}
        .data-table.compact th {{ padding: 8px; font-size: 10px; }}

        .data-table td.na-cell {{ color: var(--text-muted); font-style: italic; opacity: 0.6; }}

        .cohort tr.mature {{ }}
        .cohort tr.maturing {{ opacity: 0.85; }}
        .cohort tr.immature {{ opacity: 0.6; }}

        .legend {{
            display: flex;
            gap: 16px;
            margin-bottom: 12px;
            font-size: 12px;
            color: var(--text-muted);
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .legend-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }}

        .legend-dot.mature {{ background: var(--green); }}
        .legend-dot.maturing {{ background: var(--yellow); }}
        .legend-dot.immature {{ background: var(--text-muted); }}

        .callout {{
            background: rgba(99,102,241,0.08);
            border-left: 3px solid var(--accent);
            padding: 12px 16px;
            margin-bottom: 16px;
            border-radius: 0 8px 8px 0;
            font-size: 13px;
        }}

        .callout strong {{ color: var(--accent-light); }}

        .tab-container {{
            margin-bottom: 16px;
        }}

        .tab-buttons {{
            display: flex;
            gap: 4px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }}

        .tab-btn {{
            padding: 6px 16px;
            background: transparent;
            border: 1px solid var(--border);
            border-radius: 20px;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }}

        .tab-btn:hover {{ border-color: var(--accent); color: var(--text); }}
        .tab-btn.active {{ background: var(--accent); color: white; border-color: var(--accent); }}

        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}

        .funnel-bar {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
        }}

        .funnel-label {{
            width: 160px;
            font-size: 12px;
            font-weight: 500;
            text-align: right;
            padding-right: 12px;
        }}

        .funnel-track {{
            flex: 1;
            height: 32px;
            background: rgba(255,255,255,0.05);
            border-radius: 6px;
            overflow: hidden;
            position: relative;
        }}

        .funnel-fill {{
            height: 100%;
            border-radius: 6px;
            display: flex;
            align-items: center;
            padding-left: 8px;
            font-size: 11px;
            font-weight: 600;
            color: white;
            transition: width 0.5s ease;
        }}

        .funnel-fill.s0 {{ background: linear-gradient(90deg, #6366f1, #818cf8); }}
        .funnel-fill.s1 {{ background: linear-gradient(90deg, #3b82f6, #60a5fa); }}
        .funnel-fill.s2 {{ background: linear-gradient(90deg, #0ea5e9, #38bdf8); }}
        .funnel-fill.s3 {{ background: linear-gradient(90deg, #14b8a6, #2dd4bf); }}
        .funnel-fill.s4 {{ background: linear-gradient(90deg, #22c55e, #4ade80); }}

        .two-col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }}

        @media (max-width: 900px) {{
            .two-col {{ grid-template-columns: 1fr; }}
        }}

        .scroll-x {{
            overflow-x: auto;
        }}

        .footer {{
            text-align: center;
            padding: 24px;
            color: var(--text-muted);
            font-size: 12px;
        }}
    </style>
</head>
<body>

<div class="header">
    <h1>Dataships Sales Pipeline — Conversion Dashboard</h1>
    <div class="subtitle">
        {total_deals:,} deals created Jan 2025 – Feb 2026 &nbsp;|&nbsp;
        {format_currency(total_revenue)} total pipeline &nbsp;|&nbsp;
        Generated {datetime.now().strftime("%b %d, %Y")}
    </div>
</div>

<!-- KPI Cards -->
<div class="kpi-grid">
    <div class="kpi-card">
        <div class="kpi-value">{total_deals:,}</div>
        <div class="kpi-label">Total Deals</div>
        <div class="kpi-detail">Jan 2025 – present</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value green">{won_count:,}</div>
        <div class="kpi-label">Closed Won</div>
        <div class="kpi-detail">{format_currency(won_revenue)} revenue</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value red">{lost_count:,}</div>
        <div class="kpi-label">Closed Lost</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value">{open_count:,}</div>
        <div class="kpi-label">Still Open</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value yellow">{win_rate_closed:.1f}%</div>
        <div class="kpi-label">Win Rate (All Closed)</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value green">{mature_win_rate:.1f}%</div>
        <div class="kpi-label">Win Rate (Mature Cohorts)</div>
        <div class="kpi-detail">&gt;70% resolved</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value">{format_currency(avg_deal_size_won)}</div>
        <div class="kpi-label">Avg Won Deal Size</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value">{mature_rev_rate:.1f}%</div>
        <div class="kpi-label">Revenue Conv (Mature)</div>
        <div class="kpi-detail">Pipeline $ → Won $</div>
    </div>
</div>

<!-- Visual Funnel -->
<div class="section">
    <h2>Pipeline Funnel — Deal Volume</h2>
    <div class="section-desc">How many deals reached each stage (as % of total pipeline entry)</div>
    <div style="max-width: 800px;">
"""

    for i, f in enumerate(overall_funnel):
        if f["stage"] in ("Closed Lost", "Still Open"):
            continue
        width = f["conv_from_top"]
        html += f"""
        <div class="funnel-bar">
            <div class="funnel-label">{f['stage']}</div>
            <div class="funnel-track">
                <div class="funnel-fill s{i}" style="width: {max(width, 3)}%">
                    {f['count']:,} ({width:.1f}%)
                </div>
            </div>
        </div>"""

    html += """
    </div>
</div>

<!-- Overall Funnel Table -->
<div class="section">
    <h2>Overall Stage-to-Stage Conversion</h2>
    <div class="section-desc">
        Volume and revenue conversion at each pipeline stage. "% of Top" = cumulative from pipeline entry.
        "Stage→Stage" = conversion between consecutive stages.
    </div>
"""
    html += funnel_table_html(overall_funnel, total_deals, total_revenue)
    html += """
    <div class="callout" style="margin-top: 16px;">
        <strong>Reading this table:</strong> "% of Top" shows what fraction of ALL deals entering the pipeline reached each stage.
        "Stage→Stage" shows the conversion between consecutive stages (e.g., of deals that had a Demo Held, what % got Onboarded?).
        Revenue columns show the same but weighted by deal amount — so a $3K deal "counts more" than a $750 deal.
    </div>
</div>

<!-- By Deal Type -->
<div class="section">
    <h2>Conversion by Deal Type</h2>
    <div class="section-desc">Win rates and funnel progression compared across deal source types</div>
"""
    html += comparison_table_html(dealtype_funnels, "Deal Type")
    html += "</div>"

    # By Sub-Category (with spend data where available)
    html += f"""
<div class="section">
    <h2>Conversion by Deal Type — Sub-Category</h2>
    <div class="section-desc">Granular view by sub-category. Sorted by volume. Spend/CAC/ROI shown where data is available; N/A where not tracked.
    <br>Won $ is MRR. CAC and ROI use "matured spend" only (spend deployed &gt;{SPEND_MATURITY_DAYS} days ago) so recently-ramped channels aren't penalized. CAC = matured spend / customers won. ROI = (ARR &minus; matured spend) / matured spend.</div>
    <div class="scroll-x">
"""
    html += comparison_table_html(subcat_funnels, "Sub-Category", spend_data=spend_metrics)
    html += "</div></div>"

    # Channel Economics section (only for sub-categories with spend data)
    if spend_metrics:
        # Compute cutoff month for display
        from datetime import timedelta as _td
        _cutoff_date = datetime.now() - _td(days=SPEND_MATURITY_DAYS)
        _cutoff_month_label = _cutoff_date.strftime("%b %Y")

        spend_rows = ""
        for sc in sorted(spend_metrics.keys(), key=lambda x: -spend_metrics[x]["total_spend"]):
            sm = spend_metrics[sc]
            wr_class = "good" if sm["win_rate"] and sm["win_rate"] > 30 else "warn" if sm["win_rate"] and sm["win_rate"] > 15 else "bad"
            roi_class = "good" if sm["roi"] and sm["roi"] > 100 else "warn" if sm["roi"] and sm["roi"] > 0 else "bad" if sm["roi"] is not None else ""
            spend_rows += f"""<tr>
                <td><strong>{sc}</strong></td>
                <td>{format_currency(sm['total_spend'])}</td>
                <td>{format_currency(sm['matured_spend'])}</td>
                <td>{sm['total_deals']:,}</td>
                <td>{format_currency(sm['cost_per_sql']) if sm['cost_per_sql'] else '—'}</td>
                <td>{sm['won']:,}</td>
                <td class="{wr_class}">{format_pct(sm['win_rate'])}</td>
                <td>{format_currency(sm['cac']) if sm['cac'] else '—'}</td>
                <td>{format_currency(sm['won_mrr'])}</td>
                <td>{format_currency(sm['won_arr'])}</td>
                <td class="{roi_class}">{sm['roi']:+.0f}% </td>
            </tr>""" if sm['roi'] is not None else f"""<tr>
                <td><strong>{sc}</strong></td>
                <td>{format_currency(sm['total_spend'])}</td>
                <td>{format_currency(sm['matured_spend'])}</td>
                <td>{sm['total_deals']:,}</td>
                <td>{format_currency(sm['cost_per_sql']) if sm['cost_per_sql'] else '—'}</td>
                <td>{sm['won']:,}</td>
                <td class="{wr_class}">{format_pct(sm['win_rate'])}</td>
                <td>{format_currency(sm['cac']) if sm['cac'] else '—'}</td>
                <td>{format_currency(sm['won_mrr'])}</td>
                <td>{format_currency(sm['won_arr'])}</td>
                <td>—</td>
            </tr>"""

        # Total row
        total_spend_all = sum(sm["total_spend"] for sm in spend_metrics.values())
        matured_spend_all = sum(sm["matured_spend"] for sm in spend_metrics.values())
        total_deals_all = sum(sm["total_deals"] for sm in spend_metrics.values())
        total_won_all = sum(sm["won"] for sm in spend_metrics.values())
        total_mrr_all = sum(sm["won_mrr"] for sm in spend_metrics.values())
        total_arr_all = total_mrr_all * 12
        total_cac_all = (matured_spend_all / total_won_all) if total_won_all > 0 and matured_spend_all > 0 else None
        total_roi_all = ((total_arr_all - matured_spend_all) / matured_spend_all * 100) if matured_spend_all > 0 else None
        total_cost_per_sql = (total_spend_all / total_deals_all) if total_deals_all > 0 else None
        total_wr_won = total_won_all
        total_wr_lost = sum(sm["lost"] for sm in spend_metrics.values())
        total_wr = (total_wr_won / (total_wr_won + total_wr_lost) * 100) if (total_wr_won + total_wr_lost) > 0 else None

        spend_rows += f"""<tr style="border-top: 2px solid var(--accent); font-weight: 600;">
            <td><strong>TOTAL (tracked)</strong></td>
            <td>{format_currency(total_spend_all)}</td>
            <td>{format_currency(matured_spend_all)}</td>
            <td>{total_deals_all:,}</td>
            <td>{format_currency(total_cost_per_sql) if total_cost_per_sql else '—'}</td>
            <td>{total_won_all:,}</td>
            <td>{format_pct(total_wr)}</td>
            <td>{format_currency(total_cac_all) if total_cac_all else '—'}</td>
            <td>{format_currency(total_mrr_all)}</td>
            <td>{format_currency(total_arr_all)}</td>
            <td class="{'good' if total_roi_all and total_roi_all > 100 else 'warn' if total_roi_all and total_roi_all > 0 else 'bad'}">{total_roi_all:+.0f}%</td>
        </tr>"""

        html += f"""
<div class="section">
    <h2>Channel Economics — Spend, CAC & ROI</h2>
    <div class="section-desc">
        Marketing spend mapped to deal sub-categories. Won $ is MRR; ARR = MRR &times; 12.
        <br><strong>Matured Spend</strong> = spend deployed &gt;{SPEND_MATURITY_DAYS} days ago (through {_cutoff_month_label}). Recent spend is excluded from CAC/ROI because deals haven't had time to close.
        <br><strong>CAC</strong> = matured spend / customers won. <strong>ROI</strong> = (ARR from wins &minus; matured spend) / matured spend.
        <br>Only channels with tracked spend shown. Partnerships, Sales, and other channels without tracked spend are N/A in the sub-category table above.
    </div>
    <div class="scroll-x">
    <table class="data-table compact">
        <thead>
            <tr>
                <th>Channel</th>
                <th>Total<br>Spend</th>
                <th>Matured<br>Spend</th>
                <th>Deals<br>Created</th>
                <th>Cost per<br>SQL</th>
                <th>Won</th>
                <th>Win Rate</th>
                <th>CAC<br>({SPEND_MATURITY_DAYS}d)</th>
                <th>Won MRR</th>
                <th>Won ARR</th>
                <th>ROI<br>({SPEND_MATURITY_DAYS}d)</th>
            </tr>
        </thead>
        <tbody>{spend_rows}</tbody>
    </table>
    </div>
    <div class="callout" style="margin-top: 16px;">
        <strong>How to read this table:</strong> CAC and ROI use "matured spend" only &mdash; spend deployed &gt;{SPEND_MATURITY_DAYS} days ago (median won-deal cycle is ~33 days, P75 ~57 days).
        This prevents recently-deployed spend from inflating costs before deals have had time to close.
        <br>+100% ROI means you earned 2&times; what you spent (ARR basis, year 1).
        A positive ROI means the channel pays for itself in year 1; negative means it takes longer than 12 months to recoup.
        <br>LinkedIn+Vouchers/Tremendous+Meta are grouped as "Paid Campaign". Spend excludes contractors, swag, and experiments.
    </div>
</div>
"""

    # By AE — with last quarter column
    def ae_comparison_table_html(funnels_dict, lq_stats, lq_label, label="AE"):
        """Build AE comparison table with an extra last-quarter win rate column."""
        rows = ""
        for name, funnel in sorted(funnels_dict.items(), key=lambda x: -len([d for f in x[1] for d in [f] if f["stage"] == "Demo Scheduled (SQL)"])):
            total = 0
            won = 0
            won_rev = 0
            total_rev = 0
            demo_held = 0
            onboarded = 0
            negotiation = 0
            lost = 0

            for f in funnel:
                if f["stage"] == "Demo Scheduled (SQL)":
                    total = f["count"]
                    total_rev = f["revenue"]
                elif f["stage"] == "Demo Held (SQO)":
                    demo_held = f["count"]
                elif f["stage"] == "Onboarded (SQO)":
                    onboarded = f["count"]
                elif f["stage"] == "Negotiation (SQO)":
                    negotiation = f["count"]
                elif f["stage"] == "Closed Won":
                    won = f["count"]
                    won_rev = f["revenue"]
                elif f["stage"] == "Closed Lost":
                    lost = f["count"]

            win_rate = (won / (won + lost) * 100) if (won + lost) > 0 else None
            sql_to_won = (won / total * 100) if total > 0 else 0
            rev_conv = (won_rev / total_rev * 100) if total_rev > 0 else 0

            # Last quarter stats
            lq = lq_stats.get(name, {"total": 0, "won": 0, "lost": 0, "open": 0, "win_rate": None, "won_revenue": 0})
            lq_wr = lq["win_rate"]
            lq_total = lq["total"]
            lq_won = lq["won"]
            lq_lost = lq["lost"]

            # Trend indicator: compare LQ win rate vs overall
            trend = ""
            if lq_wr is not None and win_rate is not None:
                diff = lq_wr - win_rate
                if diff > 5:
                    trend = " ↑"
                elif diff < -5:
                    trend = " ↓"

            lq_cell_class = "good" if lq_wr and lq_wr > 30 else "warn" if lq_wr and lq_wr > 15 else "bad" if lq_wr is not None else ""
            lq_display = format_pct(lq_wr) + trend if lq_wr is not None else "—"
            lq_detail = f"({lq_won}W/{lq_lost}L" + (f"/{lq['open']}O" if lq['open'] > 0 else "") + f" of {lq_total})" if lq_total > 0 else ""

            rows += f"""<tr>
                <td><strong>{name}</strong></td>
                <td>{total:,}</td>
                <td>{format_pct((demo_held/total*100) if total > 0 else 0)}</td>
                <td>{format_pct((onboarded/total*100) if total > 0 else 0)}</td>
                <td>{format_pct((negotiation/total*100) if total > 0 else 0)}</td>
                <td>{won:,}</td>
                <td>{lost:,}</td>
                <td class="{'good' if win_rate and win_rate > 30 else 'warn' if win_rate and win_rate > 15 else 'bad'}">{format_pct(win_rate)}</td>
                <td class="{lq_cell_class}" title="{lq_detail}">{lq_display}<br><span style="font-size:10px;opacity:0.7;">{lq_detail}</span></td>
                <td>{format_pct(sql_to_won)}</td>
                <td>{format_currency(total_rev)}</td>
                <td>{format_currency(won_rev)}</td>
                <td>{format_pct(rev_conv)}</td>
            </tr>"""

        return f"""<table class="data-table compact">
            <thead>
                <tr>
                    <th>{label}</th>
                    <th>Total<br>Deals</th>
                    <th>→Demo<br>Held</th>
                    <th>→Onboard</th>
                    <th>→Negot.</th>
                    <th>Won</th>
                    <th>Lost</th>
                    <th>Win Rate<br>(All Time)</th>
                    <th>Win Rate<br>({lq_label})</th>
                    <th>SQL→Won<br>(All)</th>
                    <th>Pipeline $</th>
                    <th>Won $</th>
                    <th>Rev Conv</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>"""

    html += f"""
<div class="section">
    <h2>Conversion by Account Executive</h2>
    <div class="section-desc">Active AEs only. Shows pipeline progression and win rates per rep. "{lq_label}" column shows win rate for deals <strong>created</strong> in {lq_label} only (with W/L/Open breakdown).</div>
"""
    html += ae_comparison_table_html(ae_funnels, ae_lq_stats, lq_label)
    html += "</div>"

    # Cohort Analysis
    html += """
<div class="section">
    <h2>Monthly Cohort Analysis — Create Date</h2>
    <div class="section-desc">
        Deals grouped by the month they were <strong>created</strong>. This is your "true conversion rate" view —
        each cohort is a fixed set of deals, so new pipeline additions don't distort the numbers.
        <br>Mature cohorts (&gt;70% resolved) give the most reliable win rates. Immature cohorts are faded.
    </div>
    <div class="legend">
        <div class="legend-item"><div class="legend-dot mature"></div> Mature (&gt;70% resolved)</div>
        <div class="legend-item"><div class="legend-dot maturing"></div> Maturing (40-70%)</div>
        <div class="legend-item"><div class="legend-dot immature"></div> Immature (&lt;40%)</div>
    </div>
    <div class="scroll-x">
"""
    html += cohort_table_html(cohort_data, monthly_spend_totals=monthly_spend_totals, matured_monthly_totals=matured_monthly_totals)
    html += f"""
    </div>
    <div class="callout" style="margin-top: 16px;">
        <strong>Why this matters:</strong> Your "true" win rate comes from mature cohorts where most deals have resolved.
        Looking at all-time win rates gets skewed by recently-created deals that haven't had time to close.
        Focus on cohorts with &gt;70% resolution for reliable conversion benchmarks.
        <br><strong>Mktg Spend</strong> = total tracked marketing spend that month (LinkedIn+Vouchers/Tremendous+Meta+Events+GROW+DTConnect+Landmark).
        <strong>Cohort CAC</strong> = that month's spend / won deals from that cohort. "Pending" = month is within the {SPEND_MATURITY_DAYS}-day grace window (spend too recent for reliable CAC). N/A = no spend data.
    </div>
</div>
"""

    # ============================================================
    # TIME TO CLOSE SECTION
    # ============================================================

    def fmt_days(val):
        if val is None:
            return "—"
        return f"{val:.1f}d"

    # Overall TTC summary
    html += f"""
<div class="section">
    <h2>Time to Close</h2>
    <div class="section-desc">
        How long deals take from creation to close. Shows Won vs Lost separately —
        if lost deals die fast, your pipeline is qualifying quickly. If they linger, there may be a stall problem.
    </div>

    <div class="kpi-grid" style="margin-bottom: 20px;">
        <div class="kpi-card">
            <div class="kpi-value green">{fmt_days(ttc_won['median'])}</div>
            <div class="kpi-label">Median Days to Won</div>
            <div class="kpi-detail">Avg: {fmt_days(ttc_won['avg'])} &nbsp;|&nbsp; n={ttc_won['count']}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value red">{fmt_days(ttc_lost['median'])}</div>
            <div class="kpi-label">Median Days to Lost</div>
            <div class="kpi-detail">Avg: {fmt_days(ttc_lost['avg'])} &nbsp;|&nbsp; n={ttc_lost['count']}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">{fmt_days(ttc_won['p25'])} – {fmt_days(ttc_won['p75'])}</div>
            <div class="kpi-label">Won IQR (25th–75th)</div>
            <div class="kpi-detail">Middle 50% of won deals</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">{fmt_days(ttc_lost['p25'])} – {fmt_days(ttc_lost['p75'])}</div>
            <div class="kpi-label">Lost IQR (25th–75th)</div>
            <div class="kpi-detail">Middle 50% of lost deals</div>
        </div>
    </div>
"""

    # Speed vs Win Rate table
    html += """
    <h3 style="font-size: 15px; margin-bottom: 8px; margin-top: 24px;">Speed vs Win Rate</h3>
    <div class="section-desc">Does closing faster correlate with winning? Bucket deals by how many days they took to resolve.</div>
    <table class="data-table compact">
        <thead>
            <tr>
                <th>Time Bucket</th>
                <th>Total Closed</th>
                <th>Won</th>
                <th>Lost</th>
                <th>Win Rate</th>
                <th>Won Revenue</th>
            </tr>
        </thead>
        <tbody>
"""
    for sa in speed_analysis:
        wr_class = "good" if sa["win_rate"] and sa["win_rate"] > 30 else "warn" if sa["win_rate"] and sa["win_rate"] > 15 else "bad"
        html += f"""<tr>
            <td><strong>{sa['label']}</strong></td>
            <td>{sa['total']:,}</td>
            <td>{sa['won']:,}</td>
            <td>{sa['lost']:,}</td>
            <td class="{wr_class}">{format_pct(sa['win_rate'])}</td>
            <td>{format_currency(sa['rev_won'])}</td>
        </tr>"""

    html += """
        </tbody>
    </table>
"""

    # TTC by Deal Type
    html += """
    <h3 style="font-size: 15px; margin-bottom: 8px; margin-top: 24px;">Time to Close by Deal Type</h3>
    <table class="data-table compact">
        <thead>
            <tr>
                <th>Deal Type</th>
                <th>Won Median</th>
                <th>Won Avg</th>
                <th>Won n</th>
                <th>Lost Median</th>
                <th>Lost Avg</th>
                <th>Lost n</th>
            </tr>
        </thead>
        <tbody>
"""
    for dt in sorted(ttc_by_dealtype.keys()):
        td = ttc_by_dealtype[dt]
        html += f"""<tr>
            <td><strong>{dt}</strong></td>
            <td>{fmt_days(td['won']['median'])}</td>
            <td>{fmt_days(td['won']['avg'])}</td>
            <td>{td['won']['count']}</td>
            <td>{fmt_days(td['lost']['median'])}</td>
            <td>{fmt_days(td['lost']['avg'])}</td>
            <td>{td['lost']['count']}</td>
        </tr>"""

    html += """
        </tbody>
    </table>
"""

    # TTC by AE
    html += """
    <h3 style="font-size: 15px; margin-bottom: 8px; margin-top: 24px;">Time to Close by AE</h3>
    <table class="data-table compact">
        <thead>
            <tr>
                <th>AE</th>
                <th>Won Median</th>
                <th>Won Avg</th>
                <th>Won n</th>
                <th>Lost Median</th>
                <th>Lost Avg</th>
                <th>Lost n</th>
            </tr>
        </thead>
        <tbody>
"""
    for ae in sorted(ttc_by_ae.keys()):
        td = ttc_by_ae[ae]
        html += f"""<tr>
            <td><strong>{ae}</strong></td>
            <td>{fmt_days(td['won']['median'])}</td>
            <td>{fmt_days(td['won']['avg'])}</td>
            <td>{td['won']['count']}</td>
            <td>{fmt_days(td['lost']['median'])}</td>
            <td>{fmt_days(td['lost']['avg'])}</td>
            <td>{td['lost']['count']}</td>
        </tr>"""

    html += """
        </tbody>
    </table>
"""

    # TTC by Cohort
    html += """
    <h3 style="font-size: 15px; margin-bottom: 8px; margin-top: 24px;">Time to Close by Monthly Cohort</h3>
    <div class="section-desc">Is your sales cycle getting faster or slower over time?</div>
    <div class="scroll-x">
    <table class="data-table compact">
        <thead>
            <tr>
                <th>Cohort</th>
                <th>Won Median</th>
                <th>Won Avg</th>
                <th>Won n</th>
                <th>Lost Median</th>
                <th>Lost Avg</th>
                <th>Lost n</th>
            </tr>
        </thead>
        <tbody>
"""
    for month in sorted(ttc_by_cohort.keys()):
        td = ttc_by_cohort[month]
        try:
            dt_m = datetime.strptime(month, "%Y-%m")
            month_label = dt_m.strftime("%b %Y")
        except:
            month_label = month
        html += f"""<tr>
            <td><strong>{month_label}</strong></td>
            <td>{fmt_days(td['won']['median'])}</td>
            <td>{fmt_days(td['won']['avg'])}</td>
            <td>{td['won']['count']}</td>
            <td>{fmt_days(td['lost']['median'])}</td>
            <td>{fmt_days(td['lost']['avg'])}</td>
            <td>{td['lost']['count']}</td>
        </tr>"""

    html += """
        </tbody>
    </table>
    </div>

    <div class="callout" style="margin-top: 16px;">
        <strong>Reading this section:</strong> Median is more reliable than average (not skewed by outliers).
        The "Speed vs Win Rate" table reveals whether deals that close quickly tend to win more often —
        a strong pattern here means speed is a leading indicator of deal health.
        If lost deals take much longer than won deals, consider implementing earlier disqualification.
    </div>
</div>
"""

    # Insights section
    # Find best/worst deal types
    best_type = ""
    best_type_wr = 0
    worst_type = ""
    worst_type_wr = 100
    for dt, funnel in dealtype_funnels.items():
        won = sum(1 for f in funnel if f["stage"] == "Closed Won" for _ in range(f["count"]))
        lost = sum(1 for f in funnel if f["stage"] == "Closed Lost" for _ in range(f["count"]))
        won_c = next((f["count"] for f in funnel if f["stage"] == "Closed Won"), 0)
        lost_c = next((f["count"] for f in funnel if f["stage"] == "Closed Lost"), 0)
        if (won_c + lost_c) >= 5:  # minimum sample
            wr = won_c / (won_c + lost_c) * 100
            if wr > best_type_wr:
                best_type_wr = wr
                best_type = dt
            if wr < worst_type_wr:
                worst_type_wr = wr
                worst_type = dt

    html += f"""
<div class="section">
    <h2>Key Insights & Recommendations</h2>
    <div class="callout">
        <strong>🎯 True Win Rate (Mature Cohorts):</strong> {mature_win_rate:.1f}% by volume, {mature_rev_rate:.1f}% by revenue.
        Based on cohorts with &gt;70% of deals resolved. This is your most reliable conversion benchmark.
    </div>
    <div class="callout">
        <strong>💰 Revenue Conversion:</strong> You entered {format_currency(total_revenue)} in pipeline and have won {format_currency(won_revenue)} so far.
        {"Revenue conversion often lags volume because larger deals take longer to close." if won_revenue < total_revenue * 0.3 else ""}
    </div>
"""
    if best_type:
        html += f"""
    <div class="callout">
        <strong>🏆 Best Performing Type:</strong> {best_type} deals have the highest win rate at {best_type_wr:.1f}%.
        {"" if not worst_type else f"<strong>⚠️ Lowest:</strong> {worst_type} at {worst_type_wr:.1f}%."}
    </div>
"""

    html += f"""
    <div class="callout">
        <strong>📊 Cohort Maturity:</strong> You have {len(mature_cohorts)} mature cohort(s) ({mature_months}).
        Recent months are still maturing — their win rates will change as open deals resolve.
    </div>
    <div class="callout">
        <strong>💡 Suggested Next Steps:</strong><br>
        1. Focus on the biggest stage-to-stage drop-off to find your bottleneck<br>
        2. Compare AE conversion rates to identify coaching opportunities<br>
        3. Watch immature cohorts month-over-month as they mature<br>
        4. Consider tracking <em>why</em> deals drop off at each stage (closed lost reasons by stage)
    </div>
</div>

<div class="footer">
    Dashboard built from HubSpot CRM data · {total_deals:,} deals analyzed · Dataships Sales Pipeline
</div>

</body>
</html>"""

    # Write the HTML file
    with open(OUTPUT_HTML, "w") as f:
        f.write(html)

    print(f"\n✅ Dashboard written to: {OUTPUT_HTML}")
    print(f"   Total deals: {total_deals}")
    print(f"   Won: {won_count} | Lost: {lost_count} | Open: {open_count}")
    print(f"   Win rate (all closed): {win_rate_closed:.1f}%")
    print(f"   Win rate (mature cohorts): {mature_win_rate:.1f}%")


if __name__ == "__main__":
    main()
