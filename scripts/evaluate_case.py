"""Synthetic Case Evaluation Utility.

Compares manual vs assisted visit preparation on synthetic test fixtures.
Measures fact coverage, review corrections, and processing time under
controlled evaluation criteria. Never fabricates claims of clinical efficacy.
"""

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import sys

# Ensure backend can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.brief_service import build_structured_brief


SYNTHETIC_FIXTURES = [
    {
        "id": "synthetic-long-consult",
        "title": "Long Consultation Report",
        "file": "demo-data/long-consultation-report.txt",
    },
    {
        "id": "synthetic-allergy-conflict",
        "title": "Discharge Summary with Allergy Note",
        "file": "demo-data/allergy-conflict-discharge.txt",
    },
    {
        "id": "synthetic-follow-up",
        "title": "Follow-up Visit Note",
        "file": "demo-data/follow-up.txt",
    },
]

TARGET_FACTS_CHECKLIST = [
    {"fact": "Prior coronary stent (2022)", "source_type": "record", "terms": ["stent", "2022"]},
    {"fact": "Medication: Atorvastatin 40mg daily", "source_type": "record", "terms": ["atorvastatin", "40mg"]},
    {"fact": "Medication: Metformin 500mg BID", "source_type": "record", "terms": ["metformin", "500mg"]},
    {"fact": "Reported Allergy: Penicillin in intake", "source_type": "intake", "terms": ["penicillin", "swelling"]},
    {"fact": "Conflicting Allergy Statement in discharge note", "source_type": "record", "terms": ["allergies", "differ"]},
    {"fact": "Recent concern: Exertional shortness of breath", "source_type": "intake", "terms": ["shortness", "breath"]},
    {"fact": "Recent blood pressure: 138/86 mmHg", "source_type": "record", "terms": ["138/86"]},
]


def evaluate_assisted(root: Path):
    available_records = []
    extractions = {}
    for fixture in SYNTHETIC_FIXTURES:
        p = root / fixture["file"]
        if p.is_file():
            text = p.read_text(encoding="utf-8")
            rec = {
                "id": fixture["id"],
                "title": fixture["title"],
                "text": text,
                "created_at": "2026-10-14T00:00:00Z",
            }
            available_records.append(rec)
            extractions[fixture["id"]] = {
                "record_id": fixture["id"],
                "version": 1,
                "pages_json": json.dumps([{"page_number": 1, "length": len(text), "start_offset": 0, "end_offset": len(text)}]),
                "method": "direct_text",
                "warnings": "[]",
            }

    intake = {
        "id": "synthetic-intake",
        "reason": "Exertional shortness of breath when walking uphill for two weeks.",
        "duration": "Two weeks",
        "allergies": "Penicillin (developed rash and facial swelling in 2018)",
        "questions": "Could this shortness of breath be related to my heart stent from 2022?",
    }

    start = time.perf_counter()
    brief_data = build_structured_brief(
        patient_id="synthetic-eval-patient",
        intake=intake,
        available_records=available_records,
        extractions_by_record=extractions,
        selected_record_ids=None,
        ai_mode="extractive",
        model_name="source_only",
        clinical_rev="eval-rev-1",
        latency_ms=0,
    )
    elapsed_seconds = round(time.perf_counter() - start, 3)

    # Fact detection check in assisted brief
    full_brief_text = json.dumps(brief_data.get("sections", {})) + " " + json.dumps(brief_data.get("uncertainties", []))
    detected_record_facts = []
    detected_intake_facts = []
    missing_facts = []

    for item in TARGET_FACTS_CHECKLIST:
        fact_name = item["fact"]
        terms = item["terms"]
        matches = sum(1 for t in terms if t.lower() in full_brief_text.lower())
        if matches == len(terms):
            if item["source_type"] == "record":
                detected_record_facts.append(fact_name)
            else:
                detected_intake_facts.append(fact_name)
        else:
            missing_facts.append(fact_name)

    uncertainties = brief_data.get("uncertainties", [])

    return {
        "mode": "assisted_source_only",
        "execution_seconds": elapsed_seconds,
        "total_target_facts": len(TARGET_FACTS_CHECKLIST),
        "detected_record_facts": detected_record_facts,
        "detected_intake_facts": detected_intake_facts,
        "missing_facts": missing_facts,
        "uncertainties_flagged": len(uncertainties),
        "coverage": brief_data.get("coverage", {}),
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate synthetic case preparation")
    parser.add_argument("--output", default="submission/evaluation-template.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    assisted_result = evaluate_assisted(root)

    # Structured comparison template for human evaluators
    report = {
        "evaluation_date": datetime.now(timezone.utc).isoformat(),
        "disclaimer": (
            "Synthetic data evaluation only. Not a clinical trial or proof of diagnostic "
            "efficacy. Manual timings must be recorded by human clinicians under controlled conditions."
        ),
        "test_scenario": {
            "name": "Synthetic Multi-Document Cardiology Intake",
            "fixtures": [f["title"] for f in SYNTHETIC_FIXTURES],
            "target_checklist": TARGET_FACTS_CHECKLIST,
        },
        "assisted_system_run": assisted_result,
        "human_evaluator_template": {
            "instructions": (
                "Have a qualified clinician review the same synthetic records manually and record "
                "preparation time, missed facts, and error corrections before and after using HealthBridge."
            ),
            "manual_baseline_protocol": {
                "evaluator_role": "Clinician or medical resident",
                "sample_cases": 1,
                "recorded_manual_time_seconds": None,
                "manual_missed_facts": [],
                "manual_incorrect_notes": [],
            },
            "assisted_protocol": {
                "recorded_review_time_seconds": None,
                "clinician_corrections_required": None,
                "clarifications_initiated": None,
                "final_instruction_edits": None,
            },
            "limitations": [
                "Small sample size (synthetic case studies)",
                "Clinician familiarity with UI affects review speed",
                "Quote matching does not evaluate clinical nuance or omitted unquoted context",
                "Local inference latency varies with hardware",
            ],
        },
    }

    out_path = root / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved evaluation benchmark template to {out_path}")


if __name__ == "__main__":
    main()
