import json
import sys

# Mappings
STAGE_MAP = {
    "qualifiedtobuy": "Demo Scheduled - SQL",
    "presentationscheduled": "Demo Held - SQO",
    "96256085": "Onboarded - SQO",
    "998696192": "Negotiation - SQO",
    "closedwon": "Closed Won",
    "closedlost": "Closed Lost",
}

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
}

def parse_amount(val):
    if val is None or val == "" or val == "null":
        return 0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0

def empty_to_null(val):
    if val is None or val == "" or val == "null":
        return None
    return val

def transform_deal(raw_deal):
    props = raw_deal.get("properties", {})

    owner_id_raw = props.get("hubspot_owner_id", "")
    owner_name = OWNER_MAP.get(str(owner_id_raw), "Other/Inactive") if owner_id_raw else "Other/Inactive"

    stage_raw = props.get("dealstage", "")
    stage = STAGE_MAP.get(stage_raw, stage_raw)

    dealtype_raw = props.get("dealtype", "")
    dealtype = DEALTYPE_MAP.get(dealtype_raw, dealtype_raw) if dealtype_raw else dealtype_raw

    is_closed_raw = props.get("hs_is_closed_count", "0")
    try:
        is_closed = int(is_closed_raw) if is_closed_raw else 0
    except (ValueError, TypeError):
        is_closed = 0

    return {
        "id": props.get("hs_object_id", str(raw_deal.get("id", ""))),
        "dealname": props.get("dealname", ""),
        "stage": stage,
        "dealtype": dealtype,
        "sub_category": empty_to_null(props.get("deal_type___sub_category")),
        "owner_id": str(owner_id_raw) if owner_id_raw else None,
        "owner_name": owner_name,
        "amount": parse_amount(props.get("amount")),
        "createdate": empty_to_null(props.get("createdate")),
        "closedate": empty_to_null(props.get("closedate")),
        "is_closed": is_closed,
        "entered_demo_scheduled": empty_to_null(props.get("entered_demo_scheduled_stage__historic__date")),
        "entered_demo_held": empty_to_null(props.get("entered_demo_held_stage__historic__date")),
        "entered_agreed_in_principle": empty_to_null(props.get("entered_agreed_in_principle_stage__historic__date")),
        "entered_closed_won": empty_to_null(props.get("entered_closed_won_stage__historic__date")),
        "entered_closed_lost": empty_to_null(props.get("entered_closed_lost_stage__historic__date")),
    }

def main():
    input_file = '/Users/mgottron/.claude/projects/-Users-mgottron-Claude-Code/527ec8aa-2cac-47b3-8bc8-1eefdc3a1687/tool-results/mcp-4015ff8e-8996-4ec0-b434-76a999e3f7b7-search_crm_objects-1770993186512.txt'
    output_file = '/Users/mgottron/Claude Code/deals_batch2.json'

    # Read and parse
    with open(input_file, 'r') as f:
        raw = json.load(f)

    inner = json.loads(raw[0]['text'])

    results = inner.get('results', [])
    total_from_api = inner.get('total', 'unknown')

    print(f"API total: {total_from_api}")
    print(f"Results in file: {len(results)}")

    # Show property keys from first record
    if results:
        print(f"Property keys in first record: {sorted(results[0]['properties'].keys())}")

    # Transform all deals
    deals = []
    for r in results:
        deals.append(transform_deal(r))

    output = {
        "batch": "101-300",
        "count": len(deals),
        "deals": deals
    }

    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nWrote {len(deals)} deals to {output_file}")

    # Summary stats
    stages = {}
    types = {}
    owners = {}
    for d in deals:
        stages[d['stage']] = stages.get(d['stage'], 0) + 1
        types[d['dealtype']] = types.get(d['dealtype'], 0) + 1
        owners[d['owner_name']] = owners.get(d['owner_name'], 0) + 1

    print("\n--- Stage distribution ---")
    for k, v in sorted(stages.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print("\n--- Dealtype distribution ---")
    for k, v in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print("\n--- Owner distribution (top 10) ---")
    for k, v in sorted(owners.items(), key=lambda x: -x[1])[:10]:
        print(f"  {k}: {v}")

    # Check for unmapped stages or dealtypes
    unmapped_stages = [d['stage'] for d in deals if d['stage'] not in STAGE_MAP.values()]
    unmapped_types = [d['dealtype'] for d in deals if d['dealtype'] and d['dealtype'] not in DEALTYPE_MAP.values()]
    if unmapped_stages:
        unique_unmapped = set(unmapped_stages)
        print(f"\nWARNING: Unmapped stages found: {unique_unmapped}")
    if unmapped_types:
        unique_unmapped = set(unmapped_types)
        print(f"\nWARNING: Unmapped dealtypes found: {unique_unmapped}")

if __name__ == '__main__':
    main()
