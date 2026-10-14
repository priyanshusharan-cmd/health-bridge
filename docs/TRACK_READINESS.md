# Health and Wellbeing Track Alignment

HealthBridge focuses on preparing a patient and clinician for one visit, with a traceable, human-in-the-loop handoff.

---

## 1. Track Requirements & Implementation Alignment

| Track Expectation | Implemented Prototype Behavior | Evidence & Verification | Honest Remaining Boundaries |
| --- | --- | --- | --- |
| **Defined Patient or Staff Need** | Intake in patient's words, durable document upload queue, extraction provenance, and structured visit brief organized into 4 clinician-ready sections. | `backend/tests/test_workflow.py`, `backend/tests/test_brief_schema.py` | Built for synthetic demonstration; does not replace complete hospital Electronic Health Record (EHR). |
| **Realistic Input to Result** | Upload TXT/PDF/images, bounded extraction/OCR, schema 2.0 visit brief, clarification threads, versioned instruction publication, and patient acknowledgement. | Real client-to-API HTTP integration (`frontend/tests/connection.mjs`), 41 backend tests, 23 frontend tests. | Pre-seeded synthetic test data; real clinical records must not be accepted without Stage D compliance. |
| **Strict Model & Evidence Boundaries** | Model output quotes must exist verbatim in the source documents. Hallucinated excerpts, altered whitespace, or malformed JSON are strictly rejected. | `backend/tests/test_ai_boundaries.py` | Quote matching does not guarantee clinical factuality; qualified human review is always required. |
| **Visible Uncertainty & Conflicts** | Discrepancies between intake and records (e.g. conflicting penicillin allergies) are surfaced as prominent uncertainty badges with source citations. | `backend/app/brief_service.py`, `backend/tests/test_brief_schema.py` | System never attempts autonomous medical reconciliation of conflicting records. |
| **Human Takeover & Control** | Only assigned clinicians can approve/flag briefs, resolve clarification requests, or publish instructions. Stale versions reject modifications with `409 Conflict`. | `backend/tests/test_workflow.py`, `backend/app/review_service.py` | Clinician overrides require an explicit recorded clinical justification. |
| **High-Risk Decisions** | No autonomous diagnosis, triage scoring, medication prescribing, or machine-generated medical advice. | Verified architecture; strictly extractive evidence selection with clinician-authored instructions. | Preserves clinician liability and decision autonomy. |
| **Sensitive Information & Privacy** | Scoped record deletion with tombstone auditing, authenticated portable care summary export, and HttpOnly session cookies. | `backend/tests/test_workflow.py`, `backend/app/main.py` | Shared demo identities; production requires Stage D workstream (verified identity, HIPAA/GDPR policies). |
| **Accessibility & Regional Languages** | Accessible design tokens, responsive layouts, 3 complete UI languages (English, Hindi, Kannada), and 28 regional care-content languages. | `frontend/tests/localization.test.mjs` (100% key parity) | UI localization does not automatically translate patient medical records. Clinical translation must be reviewed by qualified clinicians. |
| **Measurable Improvement** | Case evaluation utility (`scripts/evaluate_case.py`) records target fact coverage, uncertainties, and execution latency. | Generated template in `submission/evaluation-template.json` | Sample size limitations; human timing trials must be conducted under controlled clinical conditions. |
| **Meaningful AMD Use** | OpenAI-compatible open-model adapter configured for vLLM with ROCm on AMD hardware. | Adapter implemented in `backend/app/ai.py`; benchmark harness in `scripts/benchmark_model.py`. | Real AMD ROCm execution logs and hardware attestation remain an external dependency. |

---

## 2. Controlled Evaluation Protocol

Rather than claiming unverified time savings or diagnostic accuracy, the project provides a structured protocol template:

```sh
.venv/bin/python scripts/evaluate_case.py --output submission/evaluation-template.json
```

- **Objective:** Compare manual document review against HealthBridge-assisted review using the same synthetic multi-document case (`demo-data/long-consultation-report.txt` and `demo-data/allergy-conflict-discharge.txt`).
- **Metrics Measured:**
  1. Target clinical facts identified vs. missed.
  2. Conflicting statements detected (e.g. allergy contradiction).
  3. Total preparation and review time in seconds.
  4. Number of clarification items raised and resolved.
- **Limitation:** Small sample size; evaluator familiarity with clinical software affects speed.
