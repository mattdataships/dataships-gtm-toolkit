# Dataships GTM Toolkit

## Who This Is For
Matt Gottron, VP GTM at Dataships. This is my working environment for GTM operations — event strategy, customer research, content, reporting, and deal ops.

## How I Work
- I move fast and don't want to approve every intermediate step. Run full workflows end-to-end and come back with the finished output.
- I'll typically drop a short prompt ("enrich this event list", "review YoungLA calls", "draft a case study"). The skills and rules here should give you everything you need to execute without follow-up questions unless genuinely ambiguous.
- Output files go to `~/Downloads/` unless I specify otherwise.
- When writing (case studies, emails, social posts), match my voice: direct, confident, data-driven, no fluff. I'm talking to DTC/e-commerce operators, not enterprise buyers.

## Key Data Sources
- **Storeleads TAM CSV**: `data/storeleads-tam.csv`
- **HubSpot**: Hub ID 8868359, accessible via MCP tools (main thread only — subagents can't access)
- **Gong**: API access configured via MCP. See `.claude/rules/gong.md` for mechanics.

## Technical Notes
- Subagents cannot access HubSpot or Gong MCP tools — run all queries from the main thread
- For bulk operations (80+ API calls), prefer local file matching over live API when a CSV export is available
