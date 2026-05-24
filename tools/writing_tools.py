"""
Orwell Writing Coach tools — analysis, voice calibration, draft management.

Inspired by the humanizer project (github.com/blader/humanizer):
  • Rule-based AI-pattern detection (70+ markers across 4 categories)
  • Voice calibration: extract stylistic fingerprint from user writing samples
  • Two-pass diagnosis: detect patterns → agent rewrites → verify residuals
  • Draft persistence in data/writing_drafts.json
"""

import json
import uuid
import re
from pathlib import Path
from datetime import datetime
from langchain.tools import tool

_BASE = Path(__file__).resolve().parent.parent
_DRAFTS_FILE  = _BASE / "data" / "writing_drafts.json"
_VOICE_FILE   = _BASE / "data" / "writing_voice.json"

# ── JSON helpers ──────────────────────────────────────────────────────────────

def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def _save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── AI-pattern library (humanizer-inspired) ───────────────────────────────────

_PATTERNS: dict[str, list[str]] = {
    "Significance Inflation": [
        "marks a pivotal moment", "pivotal moment", "underscores the importance",
        "reflects broader trends", "highlights the need", "demonstrates the impact",
        "showcases", "epitomizes", "testament to", "a milestone", "groundbreaking",
        "revolutionary", "transformative", "game-changing", "game changer",
        "unprecedented", "remarkable", "landmark", "seminal",
    ],
    "Hollow Hedging": [
        "it's worth noting", "it is worth noting", "it is important to note",
        "it should be noted", "notably", "interestingly", "it could be argued",
        "one could argue", "arguably", "in a sense", "in some ways",
        "to some extent", "it might be said", "it seems",
    ],
    "Corporate Filler": [
        "in the realm of", "in the landscape of", "within the context of",
        "across the board", "at the end of the day", "going forward",
        "leverage", "synergy", "streamline", "cutting-edge", "state-of-the-art",
        "innovative solution", "best practices", "value proposition",
        "robust", "scalable", "holistic", "paradigm shift", "ecosystem",
        "vibrant", "nestled", "breathtaking",
    ],
    "Copula Avoidance": [
        "serves as a", "serves as the", "boasts", "presents as", "functions as",
        "stands as", "acts as a", "acts as the", "operates as",
    ],
    "Transition Filler": [
        "in conclusion", "to summarize", "to sum up", "in summary",
        "as mentioned earlier", "as stated above", "as previously discussed",
        "building upon this", "with that said", "that being said",
        "furthermore", "moreover", "additionally", "in addition to this",
        "it follows that", "consequently",
    ],
    "Vague Attribution": [
        "experts say", "experts argue", "experts suggest", "studies show",
        "research indicates", "research suggests", "according to experts",
        "many believe", "many argue", "some argue", "it has been observed",
        "observers note", "industry insiders",
    ],
    "Chatbot Artifacts": [
        "i hope this helps", "i hope this was helpful", "feel free to",
        "of course", "certainly", "absolutely", "great question",
        "i'd be happy to", "i would be happy to", "sure thing",
        "please let me know", "don't hesitate to",
    ],
    "Outline Formula": [
        "challenges and opportunities", "challenges and future prospects",
        "pros and cons", "advantages and disadvantages",
        "not only.*but also", "both.*and.*",
    ],
}

_PASSIVE_RE = re.compile(
    r'\b(is|are|was|were|be|been|being)\s+\w+ed\b', re.IGNORECASE
)
_EM_DASH_RE  = re.compile(r'—')
_ADV_RE      = re.compile(
    r'\b(very|quite|rather|somewhat|extremely|incredibly|amazingly|'
    r'significantly|substantially|largely|essentially|basically|literally|'
    r'absolutely|completely|totally|utterly|profoundly)\b',
    re.IGNORECASE
)


