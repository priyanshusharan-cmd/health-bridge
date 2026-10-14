# HealthBridge Verification Report

**Date:** 14 October 2026  
**Scope:** Phase A1 through Phase C2 of the synthetic healthcare handoff prototype.

---

## 1. Automated Verification Results

| Area | Check / Command | Result | Evidence / Details |
| --- | --- | --- | --- |
| Frontend TypeScript & Build | `npm --prefix frontend run build` | **Passed** | Clean build (`tsc -b && vite build`) in 1.89s; 0 TypeScript errors. |
| Frontend Behavior & Localization | `npm --prefix frontend test` | **23 passed** | 23/23 tests passed (305ms). Includes 100% UI key parity in Hindi (`hi`) and Kannada (`kn`), dialog context isolation, save/refresh retry semantics, session expiry, and storage fallback. |
| Backend Workflows & Security | `PYTHONPATH=backend .venv/bin/pytest backend/tests -q` | **41 passed** | 41/41 tests passed (8.6s). Covers authorization, durable upload queue leases, extraction provenance, conflict detection, instruction versions, patient acknowledgement, and assignment unlinking. |
| Real HTTP API Integration | `node frontend/tests/connection.mjs` | **Passed** | Exercises frontend API client over loopback HTTP against ephemeral FastAPI/SQLite instance. Verifies full flow: intake, upload, structured brief, clarification thread, versioned instructions, and invitation unlinking. |
| Docker Compose Configuration | `docker compose config --quiet` | **Valid** | Multi-service orchestration syntax verified. |
| Local Submission Preflight | `.venv/bin/python scripts/release_check.py` | **Passed (`local_ready: true`)** | Local artifacts verified; external gates explicitly identified as requiring human evidence. |
| Synthetic Case Evaluation | `.venv/bin/python scripts/evaluate_case.py` | **Passed** | Evaluated multi-document synthetic case; exported structured protocol template to `submission/evaluation-template.json`. |

---

## 2. Failure Behaviors & Security Boundaries Verified

The following edge cases and negative pathways are covered by automated tests to ensure graceful degradation:

1. **Unsupported Model Quotes & Fallback**:
   - Model outputs containing hallucinated quotes, non-matching whitespace, or malformed JSON are rejected by `backend/app/ai.py`.
   - The brief service falls back to source-only deterministic extraction without inventing synthetic facts or pretending AI succeeded (`backend/tests/test_ai_boundaries.py`).
2. **Authorization & Tenant Isolation**:
   - Unauthenticated callers receive `401 Unauthorized`.
   - Unassigned clinicians attempting to access patient clinical workspaces receive `403 Forbidden`.
   - Patients attempting clinician-only endpoints (e.g. approving a brief, resolving a clarification, or publishing instructions) receive `403 Forbidden` (`backend/tests/test_workflow.py`).
3. **Stale Revision Conflict (409 Conflict)**:
   - When source records or intake are modified, the patient's `clinical_revision` increments monotonically.
   - Any clinician attempt to approve an outdated brief revision or publish instructions bound to a superseded revision is rejected with `409 Conflict` and requires a data refresh.
4. **Tombstone Dependency Invalidation**:
   - Scoped deletion of a record (`DELETE /api/records/{id}`) records a tombstone and triggers `invalidate_briefs()`.
   - Any existing brief citing the withdrawn record is marked as `outdated`, preventing broken citations from being presented as verified evidence.
5. **Acknowledged-Save & Refresh Retry Semantics**:
   - In the frontend client, if a mutation succeeds on the backend but the subsequent background refresh fails, the UI preserves the saved state and surfaces a retryable "Saved; refresh failed" action rather than prompting the user to repeat the mutation (`frontend/tests/behavior.test.mjs`).

---

## 3. Manual QA Checklist & Verification Status

The following table distinguishes automated verifications from checks requiring human physical execution or external hardware:

| Surface / Flow | Mode | Status | Notes / Limitations |
| --- | --- | --- | --- |
| Patient Intake & Upload | Local / Browser | **Verified (API/Unit)** | Fully verified via HTTP integration and pytest; physical browser click QA pending human reviewer. |
| Visit Preparation Brief v2 | Local / Browser | **Verified (API/Unit)** | 4 structured sections, coverage metrics, and conflict detection verified across synthetic fixtures. |
| Clarification Lifecycle | Local / Browser | **Verified (API/Unit)** | Clinician question, patient response, and clinician-only resolution verified via tests. |
| Instruction Versioning & Acknowledgment | Local / Browser | **Verified (API/Unit)** | Immutable versioning (`v1`, `v2`), override note preservation, and version-bound acknowledgement verified. |
| Regional Interface Localization | Automated Text | **Verified (Unit)** | 100% dictionary key parity verified for English, Hindi, and Kannada. Note: Does not substitute for clinical translation review. |
| Responsive Layout & Keyboard Access | Design System | **Verified (Static)** | Semantic HTML, accessible form controls, and ARIA dialogs implemented. |
| Mobile Touch / Native Trackpad Gestures | Physical Device | **Not Performed** | Requires physical device testing; browser automation is prohibited. |
| Real AMD ROCm GPU Inference | Remote / Hardware | **Not Performed** | Requires live AMD host access. Source-only mode runs locally without fabricated hardware claims. |

---

## 4. Controlled Benchmark Protocol (Manual vs. Assisted)

To measure clinical preparation utility without equating model latency to clinical accuracy, run:

```sh
.venv/bin/python scripts/evaluate_case.py --output submission/evaluation-template.json
```

### Protocol Guidelines:
- **Baseline (Manual)**: Evaluator reviews raw synthetic documents (`demo-data/long-consultation-report.txt` and `demo-data/allergy-conflict-discharge.txt`) and records time spent, omissions, and missed allergy discrepancies.
- **Assisted (HealthBridge)**: Evaluator uses the generated visit brief with structured sections and highlighted uncertainties. Measure review time, clarification resolution time, and final instruction adjustments.
- **Reporting Rule**: Never equate backend response latency with proven clinician time saved. Report sample size, evaluator qualifications, and error rates transparently.
