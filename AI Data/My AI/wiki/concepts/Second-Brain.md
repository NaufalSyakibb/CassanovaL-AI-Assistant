---
title: Second Brain — This System
category: concept
tags: [PKM, organization, system, meta, PARA]
created: 2026-05-31
updated: 2026-05-31
---

# Second Brain — This System

> Meta-documentation of the personal AI second brain. How it works, what each part does, and how to use it well.

[[Home]] | [[wiki/index]]

---

## What Is a Second Brain?

A second brain is an external system that captures, organizes, and connects knowledge — so your biological brain doesn't have to hold everything. It makes thinking external and searchable.

Coined by Tiago Forte (Building a Second Brain). The key principle:

> **Your mind is for having ideas, not for holding them.**

---

## This System's Architecture

```
User
 │
 ├── 10 AI Agents (specialized tasks)
 │    ├── Alfred     — tasks, to-do, quick notes
 │    ├── Mansa      — finance, accounts, expenses
 │    ├── Dostoyevsky— journaling, emotional reflection
 │    ├── Lavoisier  — nutrition, fitness tracking
 │    ├── Cicero     — study, Cornell notes
 │    ├── Linus      — code, programming
 │    ├── Najwa      — news, current events
 │    ├── CalCore    — calendar, scheduling
 │    ├── Da Vinci   — creative brainstorming
 │    └── Ferry      — deep autonomous research
 │
 ├── Wiki (distilled knowledge graph)
 │    ├── entities/  — people, places
 │    ├── concepts/  — frameworks, ideas
 │    ├── sources/   — ingested readings
 │    └── research/  — Ferry output
 │
 └── Synthesis Layer
      ├── _HOME.md         — daily entry point
      ├── _PROFILE.md      — personal synthesis
      ├── _INSIGHTS_*.md   — monthly cross-agent analysis
      └── _WEEKLY_REVIEW   — reflection template
```

---

## The Four Workflows (PARA Adapted)

| Layer | What it is | Your agents |
|-------|-----------|-------------|
| **Capture** | Get it out of your head | Alfred (tasks), all agents (conversations) |
| **Organize** | Route to the right place | Agent routing via supervisor |
| **Distill** | Extract what matters | Wiki pages, monthly insights |
| **Express** | Use knowledge to act | Cicero (study), Linus (code), Da Vinci (ideas) |

---

## Daily Usage Guide

| Trigger | Action | Agent |
|---------|--------|-------|
| Something to do | "add task: [X]" | Alfred |
| A purchase | "[item] [amount]" | Mansa |
| A feeling | Describe it naturally | Dostoyevsky |
| Something I ate | "[food] [portion]" | Lavoisier |
| Something to learn | "[topic]" | Cicero |
| A code question | Describe the problem | Linus |
| News I want | "[topic] news" | Najwa |
| A calendar event | "add event: [details]" | CalCore |
| A creative question | Ask freely | Da Vinci |
| Deep research | "[topic] — research" | Ferry |

---

## Weekly Maintenance

Every Sunday, run the [[_WEEKLY_REVIEW_TEMPLATE]]:
1. Clear loose ends into agents
2. Score the week across domains
3. Check agent data summaries
4. Write a retrospective
5. Set 3 intentions for next week
6. Optionally: add 1 wiki page

---

## Monthly Synthesis

On the 1st of each month, create `_INSIGHTS_YYYY-MM.md`:
1. Review all agent conversation logs from the month
2. Identify cross-domain patterns
3. Update `_PROFILE.md` with new information
4. Update relevant wiki entity/concept pages
5. Log the session in `wiki/log.md`

---

## See Also

[[concepts/Cornell-Method]] · [[_PROFILE]] · [[_INSIGHTS_2026-05]] · [[wiki/index]] · [[Home]]