def _detect_patterns(text: str) -> dict:
    """Return a dict of {category: [matched phrases]} found in text."""
    findings: dict[str, list[str]] = {}
    lower = text.lower()

    for category, phrases in _PATTERNS.items():
        hits = []
        for phrase in phrases:
            if ".*" in phrase:
                if re.search(phrase, lower):
                    hits.append(phrase.replace(".*", " … "))
            elif phrase.lower() in lower:
                hits.append(phrase)
        if hits:
            findings[category] = hits

    passive_count = len(_PASSIVE_RE.findall(text))
    if passive_count >= 3:
        findings["Passive Voice"] = [f"{passive_count} passive constructions detected"]

    em_count = len(_EM_DASH_RE.findall(text))
    if em_count >= 4:
        findings["Em-dash Overuse"] = [f"{em_count} em-dashes — varied punctuation would help"]

    adv_hits = _ADV_RE.findall(text)
    if len(adv_hits) >= 3:
        unique = list(dict.fromkeys(a.lower() for a in adv_hits))
        findings["Weak Adverbs"] = unique[:6]

    return findings


def _sentence_stats(text: str) -> dict:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if not sentences:
        return {}
    lengths = [len(s.split()) for s in sentences if s.strip()]
    avg = round(sum(lengths) / len(lengths), 1) if lengths else 0
    short  = sum(1 for l in lengths if l <= 10)
    medium = sum(1 for l in lengths if 11 <= l <= 25)
    long_  = sum(1 for l in lengths if l > 25)
    return {
        "count": len(lengths),
        "avg_words": avg,
        "short_pct":  round(short  / len(lengths) * 100) if lengths else 0,
        "medium_pct": round(medium / len(lengths) * 100) if lengths else 0,
        "long_pct":   round(long_  / len(lengths) * 100) if lengths else 0,
    }


# ── LangChain tools ───────────────────────────────────────────────────────────

@tool
def analyze_writing(text: str) -> str:
    """Analyze text for AI-writing tells, weak style, and structural problems.

    Returns a structured diagnostic report listing:
    - Detected AI-pattern categories with specific phrases
    - Sentence rhythm stats (avg length, short/medium/long distribution)
    - Passive voice count
    - Specific rewriting suggestions

    Use this FIRST before any rewrite. Feed the report to your own reasoning to
    produce the improved text.
    """
    if len(text.strip()) < 20:
        return "Text too short to analyze. Please provide at least a few sentences."

    findings = _detect_patterns(text)
    stats    = _sentence_stats(text)
    word_count = len(text.split())

    lines = [f"## Writing Analysis ({word_count} words)\n"]

    # Sentence rhythm
    if stats:
        rhythm_note = ""
        if stats["long_pct"] > 60:
            rhythm_note = " ← too many long sentences; vary with shorter ones"
        elif stats["short_pct"] > 70:
            rhythm_note = " ← choppy; some longer sentences would add flow"
        lines.append(
            f"**Rhythm** — {stats['count']} sentences, avg {stats['avg_words']} words "
            f"({stats['short_pct']}% short / {stats['medium_pct']}% medium / "
            f"{stats['long_pct']}% long){rhythm_note}"
        )

    if not findings:
        lines.append("\n**Pattern Scan** — No major AI-writing tells detected. "
                     "The text reads as relatively natural.")
    else:
        lines.append(f"\n**Pattern Scan** — {len(findings)} issue categories found:\n")
        for category, hits in findings.items():
            lines.append(f"- **{category}**: {', '.join(f'`{h}`' for h in hits[:4])}")

    lines.append("\n## Suggested Actions")
    if "Significance Inflation" in findings:
        lines.append("- Replace inflated language with plain verbs: "
                     "`showcases` → `shows`, `serves as a testament to` → `is`")
    if "Hollow Hedging" in findings:
        lines.append("- Cut hedge phrases entirely — they add no information")
    if "Transition Filler" in findings:
        lines.append("- Delete closing transition phrases (`In conclusion`, `To summarize`); "
                     "let the last sentence carry the weight")
    if "Corporate Filler" in findings:
        lines.append("- Replace corporate abstractions with specific facts, numbers, or names")
    if "Passive Voice" in findings:
        lines.append("- Convert passive constructions to active subject-verb-object order")
    if "Chatbot Artifacts" in findings:
        lines.append("- Remove chatbot phrases (`feel free to`, `I hope this helps`) entirely")
    if "Vague Attribution" in findings:
        lines.append("- Replace vague attribution (`experts say`) with named sources, "
                     "dates, or specific data points")
    if "Weak Adverbs" in findings:
        adv_list = findings["Weak Adverbs"]
        lines.append(f"- Cut or replace weak adverbs: {', '.join(adv_list)} "
                     "— choose a stronger verb instead")
    if stats and stats["avg_words"] > 25:
        lines.append("- Break long sentences at natural clause boundaries — "
                     "a period beats a comma every time")

    return "\n".join(lines)


