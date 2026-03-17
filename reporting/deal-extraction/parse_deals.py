import json
import sys

fp = '/Users/mgottron/.claude/projects/-Users-mgottron-Claude-Code/527ec8aa-2cac-47b3-8bc8-1eefdc3a1687/tool-results/mcp-4015ff8e-8996-4ec0-b434-76a999e3f7b7-search_crm_objects-1770992993243.txt'

with open(fp) as f:
    data = json.load(f)

# Understand structure
if isinstance(data, list):
    print(f"Type: list, length: {len(data)}")
    if len(data) > 0:
        first = data[0]
        print(f"First element type: {type(first).__name__}")
        if isinstance(first, dict):
            print(f"First element keys: {list(first.keys())}")
            # Check if it's a wrapper with content_type/text structure
            if 'text' in first:
                inner = first['text']
                if isinstance(inner, str):
                    inner_data = json.loads(inner)
                    print(f"Inner data type: {type(inner_data).__name__}")
                    if isinstance(inner_data, dict):
                        print(f"Inner data keys: {list(inner_data.keys())}")
                        print(f"total: {inner_data.get('total')}")
                        print(f"offset: {inner_data.get('offset')}")
                        results = inner_data.get('results', [])
                        print(f"Number of results: {len(results)}")
                        if len(results) > 0:
                            print(f"First result keys: {list(results[0].keys())}")
                            props = results[0].get('properties', {})
                            print(f"Properties keys: {sorted(props.keys())}")
                            print(f"\nSample first result properties:")
                            for k, v in sorted(props.items()):
                                print(f"  {k}: {v}")
elif isinstance(data, dict):
    print(f"Type: dict")
    print(f"Keys: {list(data.keys())}")
    print(f"total: {data.get('total')}")
    print(f"offset: {data.get('offset')}")
