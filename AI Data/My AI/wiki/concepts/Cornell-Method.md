---
title: Cornell Method — Note-Taking System
category: concept
tags: [study, learning, note-taking, Cicero, retention]
created: 2026-05-31
updated: 2026-05-31
sources: []
---

# Cornell Method — Note-Taking System

> The primary study framework used by Cicero (Study Agent).

[[Home]] | [[Cicero Agent]]

---

## What It Is

The Cornell Method is a structured note-taking system that divides a page into three sections to improve retention and active recall. Developed at Cornell University.

---

## The Three Sections

```
┌──────────────────────────────────────────┐
│              TOPIC / TITLE               │
├───────────────┬──────────────────────────┤
│               │                          │
│  KEY TERMS &  │     MAIN NOTES           │
│  QUESTIONS    │     (Detail section)     │
│  (Cue column) │                          │
│               │                          │
├───────────────┴──────────────────────────┤
│           SUMMARY (3–5 sentences)        │
└──────────────────────────────────────────┘
```

| Section | Purpose | How to use |
|---------|---------|------------|
| **Main notes** (right, ~70%) | Full explanation and details | Write during study/lecture |
| **Key terms / Cue column** (left, ~30%) | Questions and keywords that trigger recall | Fill after writing main notes |
| **Summary** (bottom) | Synthesize the whole page | Write after everything else |

---

## How Cicero Implements It

Cicero runs three agents in sequence when you enter a topic:

| Agent | Produces | Cornell Section |
|-------|---------|----------------|
| MateriAgent | 3–5 comprehensive content sections | Main notes (right column) |
| KonsepAgent | 6–12 key terms + definitions | Cue column (left) |
| RingkasanAgent | 3–5 sentence synthesis | Summary (bottom) |

---

## Why It Works

- Forces **active processing** — summarizing is harder than re-reading
- Cue column enables **self-testing** (cover the right, quiz yourself from the left)
- Summary forces **synthesis**, not just transcription
- Long-term: review only the cue column for efficient revision

---

## Usage in Your System

Trigger Cicero with any topic. Best used for:
- Academic subjects (Design Thinking, Supply Chain, Math)
- Concepts from reading (books, articles, research)
- Frameworks from any domain

---

## See Also

[[Cicero Agent]] · [[concepts/Second-Brain]] · [[entities/Naufal]]
