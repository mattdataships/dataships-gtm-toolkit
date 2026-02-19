# Gong Access & Mechanics

## API Credentials
- **Access Key**: REDACTED_GONG_ACCESS_KEY
- **Secret**: REDACTED_GONG_SECRET
- **Base URL**: https://us-26354.api.gong.io
- **Auth**: Basic auth, base64-encode `key:secret`

## MCP vs Direct API
The Gong MCP server (`search_calls`) is available but limited — it only filters by date, user IDs, and call IDs. **It cannot search by call title or company name.**

For any workflow that requires finding calls by company/brand name, use direct API calls via Python `requests`. This is faster and more reliable for bulk operations.

## API Patterns

### Search All Calls (paginated)
```python
import requests, base64, json

key = "REDACTED_GONG_ACCESS_KEY"
secret = "REDACTED_GONG_SECRET"
base_url = "https://us-26354.api.gong.io"
auth = base64.b64encode(f"{key}:{secret}".encode()).decode()
headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

# List calls with metadata and parties
cursor = None
all_calls = []
while True:
    body = {
        "filter": {"fromDateTime": "2024-01-01T00:00:00Z", "toDateTime": "2027-01-01T00:00:00Z"},
        "contentSelector": {"exposedFields": {"parties": True}}
    }
    if cursor:
        body["cursor"] = cursor
    resp = requests.post(f"{base_url}/v2/calls/extensive", headers=headers, json=body)
    data = resp.json()
    all_calls.extend(data.get("calls", []))
    cursor = data.get("records", {}).get("cursor")
    if not cursor:
        break
```

### Filter Calls by Company/Brand Name
After pulling all calls, filter locally by title:
```python
brand = "YoungLA"
matches = [c for c in all_calls if brand.lower() in c.get("metaData", {}).get("title", "").lower()]
```

### Pull Transcripts
```python
call_ids = [c["metaData"]["id"] for c in matches]
# API accepts max ~50 call IDs per request — batch if needed
body = {"filter": {"callIds": call_ids}}
resp = requests.post(f"{base_url}/v2/calls/transcript", headers=headers, json=body)
transcripts = resp.json().get("callTranscripts", [])
```

### Parse Transcripts
Transcripts have a nested structure. Each entry in `transcript` array is a speaker turn containing a `sentences` array:
```python
for turn in transcript_entry["transcript"]:
    speaker_id = turn["speakerId"]
    sentences = turn.get("sentences", [])
    text = " ".join([s.get("text", "") for s in sentences])
```

### Map Speaker IDs to Names
Speaker IDs from transcripts must be mapped using the `parties` data from the call metadata:
```python
# Build speaker map from call metadata
speaker_map = {}
for party in call.get("parties", []):
    speaker_id = party.get("speakerId")
    name = party.get("name", "Unknown")
    affiliation = party.get("affiliation", "Unknown")  # "Internal" or "External"
    speaker_map[speaker_id] = f"{name} ({affiliation})"
```

## Transcript Output Format
Save formatted transcripts to `/tmp/{brand}_all_transcripts.txt` with this structure:
```
================================================================================
CALL: {call_title}
DATE: {start_time}
================================================================================

{Speaker Name} ({Internal/External}): {text}

{Speaker Name} ({Internal/External}): {text}
...
```

## Deduplication
The API sometimes returns duplicate call IDs. Always deduplicate by call ID before pulling transcripts.

## Important Notes
- The MCP `search_calls` tool works fine for browsing recent calls or pulling by known call ID — use it when you don't need title search
- For bulk transcript pulls (10+ calls), save everything to a file first, then read through it systematically rather than trying to hold it all in context
- Subagents CANNOT access Gong MCP tools — all Gong operations must run from the main thread
