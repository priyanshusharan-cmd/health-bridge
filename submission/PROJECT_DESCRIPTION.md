# HealthBridge

## Short description
HealthBridge brings patient concerns and scattered records into a source-linked visit brief, then helps clinicians review the information and share clear next steps. Built for a connected, human-reviewed care handoff.

## Long description
Patients often bring several documents, unanswered questions and information in different languages to a short appointment. HealthBridge helps patients and clinicians prepare for that conversation together.

A patient records their concerns in their own words and adds synthetic reports or visit notes. The application extracts document text, organizes records into a timeline and prepares a visit brief with links to its sources. A clinician checks the evidence, records corrections and approves or flags the brief. When the patient adds new information, the old brief becomes outdated. The clinician can publish original, plain-language and reviewed translated instructions, while the patient can print their brief for another appointment.

The interface supports light and dark modes and the interface in English, Hindi and Kannada, plus 28 region-grouped care-content languages for reviewed instructions. Data flows through a real React/TypeScript frontend, FastAPI backend and persistent MongoDB database (SQLite for offline development). The configurable model adapter supports an open model served through vLLM on AMD ROCm; source-only mode keeps local development free and explicitly shows that no model was used.

HealthBridge does not diagnose, prescribe or independently validate medical advice. Model-selected excerpts must match source text, uncertainty stays visible, and care decisions remain with clinicians. The current prototype uses synthetic data only.

## Submission metadata
Track: Health and Wellbeing
Technology tags: React, TypeScript, Python, FastAPI, MongoDB, SQLite, OCR; add AMD ROCm, vLLM and the actual model only after the live run is verified.
Repository URL: pending publication
Application URL: pending deployment
Video URL: pending recording
AMD evidence: pending real runtime access

## Originality and work disclosure
Project preparation and implementation began on October 3, 2026, before the October 12 kickoff. Disclose this in the submission and obtain organizer confirmation that this work is eligible. Keep an accurate record of work completed during the event. Application source is MIT licensed; dependency/model licenses remain their own.

## Business hypothesis — not a measured outcome
Initial users: outpatient patients and the clinicians reviewing their records.
Proposed value: less searching for documents, more visible missing information, and a traceable handoff.
Pilot evaluation: time to locate relevant sources, correction rate, completeness of the visit brief, and patient comprehension of reviewed instructions. No time-saved or clinical-outcome claim has been measured yet.
