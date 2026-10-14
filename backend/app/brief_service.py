"""Structured visit brief service with schema 2.0, visible uncertainty, coverage, and conflict surfacing."""
import json
import re
from typing import Any

from .ai import preserve_sentence_context

SCHEMA_VERSION = "2.0"
DEFAULT_RECORD_LIMIT = 12
MAX_RECORD_CHAR_BUDGET = 2400

ALLERGY_MENTION_PATTERN = re.compile(
    r'\b(allergy|allergic|allergies|penicillin|amoxicillin|sulfa|aspirin|nsaid|reaction|anaphylaxis|rash)\b',
    re.IGNORECASE
)
CONFIRMATION_PATTERN = re.compile(
    r'\b(needs confirmation|confirm|differ|differs|discrepancy|unconfirmed|patient-reported)\b',
    re.IGNORECASE
)
NEGATION_ALLERGY_PATTERN = re.compile(
    r'\b(no known allergies|nka|nkda|denies allergies|no allergies|denied allergies)\b',
    re.IGNORECASE
)

def select_passages_across_document(text: str, pages_info: list[dict] | None = None, max_chars: int = MAX_RECORD_CHAR_BUDGET) -> tuple[str, list[dict], bool]:
    """Select representative excerpts across early, middle, and later parts of the document.
    Ensures late-document facts (such as on later pages) are included rather than silently truncated."""
    if not text.strip():
        return "", [], False

    is_shortened = len(text) > max_chars
    passages: list[dict] = []

    # If we have structured page blocks from OCR or PDF
    if pages_info and len(pages_info) > 1:
        chars_per_page = max(300, max_chars // len(pages_info))
        offset = 0
        bounded_parts = []
        for page_block in pages_info:
            page_num = page_block.get('page_number', 1)
            page_len = page_block.get('length', 0)
            page_text = text[offset:offset + page_len]
            if page_text.strip():
                # Extract first meaningful chunk of this page
                chunk = page_text.strip()[:chars_per_page].strip()
                passages.append({
                    "quote": chunk,
                    "page": page_num,
                    "start_offset": offset,
                    "end_offset": offset + len(chunk)
                })
                bounded_parts.append(chunk)
            offset += page_len
        bounded_text = "\n---\n".join(bounded_parts)
        return bounded_text, passages, is_shortened

    # Plain text without explicit page breakdown:
    if not is_shortened:
        passages.append({
            "quote": text.strip(),
            "page": 1,
            "start_offset": 0,
            "end_offset": len(text)
        })
        return text, passages, False

    # Document is longer than max_chars. Sample from beginning, middle, and end so later facts are preserved
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if len(paragraphs) > 1:
        if len(paragraphs) <= 3:
            selected_parts = paragraphs
        else:
            mid_idx = len(paragraphs) // 2
            selected_parts = [paragraphs[0], paragraphs[mid_idx], paragraphs[-1]]
    else:
        # A single continuous block of text without newlines
        third = len(text) // 3
        part1 = text[:min(800, third)].strip()
        part2 = text[third:third + min(800, third)].strip()
        part3 = text[-min(800, third):].strip()
        selected_parts = [part1, part2, part3]

    offset = 0
    bounded_chunks = []
    for idx_part, part in enumerate(selected_parts):
        if part:
            chunk = part[-750:].strip() if (idx_part == len(selected_parts) - 1 and len(part) > 750) else part[:750].strip()
            idx = text.find(chunk, offset)
            if idx == -1:
                idx = text.find(chunk)
            if idx == -1:
                idx = offset
            start_off = idx
            end_off = idx + len(chunk)
            offset = end_off
            passages.append({
                "quote": chunk,
                "page": 1,
                "start_offset": start_off,
                "end_offset": end_off
            })
            bounded_chunks.append(chunk)

    bounded_text = "\n\n".join(bounded_chunks)
    return bounded_text, passages, True


def detect_conflicts_and_uncertainties(
    intake: dict | None,
    records: list[dict],
    extractions_by_record: dict[str, dict]
) -> list[dict]:
    """Identify missing information, conflicting statements across sources, and extraction warnings."""
    uncertainties = []

    # 1. Missing intake
    if not intake:
        uncertainties.append({
            "id": "unc-missing-intake",
            "kind": "missing_information",
            "description": "Patient intake form has not been submitted.",
            "citations": [],
            "status": "unresolved"
        })
    else:
        intake_id = intake.get("id") or "intake"
        # 2. Missing allergies in intake: never convert missing allergies into 'no allergies'
        allergies_val = (intake.get("allergies") or "").strip()
        if not allergies_val or allergies_val.lower() in ("not provided", "none"):
            if not allergies_val or allergies_val.lower() == "not provided":
                uncertainties.append({
                    "id": "unc-missing-allergies",
                    "kind": "missing_information",
                    "description": "Patient-reported allergy information was not provided in intake. Confirm allergy history during visit.",
                    "citations": [{
                        "source_id": intake_id,
                        "source_version": 1,
                        "page": 1,
                        "start_offset": 0,
                        "end_offset": len(allergies_val),
                        "quote": "Allergies: Not provided"
                    }],
                    "status": "unresolved"
                })

        # 3. Missing medications in intake
        meds_val = (intake.get("medications") or "").strip()
        if not meds_val or meds_val.lower() in ("not provided", ""):
            uncertainties.append({
                "id": "unc-missing-meds",
                "kind": "missing_information",
                "description": "Patient-reported medication list was not provided in intake. Confirm current medications during visit.",
                "citations": [{
                    "source_id": intake_id,
                    "source_version": 1,
                    "page": 1,
                    "start_offset": 0,
                    "end_offset": len(meds_val),
                    "quote": "Medications: Not provided"
                }],
                "status": "unresolved"
            })

    # 4. Conflicting allergy or medication statements across intake and records
    intake_allergy_text = (intake.get("allergies") or "") if intake else ""
    allergy_sources: list[dict] = []

    if intake and ALLERGY_MENTION_PATTERN.search(intake_allergy_text):
        allergy_sources.append({
            "source_id": intake.get("id") or "intake",
            "title": "Patient intake",
            "quote": intake_allergy_text.strip(),
            "has_negation": bool(NEGATION_ALLERGY_PATTERN.search(intake_allergy_text)),
            "needs_confirmation": bool(CONFIRMATION_PATTERN.search(intake_allergy_text))
        })

    for r in records:
        r_text = r.get("text", "")
        if ALLERGY_MENTION_PATTERN.search(r_text):
            # Extract sentence containing allergy
            for line in r_text.split("\n"):
                if ALLERGY_MENTION_PATTERN.search(line):
                    allergy_sources.append({
                        "source_id": r["id"],
                        "title": r.get("title", "Medical record"),
                        "quote": line.strip()[:300],
                        "has_negation": bool(NEGATION_ALLERGY_PATTERN.search(line)),
                        "needs_confirmation": bool(CONFIRMATION_PATTERN.search(line))
                    })
                    break

    # If there are multiple sources discussing allergies and any discrepancy or confirmation note exists:
    if len(allergy_sources) >= 2 or any(s["needs_confirmation"] for s in allergy_sources):
        citations = []
        for s in allergy_sources[:3]:
            citations.append({
                "source_id": s["source_id"],
                "source_version": 1,
                "page": 1,
                "start_offset": 0,
                "end_offset": len(s["quote"]),
                "quote": s["quote"]
            })
        if citations:
            uncertainties.append({
                "id": "unc-allergy-conflict",
                "kind": "conflicting_sources",
                "description": "Statements differ; confirm with a clinician.",
                "citations": citations,
                "status": "unresolved"
            })

    # 5. Extraction warnings from record extractions
    for r in records:
        ext = extractions_by_record.get(r["id"])
        if ext:
            raw_warnings = ext.get("warnings")
            warnings_list = []
            if isinstance(raw_warnings, str):
                try:
                    warnings_list = json.loads(raw_warnings)
                except Exception:
                    if raw_warnings.strip():
                        warnings_list = [raw_warnings.strip()]
            elif isinstance(raw_warnings, list):
                warnings_list = raw_warnings

            for w in warnings_list:
                uncertainties.append({
                    "id": f"unc-ext-{r['id']}-{len(uncertainties)}",
                    "kind": "extraction_warning",
                    "description": f"Document extraction warning for '{r.get('title', 'record')}': {w}",
                    "citations": [{
                        "source_id": r["id"],
                        "source_version": ext.get("version", 1),
                        "page": 1,
                        "start_offset": 0,
                        "end_offset": min(len(r.get("text", "")), 200),
                        "quote": r.get("title", "Record extraction warning")
                    }],
                    "status": "unresolved"
                })

    return uncertainties


def build_sections(
    intake: dict | None,
    records: list[dict],
    record_passages: dict[str, list[dict]],
    uncertainties: list[dict]
) -> list[dict]:
    """Construct deterministic sections with attribution and citations."""
    sections = []

    # Section 1: Reason for visit & questions
    reason_items = []
    if intake:
        intake_id = intake.get("id") or "intake"
        reason_text = intake.get("reason", "").strip() or "Not provided"
        reason_items.append({
            "text": f"Reason for visit: {reason_text}",
            "attribution": "patient_reported",
            "citations": [{
                "source_id": intake_id,
                "source_version": 1,
                "page": 1,
                "start_offset": 0,
                "end_offset": len(reason_text),
                "quote": reason_text
            }] if reason_text != "Not provided" else []
        })

        dur_text = intake.get("duration", "").strip() or "Not provided"
        reason_items.append({
            "text": f"Duration: {dur_text}",
            "attribution": "patient_reported",
            "citations": [{
                "source_id": intake_id,
                "source_version": 1,
                "page": 1,
                "start_offset": 0,
                "end_offset": len(dur_text),
                "quote": dur_text
            }] if dur_text != "Not provided" else []
        })

        q_text = intake.get("questions", "").strip() or "Not provided"
        reason_items.append({
            "text": f"Questions to discuss: {q_text}",
            "attribution": "patient_reported",
            "citations": [{
                "source_id": intake_id,
                "source_version": 1,
                "page": 1,
                "start_offset": 0,
                "end_offset": len(q_text),
                "quote": q_text
            }] if q_text != "Not provided" else []
        })
    else:
        reason_items.append({
            "text": "Patient intake has not been submitted.",
            "attribution": "patient_reported",
            "citations": []
        })

    sections.append({
        "key": "reason_questions",
        "label": "Reason for visit & questions",
        "items": reason_items
    })

    # Section 2: Patient-reported medications & allergies
    med_allergy_items = []
    if intake:
        intake_id = intake.get("id") or "intake"
        meds_text = intake.get("medications", "").strip()
        if meds_text and meds_text.lower() != "not provided":
            med_allergy_items.append({
                "text": f"Medications: {meds_text}",
                "attribution": "patient_reported",
                "citations": [{
                    "source_id": intake_id,
                    "source_version": 1,
                    "page": 1,
                    "start_offset": 0,
                    "end_offset": len(meds_text),
                    "quote": meds_text
                }]
            })
        else:
            med_allergy_items.append({
                "text": "Medications: Not provided by patient",
                "attribution": "patient_reported",
                "citations": []
            })

        allergies_text = intake.get("allergies", "").strip()
        if allergies_text and allergies_text.lower() != "not provided":
            med_allergy_items.append({
                "text": f"Allergies: {allergies_text}",
                "attribution": "patient_reported",
                "citations": [{
                    "source_id": intake_id,
                    "source_version": 1,
                    "page": 1,
                    "start_offset": 0,
                    "end_offset": len(allergies_text),
                    "quote": allergies_text
                }]
            })
        else:
            med_allergy_items.append({
                "text": "Allergies: Not provided by patient",
                "attribution": "patient_reported",
                "citations": []
            })
    else:
        med_allergy_items.append({
            "text": "Medications: Not provided by patient",
            "attribution": "patient_reported",
            "citations": []
        })
        med_allergy_items.append({
            "text": "Allergies: Not provided by patient",
            "attribution": "patient_reported",
            "citations": []
        })

    sections.append({
        "key": "medications_allergies",
        "label": "Patient-reported medications & allergies",
        "items": med_allergy_items
    })

    # Section 3: Recorded medical history & findings
    history_items = []
    for r in records:
        passages = record_passages.get(r["id"], [])
        for p in passages:
            # Preserving sentence context / negation
            safe_quote = preserve_sentence_context(p["quote"], r.get("text", ""))
            history_items.append({
                "text": f"[{r.get('kind', 'Record')}] {safe_quote}",
                "attribution": "document_recorded",
                "citations": [{
                    "source_id": r["id"],
                    "source_version": 1,
                    "page": p.get("page", 1),
                    "start_offset": p.get("start_offset", 0),
                    "end_offset": p.get("end_offset", len(safe_quote)),
                    "quote": safe_quote
                }]
            })

    sections.append({
        "key": "recorded_history",
        "label": "Recorded medical history & findings",
        "items": history_items
    })

    # Section 4: Information to confirm & uncertainties
    confirm_items = []
    for unc in uncertainties:
        confirm_items.append({
            "text": unc["description"],
            "attribution": "clinician_reviewed",
            "citations": unc["citations"]
        })

    sections.append({
        "key": "information_to_confirm",
        "label": "Information to confirm",
        "items": confirm_items
    })

    return sections


def build_structured_brief(
    patient_id: str,
    intake: dict | None,
    available_records: list[dict],
    extractions_by_record: dict[str, dict],
    selected_record_ids: list[str] | None,
    ai_mode: str,
    model_name: str,
    clinical_rev: str,
    latency_ms: int = 0
) -> dict:
    """Constructs complete schema 2.0 brief with backward-compatible evidence, sources, and coverage."""
    # 1. Determine included vs excluded records
    if selected_record_ids is not None:
        selected_set = set(selected_record_ids)
        included_records = [r for r in available_records if r["id"] in selected_set]
        excluded_records = [r for r in available_records if r["id"] not in selected_set]
        excluded_sources = [
            {"id": r["id"], "title": r.get("title", "Record"), "reason": "Not selected by clinician."}
            for r in excluded_records
        ]
    else:
        included_records = available_records[:DEFAULT_RECORD_LIMIT]
        excluded_records = available_records[DEFAULT_RECORD_LIMIT:]
        excluded_sources = [
            {"id": r["id"], "title": r.get("title", "Record"), "reason": f"Exceeds default limit of {DEFAULT_RECORD_LIMIT} records; available for clinician selection."}
            for r in excluded_records
        ]

    # 2. Extract representative passages across entire documents
    record_passages: dict[str, list[dict]] = {}
    shortened_sources: list[dict] = []
    for r in included_records:
        ext = extractions_by_record.get(r["id"])
        pages_info = None
        if ext and ext.get("pages_json"):
            try:
                pages_info = json.loads(ext["pages_json"])
            except Exception:
                pages_info = None
        bounded_text, passages, is_shortened = select_passages_across_document(r.get("text", ""), pages_info)
        record_passages[r["id"]] = passages
        if is_shortened:
            shortened_sources.append({
                "id": r["id"],
                "title": r.get("title", "Record"),
                "character_count": len(r.get("text", "")),
                "truncated_to": MAX_RECORD_CHAR_BUDGET
            })

    # 3. Detect uncertainties & conflicts
    uncertainties = detect_conflicts_and_uncertainties(intake, included_records, extractions_by_record)

    # 4. Build structured sections
    sections = build_sections(intake, included_records, record_passages, uncertainties)

    # 5. Build backward-compatible evidence list
    legacy_evidence: list[dict] = []
    if intake and intake.get("reason"):
        legacy_evidence.append({
            "source_id": intake.get("id") or "intake",
            "quote": intake["reason"].strip()
        })
    for r in included_records:
        passages = record_passages.get(r["id"], [])
        for p in passages:
            legacy_evidence.append({
                "source_id": r["id"],
                "quote": p["quote"]
            })

    # 6. Legacy sources list
    sources = []
    if intake:
        sources.append({"id": intake.get("id") or "intake", "title": "Patient intake"})
    for r in included_records:
        sources.append({"id": r["id"], "title": r.get("title", "Record")})

    # 7. Coverage
    coverage = {
        "available_records": len(available_records),
        "included_records": len(included_records),
        "excluded_sources": excluded_sources,
        "shortened_sources": shortened_sources
    }

    # 8. Processing metadata
    processing = {
        "mode": ai_mode,
        "model": model_name,
        "policy_version": "1.0",
        "latency_ms": latency_ms
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "source_revision": clinical_rev,
        "sections": sections,
        "uncertainties": uncertainties,
        "coverage": coverage,
        "evidence": legacy_evidence,
        "sources": sources,
        "intake": intake,
        "note": "",
        "latency_ms": latency_ms,
        "notice": (
            "Selected source excerpts for review, not a complete record. "
            f"Up to {DEFAULT_RECORD_LIMIT} documents are included; long sources may be shortened. "
            "This is not a diagnosis or treatment plan."
        ),
        "processing": processing
    }
