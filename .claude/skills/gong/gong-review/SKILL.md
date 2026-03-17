---
name: gong-review
description: |
  Use when user asks to review Gong calls for a brand/company, prep for an interview,
  draft case study questions, or analyze call transcripts for a specific account.
  Triggers on: "review calls", "prep for interview", "case study questions",
  "pull transcripts", "what did we talk about with [brand]", "review [brand] calls"
  Do NOT use for: broad ICP analysis across many brands (use gong-research instead),
  or event enrichment (use event-playbook rules instead)
argument-hint: brand or company name
---

# Gong Call Review

## What This Skill Does
Pulls all Gong call transcripts for a specific brand/company, reads through them systematically, and produces output based on what Matt is asking for.

## Workflow
1. **Search** — Use direct Gong API (see `.claude/rules/gong.md`) to find all calls matching the brand name in the call title. Page through all results.
2. **Deduplicate** — Remove duplicate call IDs.
3. **Pull transcripts** — Fetch all transcripts via API. Map speaker IDs to names using call party metadata.
4. **Save to file** — Write formatted transcripts to `/tmp/{brand}_all_transcripts.txt` for systematic reading.
5. **Read everything** — Read through all transcripts start to finish. Do not skip or skim. The quality of the output depends on full context.
6. **Produce output** — Based on what Matt asked for (see Output Modes below).

## Output Modes

### Interview Prep / Case Study Questions (default)
When Matt says "prep for interview", "case study questions", or just "review calls for [brand]":
- Read all transcripts and identify: the narrative arc (before state, trigger, evaluation, results, expansion), key data points, surprising insights, relationship dynamics, and quotable moments
- Draft 10-20 questions ordered as a natural interview flow: brand context -> the trigger/problem -> evaluation/test -> results -> unique angles -> expansion/future -> big picture
- Each question should include a brief note on *why* it's sharp — what specific transcript context it's pulling from
- Flag the 5-6 strongest questions for a published case study

### Account Summary
When Matt says "what do we know about [brand]" or "summarize [brand] calls":
- Produce a structured summary: key contacts, timeline, product usage, results, upcoming plans, open issues
- Include specific numbers and data points, not vague summaries

### Raw Transcript Access
When Matt says "pull transcripts for [brand]":
- Just run steps 1-4 and tell Matt where the file is

## Key Principles
- **Read every transcript fully.** The best insights come from details buried in biweekly check-ins, not just the big demo or results calls.
- **Track the timeline.** Note when things happened — demo date, test start, results review, go-live, expansion conversations.
- **Map the people.** Know who's internal (Dataships) vs external (customer), who the decision maker is, who the day-to-day contact is, who the technical contact is.
- **Find the non-obvious.** The best case study moments aren't "consent rate went up" — they're things like "the 15% incentive performed identically to a pre-tick" or "85% of the EU list was noncompliant and they didn't know."
