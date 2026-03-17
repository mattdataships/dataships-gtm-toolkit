#!/usr/bin/env python3
import json
import sys

fp = '/Users/mgottron/.claude/projects/-Users-mgottron-Claude-Code/527ec8aa-2cac-47b3-8bc8-1eefdc3a1687/tool-results/mcp-4015ff8e-8996-4ec0-b434-76a999e3f7b7-search_crm_objects-1770992993243.txt'

with open(fp) as f:
    raw = json.load(f)

# Extract the inner JSON from the wrapper
inner_text = raw[0]['text']
data = json.loads(inner_text)

total_in_pipeline = data.get('total', 0)
offset = data.get('offset', 0)
results = data.get('results', [])

deals = []
for r in results:
    props = r.get('properties', {})
    amount_str = props.get('amount', None)
    if amount_str and amount_str.strip():
        try:
            amount = float(amount_str)
        except ValueError:
            amount = 0
    else:
        amount = 0

    is_closed_str = props.get('hs_is_closed_count', '0')
    try:
        is_closed = int(is_closed_str) if is_closed_str else 0
    except ValueError:
        is_closed = 0

    deal = {
        "id": str(r.get('id', '')),
        "stage": props.get('dealstage', ''),
        "dealtype": props.get('dealtype', ''),
        "sub_category": props.get('deal_type___sub_category', ''),
        "owner_id": props.get('hubspot_owner_id', ''),
        "amount": amount,
        "createdate": props.get('createdate', ''),
        "closedate": props.get('closedate', ''),
        "is_closed": is_closed,
        "entered_demo_scheduled": props.get('entered_demo_scheduled_stage__historic__date', None),
        "entered_demo_held": props.get('entered_demo_held_stage__historic__date', None),
        "entered_agreed_in_principle": props.get('entered_agreed_in_principle_stage__historic__date', None),
        "entered_closed_won": props.get('entered_closed_won_stage__historic__date', None),
        "entered_closed_lost": props.get('entered_closed_lost_stage__historic__date', None),
    }
    deals.append(deal)

output = {
    "total_deals": len(deals),
    "offset_for_next_page": offset,
    "total_in_pipeline": total_in_pipeline,
    "deals": deals
}

out_path = '/Users/mgottron/Claude Code/deal_data_batch1.json'
with open(out_path, 'w') as f:
    json.dump(output, f, indent=2)

print(f"Successfully extracted {len(deals)} deals")
print(f"Total in pipeline: {total_in_pipeline}")
print(f"Offset for next page: {offset}")
print(f"Output written to: {out_path}")

# Print all property keys from first deal to verify field availability
if results:
    print(f"\nAll property keys in first deal: {sorted(results[0].get('properties', {}).keys())}")

# Print all unique property keys across all deals
all_keys = set()
for r in results:
    all_keys.update(r.get('properties', {}).keys())
print(f"\nAll unique property keys across all deals: {sorted(all_keys)}")