@tool
def verify_humanization(original: str, rewritten: str) -> str:
    """Second-pass check: compare original and rewritten text for residual AI tells.

    Call this AFTER producing a rewrite. It finds patterns that survived the
    first pass and prompts a targeted second revision.

    Returns: what still sounds AI-generated, and what improved.
    """
    orig_findings  = _detect_patterns(original)
    new_findings   = _detect_patterns(rewritten)

    fixed   = [cat for cat in orig_findings if cat not in new_findings]
    persist = {cat: hits for cat, hits in new_findings.items() if cat in orig_findings}
    new_    = {cat: hits for cat, hits in new_findings.items() if cat not in orig_findings}

    lines = ["## Humanization Verification\n"]

    if fixed:
        lines.append(f"**✓ Fixed ({len(fixed)}):** {', '.join(fixed)}")
    if persist:
        lines.append(f"\n**Still present — revise these:**")
        for cat, hits in persist.items():
            lines.append(f"- **{cat}**: {', '.join(f'`{h}`' for h in hits[:3])}")
    if new_:
        lines.append(f"\n**New patterns introduced — unexpected:**")
        for cat, hits in new_.items():
            lines.append(f"- **{cat}**: {', '.join(f'`{h}`' for h in hits[:3])}")

    if not persist and not new_:
        lines.append("\n**All detected patterns resolved.** The rewrite is clean.")
    else:
        lines.append(
            f"\n**Action:** Revise the {len(persist) + len(new_)} remaining categories "
            "in a targeted second pass."
        )

    return "\n".join(lines)


