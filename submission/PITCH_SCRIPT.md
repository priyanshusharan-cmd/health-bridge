# Three-minute pitch and recording script

This is a recording script, not a finished video or slide deck. Use synthetic data only. Do not use screenshare tooling automatically; the user will record the actual demo when ready.

## 0:00–0:25 — The problem
“A patient’s story often arrives in pieces: an old report, a referral, a few questions, and a language preference. The appointment is short. HealthBridge puts those pieces together so the patient and clinician can have a better-informed conversation.”

## 0:25–1:05 — Patient preparation
Show patient intake and upload demo-data/follow-up.txt. Open the record and its source text. Generate a visit brief. Explain that the brief selects excerpts, preserves source links and marks information for review. In the final competition video this generation must use the live AMD-hosted model. Do not substitute the source-only path and call it AMD inference.

## 1:05–1:45 — Clinician handoff
Enter as clinician, inspect a source, add a review note and approve. Publish clear instructions. Return as patient to show the approved status and instructions.

## 1:45–2:10 — What makes this useful
Change the intake. Show that the earlier brief is now outdated and cannot be approved as current. Open the audit trail. “We preserve the relationship between what the patient supplied, what the model selected, and what the clinician reviewed.”

## 2:10–2:40 — Technology and limits
Explain the real frontend/API/database flow and source-verification gate. Show actual model/GPU logs and measured latency only after obtaining them. Mention synthetic data, human review and the absence of autonomous diagnosis or prescribing. Translation is clinician-authored, not automatically medically validated.

## 2:40–3:00 — Next step
“Our next step is a small usability pilot: measure source-finding time, corrections and comprehension with qualified reviewers. We are building for a better handoff, with the clinician in control.”

## Six-slide outline for the final deck
1. HealthBridge — connected patient information, reviewed by people.
2. The problem — scattered records and limited appointment time.
3. The care handoff — intake, records, brief, review, instructions.
4. Trust — source links, visible unknowns, version-aware approval.
5. Working technology — actual architecture and measured AMD evidence.
6. Next step — usability pilot and honest current limits.

Do not publish a slide claiming AMD execution until it has occurred. Final deck, cover and video are still required submission assets.
