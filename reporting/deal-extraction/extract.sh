#!/bin/sh
INPUT="/Users/mgottron/.claude/projects/-Users-mgottron-Claude-Code/527ec8aa-2cac-47b3-8bc8-1eefdc3a1687/tool-results/mcp-4015ff8e-8996-4ec0-b434-76a999e3f7b7-search_crm_objects-1770992993243.txt"
OUTPUT="/Users/mgottron/Claude Code/deal_data_batch1.json"

# Extract the inner text field, unescape JSON, then pipe to python for parsing
# This is a two-step process since the file is a wrapper around stringified JSON

# Step 1: Extract line 4 which has the JSON text field
LINE=$(head -4 "$INPUT" | tail -1)

# Step 2: Remove the leading '    "text": "' and trailing '"'
# The line starts with spaces, "text": " and ends with "
INNER=$(echo "$LINE" | sed 's/^[[:space:]]*"text": "//; s/"$//')

# Step 3: Unescape the JSON string (\" -> " etc)
echo "$INNER" | sed 's/\\"/"/g; s/\\\\/\\/g' > "/tmp/inner_deals.json"

echo "Extracted inner JSON to /tmp/inner_deals.json"
wc -c "/tmp/inner_deals.json"
