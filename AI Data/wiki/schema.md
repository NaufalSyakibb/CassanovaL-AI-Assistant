# Wiki Schema

## Folder Structure
```
wiki/
  index.md          ← catalog of all pages (LLM updates on every ingest)
  log.md            ← append-only operation log
  schema.md         ← this file (conventions)
  entities/         ← pages about people, places, products, orgs
  concepts/         ← pages about ideas, frameworks, theories
  sources/          ← one summary page per ingested source
  research/         ← research reports from the research agent
  data/             ← structured data mirrors (tasks, budget, food)
```

## Page Frontmatter
Every wiki page must have YAML frontmatter:
```yaml
---
title: Page Title
category: entity | concept | source | research
tags: [tag1, tag2]
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: [url1, url2]
---
```

## Cross-Reference Convention
Link to other wiki pages using `[[Page Title]]` syntax.
Always add outbound links to related pages at the bottom under `## See Also`.

## Ingest Workflow
1. Read the source fully
2. Create/update `wiki/sources/<title>.md` with summary + key claims
3. Update any relevant entity/concept pages
4. Update `wiki/index.md` with the new page entry
5. Append to `wiki/log.md`

## Lint Checks
- Orphan pages (no inbound links)
- Pages with no outbound links
- Contradictions between entity pages and newer sources
- Concepts mentioned in body text but lacking their own page