@tool
def calibrate_voice(sample_text: str) -> str:
    """Extract and save the user's writing voice fingerprint from a sample.

    Analyzes:
    - Sentence length distribution and average
    - Common opening words / patterns
    - Transition word preferences
    - Punctuation habits (em-dashes, semicolons, parentheses)
    - Vocabulary formality estimate
    - Adverb usage tendency

    Saves the profile to data/writing_voice.json for use in future sessions.
    Provide at least 200 words of your own authentic writing as the sample.
    """
    if len(sample_text.split()) < 80:
        return ("Sample too short. Provide at least 200 words of your own writing "
                "for a meaningful voice profile.")

    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', sample_text.strip()) if s.strip()]
    lengths = [len(s.split()) for s in sentences]
    avg = round(sum(lengths) / len(lengths), 1) if lengths else 0

    # Opening word patterns (first 2 words of each sentence)
    openings = []
    for s in sentences:
        words = s.split()
        if words:
            openings.append(words[0].rstrip(",:").lower())
    from collections import Counter
    top_openings = [w for w, _ in Counter(openings).most_common(6)]

    # Transition preferences
    transitions = [
        "but", "so", "and", "because", "although", "though", "however",
        "therefore", "thus", "yet", "still", "also", "then",
    ]
    text_lower = sample_text.lower()
    used_transitions = [t for t in transitions if f" {t} " in text_lower]

    # Punctuation habits
    total_sentences = max(len(sentences), 1)
    em_dash_rate    = round(len(_EM_DASH_RE.findall(sample_text)) / total_sentences, 2)
    semicolon_rate  = round(sample_text.count(";") / total_sentences, 2)
    paren_rate      = round(sample_text.count("(") / total_sentences, 2)

    punct = {}
    punct["em_dash"]   = "frequent" if em_dash_rate > 0.3 else ("occasional" if em_dash_rate > 0.1 else "rare")
    punct["semicolon"] = "frequent" if semicolon_rate > 0.2 else ("occasional" if semicolon_rate > 0.05 else "rare")
    punct["parens"]    = "frequent" if paren_rate > 0.3 else ("occasional" if paren_rate > 0.1 else "rare")

    # Adverb tendency
    adv_count = len(_ADV_RE.findall(sample_text))
    adv_per_100 = round(adv_count / max(len(sample_text.split()), 1) * 100, 1)
    adv_style = "heavy" if adv_per_100 > 3 else ("moderate" if adv_per_100 > 1.5 else "minimal")

    # Vocabulary formality (heuristic: ratio of long words)
    words = re.findall(r'\b[a-zA-Z]+\b', sample_text)
    long_word_pct = round(sum(1 for w in words if len(w) > 8) / max(len(words), 1) * 100, 1)
    formality = "formal" if long_word_pct > 20 else ("moderate" if long_word_pct > 12 else "casual")

    short_pct  = round(sum(1 for l in lengths if l <= 10) / total_sentences * 100)
    medium_pct = round(sum(1 for l in lengths if 11 <= l <= 25) / total_sentences * 100)
    long_pct   = round(sum(1 for l in lengths if l > 25) / total_sentences * 100)

    profile = {
        "avg_sentence_words":  avg,
        "sentence_distribution": {"short_pct": short_pct, "medium_pct": medium_pct, "long_pct": long_pct},
        "common_openings":     top_openings,
        "preferred_transitions": used_transitions[:8],
        "punctuation_style":   punct,
        "adverb_usage":        adv_style,
        "vocabulary_formality": formality,
        "extracted_from_words": len(words),
        "calibrated_at":       datetime.now().isoformat(timespec="seconds"),
    }
    _save(_VOICE_FILE, profile)

    return (
        f"## Voice Profile Calibrated\n\n"
        f"- **Sentence length**: avg {avg} words "
        f"({short_pct}% short / {medium_pct}% medium / {long_pct}% long)\n"
        f"- **Common sentence openers**: {', '.join(top_openings)}\n"
        f"- **Preferred transitions**: {', '.join(used_transitions[:6]) or 'varied'}\n"
        f"- **Punctuation**: em-dash {punct['em_dash']}, "
        f"semicolons {punct['semicolon']}, parentheses {punct['parens']}\n"
        f"- **Adverb usage**: {adv_style}\n"
        f"- **Vocabulary formality**: {formality}\n\n"
        f"Profile saved. I will now mirror this voice in all rewrites and coaching."
    )


@tool
def get_voice_profile() -> str:
    """Return the stored writing voice profile, or indicate none exists yet.

    Use at the start of rewriting tasks to check if a voice fingerprint is
    available to guide the style of rewrites.
    """
    profile = _load(_VOICE_FILE, None)
    if not profile:
        return ("No voice profile saved yet. Use `calibrate_voice()` with a sample "
                "of your own writing (200+ words) to set one up.")

    p = profile
    dist = p.get("sentence_distribution", {})
    punct = p.get("punctuation_style", {})
    since = p.get("calibrated_at", "unknown date")[:10]

    return (
        f"## Your Writing Voice Profile (calibrated {since})\n\n"
        f"- Sentence length: avg {p.get('avg_sentence_words')} words "
        f"({dist.get('short_pct',0)}% short / {dist.get('medium_pct',0)}% medium / "
        f"{dist.get('long_pct',0)}% long)\n"
        f"- Common openers: {', '.join(p.get('common_openings', []))}\n"
        f"- Preferred transitions: {', '.join(p.get('preferred_transitions', []))}\n"
        f"- Punctuation: em-dash {punct.get('em_dash','?')}, "
        f"semicolons {punct.get('semicolon','?')}, parens {punct.get('parens','?')}\n"
        f"- Adverb usage: {p.get('adverb_usage','?')}\n"
        f"- Vocabulary: {p.get('vocabulary_formality','?')}"
    )


