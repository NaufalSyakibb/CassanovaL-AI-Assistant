# Study Material → PDF Pipeline — System Design

> Sequential 3-agent pipeline: User submits a topic → structured PDF output

---

## Overview

```
User Input ──► Material Agent ──► Konsep Agent ──► Summary Agent ──► Download PDF
               (Collector)        (Structurer)      (Writer)
```

---

## Pipeline Stages

### Stage 0 — User Input

The user provides one of:
- A **topic string** (e.g. "Photosynthesis", "Hukum Newton")
- A **URL** to an article or resource
- **Raw text / paste** from slides or notes

Submitted via `POST /api/study/kickoff` with body `{ "topic": "...", "url": "...", "text": "..." }`.

---

### Stage 1 — Material Agent 📚

**Role:** Collector & Extractor

**Model:** `mistral-large-latest`

**Input:** Raw user topic / URL / text

**Actions:**
1. `fetch_and_summarize_url(url)` — scrape and clean web content
2. `search_notes(topic)` — pull relevant notes from `data/notes.json`
3. `query_wiki(topic)` — search Obsidian wiki for existing knowledge
4. `ingest_source(title, content)` — persist new material into wiki

**Output payload passed to Konsep Agent:**

```json
{
  "topic": "string",
  "raw_text": "scraped / searched content (string)",
  "sources": ["url1", "note_id_1"],
  "word_count": 1200
}
```

---

### Stage 2 — Konsep Agent 🧠

**Role:** Structurer & Explainer

**Model:** `mistral-large-latest`

**Input:** Raw material payload from Stage 1

**Actions:**
1. Extract key concepts from raw text
2. Build hierarchical concept outline
3. Generate examples and analogies per concept
4. Tag difficulty level (beginner / intermediate / advanced)
5. `update_wiki_entity(name, info)` — update wiki with new concepts

**Output payload passed to Summary Agent:**

```json
{
  "concepts": [
    {
      "term": "string",
      "definition": "string",
      "example": "string",
      "analogy": "string"
    }
  ],
  "outline": {
    "I. Section": {
      "A. Sub-topic": ["detail 1", "detail 2"]
    }
  },
  "key_formulas": ["E = mc²"],
  "key_dates": ["1905 — Special Relativity"],
  "difficulty_level": "intermediate"
}
```

---

### Stage 3 — Summary Agent ✍️

**Role:** Writer & Formatter

**Model:** `mistral-large-latest`

**Input:** Concepts + outline payload from Stage 2

**Actions:**
1. Write narrative prose summary per section
2. Format full document in Markdown (headings, bold, tables)
3. Generate flashcard section (Q&A pairs)
4. Generate quiz section (MCQ + essay questions + answer key)
5. `create_note(title, content)` — archive to `data/notes.json`
6. Render Markdown → PDF (reportlab / weasyprint)

**Output:** PDF file saved to `AI Data/Study Pipeline/{date}_{topic}.pdf`

---

## Output PDF Structure

| Section | Content |
|---|---|
| 📌 Cover | Topic title · date generated · source list |
| 📖 Material Summary | Narrative prose · key points · examples & analogies |
| 🗂️ Concept Map | Outline / hierarchy · definitions · formulas |
| 🃏 Flashcards | Q&A pairs per concept |
| ❓ Quiz | MCQ + essay questions · answer key at end |

---

## Data Flow

```
User
 │
 │  { topic, url, text }
 ▼
Material Agent
 │  fetch_and_summarize_url()
 │  search_notes()
 │  query_wiki()
 │  ingest_source()
 │
 │  { raw_text, sources, word_count }
 ▼
Konsep Agent
 │  extract concepts
 │  build outline
 │  generate examples
 │  update_wiki_entity()
 │
 │  { concepts[], outline{}, difficulty_level }
 ▼
Summary Agent
 │  write prose
 │  generate flashcards
 │  generate quiz
 │  create_note()  ← archive
 │  render PDF
 │
 │  binary PDF file
 ▼
Download PDF  (GET /api/study/download/{job_id})
```

---

## API Endpoints (server.py)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/study/kickoff` | Start pipeline · body: `{ topic, url?, text? }` |
| `GET` | `/api/study/status/{job_id}` | Poll job progress + current phase |
| `GET` | `/api/study/download/{job_id}` | Download final PDF |

**Status response shape:**
```json
{
  "job_id": "abc123",
  "status": "running",
  "phase": "konsep",
  "progress": 66,
  "output_path": null
}
```

---

## Implementation — crewai_agents.py

```python
class StudyPipeline:
    """
    Sequential 3-agent study pipeline.
    Phase 1: MaterialAgent  → collect & extract raw material
    Phase 2: KonsepAgent    → structure concepts & outline
    Phase 3: SummaryAgent   → write prose, flashcards, quiz → render PDF
    """

    def kickoff(self, topic: str, url: str = "", text: str = "") -> str:
        # Phase 1
        material_crew = Crew(
            agents=[material_agent],
            tasks=[material_task],
            process=Process.sequential,
        )
        raw_output = material_crew.kickoff(inputs={"topic": topic, "url": url, "text": text})

        # Phase 2
        konsep_crew = Crew(
            agents=[konsep_agent],
            tasks=[konsep_task],
            process=Process.sequential,
        )
        concepts_output = konsep_crew.kickoff(inputs={"material": raw_output})

        # Phase 3
        summary_crew = Crew(
            agents=[summary_agent],
            tasks=[summary_task],
            process=Process.sequential,
        )
        pdf_path = summary_crew.kickoff(inputs={"concepts": concepts_output, "topic": topic})

        return pdf_path
```

---

## Agent Definitions

### Material Agent

```python
material_agent = Agent(
    role="Material Collector",
    goal="Gather all relevant content about the topic from the web, notes, and wiki",
    backstory="You are a research librarian. You collect, clean, and consolidate raw information without interpreting it.",
    tools=[fetch_and_summarize_url, search_notes, query_wiki, ingest_source],
    llm=mistral_large,
)
```

### Konsep Agent

```python
konsep_agent = Agent(
    role="Concept Structurer",
    goal="Extract key concepts, build a clear outline, and add examples and analogies",
    backstory="You are a curriculum designer. You transform raw information into structured, learner-friendly knowledge maps.",
    tools=[update_wiki_entity],
    llm=mistral_large,
)
```

### Summary Agent

```python
summary_agent = Agent(
    role="Summary Writer",
    goal="Write a complete study document with narrative prose, flashcards, and quiz, then render to PDF",
    backstory="You are a textbook author. You write clear, engaging study materials ready for exam preparation.",
    tools=[create_note, render_pdf],
    llm=mistral_large,
)
```

---

## File Output

```
AI Data/
└── Study Pipeline/
    ├── 2026-06-07_Photosynthesis_material.txt   ← Stage 1 output
    ├── 2026-06-07_Photosynthesis_concepts.json  ← Stage 2 output
    └── 2026-06-07_Photosynthesis.pdf            ← Final PDF
```

---

## Key Conventions

- All 3 agents use `mistral-large-latest` for quality output
- Pipeline runs in a background thread (same pattern as Ibn Al-Haytham)
- Each stage output is saved to `AI Data/Study Pipeline/` for debugging
- The PDF is also archived as a note in `data/notes.json` for Cicero to reference later
- Job status is polled via the existing `/api/crew/status` pattern
