#!/bin/bash
# Extract deal data from HubSpot JSON response file
INPUT="/Users/mgottron/.claude/projects/-Users-mgottron-Claude-Code/527ec8aa-2cac-47b3-8bc8-1eefdc3a1687/tool-results/mcp-4015ff8e-8996-4ec0-b434-76a999e3f7b7-search_crm_objects-1770992993243.txt"
OUTPUT="/Users/mgottron/Claude Code/deal_data_batch1.json"

# Step 1: Extract the text content from line 4, removing the JSON wrapper
# The file format is: [{"type":"text","text":"<escaped JSON>"}]
# Line 4 has format:     "text": "<escaped JSON content>"

# Get the escaped JSON content from line 4
RAW_LINE=$(head -4 "$INPUT" | tail -1)

# Remove leading '    "text": "' (14 chars) and trailing '"'
CONTENT="${RAW_LINE#*\"text\": \"}"
CONTENT="${CONTENT%\"}"

# Unescape: replace \" with "
UNESCAPED=$(printf '%s' "$CONTENT" | sed 's/\\"/"/g')

# Write to temp file
printf '%s' "$UNESCAPED" > /tmp/deals_inner.json

echo "Inner JSON written to /tmp/deals_inner.json"
wc -c /tmp/deals_inner.json

# Now use /usr/bin/env to run an interpreter
/usr/bin/env -S /usr/bin/python3 << 'HEREDOC'
import json

with open('/tmp/deals_inner.json') as f:
    data = json.load(f)

total_in_pipeline = data.get('total', 0)
offset = data.get('offset', 0)
results = data.get('results', [])

deals = []
for r in results:
    props = r.get('properties', {})
    amount_str = props.get('amount', '')
    try:
        amount = float(amount_str) if amount_str else 0
    except:
        amount = 0

    is_closed_str = props.get('hs_is_closed_count', '0')
    try:
        is_closed = int(is_closed_str) if is_closed_str else 0
    except:
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
        "entered_demo_scheduled": props.get('entered_demo_scheduled_stage__historic__date'),
        "entered_demo_held": props.get('entered_demo_held_stage__historic__date'),
        "entered_agreed_in_principle": props.get('entered_agreed_in_principle_stage__historic__date'),
        "entered_closed_won": props.get('entered_closed_won_stage__historic__date'),
        "entered_closed_lost": props.get('entered_closed_lost_stage__historic__date'),
    }
    deals.append(deal)

output = {
    "total_deals": len(deals),
    "offset_for_next_page": offset,
    "total_in_pipeline": total_in_pipeline,
    "deals": deals
}

with open('/Users/mgottron/Claude Code/deal_data_batch1.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"Extracted {len(deals)} deals")
print(f"Total in pipeline: {total_in_pipeline}")
print(f"Offset for next: {offset}")

all_keys = set()
for r in results:
    all_keys.update(r.get('properties', {}).keys())
print(f"All property keys: {sorted(all_keys)}")
HEREDOC