@tool
def save_draft(title: str, content: str, doc_type: str = "other", notes: str = "") -> str:
    """Save a writing draft for future reference.

    Args:
        title:    Short descriptive title for the draft
        content:  The full text content
        doc_type: One of: essay, report, email, cover_letter, article, proposal,
                  story, speech, other
        notes:    Optional context notes (e.g. target audience, purpose, deadline)

    Always confirm with the user before saving.
    """
    data = _load(_DRAFTS_FILE, {"drafts": []})
    now = datetime.now().isoformat(timespec="seconds")

    # Check for existing draft with same title (update)
    for draft in data["drafts"]:
        if draft["title"].lower() == title.lower():
            draft["content"]    = content
            draft["doc_type"]   = doc_type
            draft["notes"]      = notes
            draft["updated_at"] = now
            _save(_DRAFTS_FILE, data)
            return f"Draft **\"{title}\"** updated ({len(content.split())} words)."

    data["drafts"].append({
        "id":         str(uuid.uuid4())[:8],
        "title":      title,
        "content":    content,
        "doc_type":   doc_type,
        "notes":      notes,
        "created_at": now,
        "updated_at": now,
    })
    _save(_DRAFTS_FILE, data)
    return (
        f"Draft **\"{title}\"** saved — {len(content.split())} words, "
        f"type: {doc_type}."
    )


@tool
def list_drafts() -> str:
    """List all saved writing drafts with their titles, types, and word counts."""
    data = _load(_DRAFTS_FILE, {"drafts": []})
    drafts = data.get("drafts", [])
    if not drafts:
        return "No drafts saved yet. Use `save_draft()` to save your work."

    lines = [f"## Writing Drafts ({len(drafts)} saved)\n"]
    for d in sorted(drafts, key=lambda x: x.get("updated_at", ""), reverse=True):
        wc   = len(d.get("content", "").split())
        date = d.get("updated_at", "")[:10]
        note = f" — {d['notes'][:60]}" if d.get("notes") else ""
        lines.append(f"- **{d['title']}** ({d.get('doc_type','other')}, {wc} words, {date}){note}")
    return "\n".join(lines)


@tool
def read_draft(title: str) -> str:
    """Read a specific saved draft by title (case-insensitive partial match).

    Returns the full content of the draft plus its metadata.
    """
    data   = _load(_DRAFTS_FILE, {"drafts": []})
    drafts = data.get("drafts", [])
    title_lower = title.lower()

    # Exact match first, then partial
    match = next((d for d in drafts if d["title"].lower() == title_lower), None)
    if not match:
        match = next((d for d in drafts if title_lower in d["title"].lower()), None)
    if not match:
        available = ", ".join(f'"{d["title"]}"' for d in drafts[:8])
        return f"No draft matching \"{title}\" found. Available: {available or 'none'}"

    wc   = len(match.get("content", "").split())
    date = match.get("updated_at", "")[:10]
    note = f"\n**Notes:** {match['notes']}" if match.get("notes") else ""
    return (
        f"## {match['title']}\n"
        f"Type: {match.get('doc_type','other')} | {wc} words | Last edited: {date}{note}\n\n"
        f"---\n\n{match.get('content', '')}"
    )


WRITING_TOOLS = [
    analyze_writing,
    verify_humanization,
    calibrate_voice,
    get_voice_profile,
    save_draft,
    list_drafts,
    read_draft,
]
