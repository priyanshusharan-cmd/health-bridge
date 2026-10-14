# HealthBridge Demo Guide

A 3-minute reproducible demonstration script for the synthetic care handoff prototype.

---

## Prerequisites
- Start backend: `.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload`
- Start frontend: `npm --prefix frontend run dev`
- Open `http://127.0.0.1:5173`
- Pre-seeded synthetic credentials available via demo login buttons:
  - **Patient:** `patient@healthbridge.demo` / `BridgeDemo2026!`
  - **Clinician:** `doctor@healthbridge.demo` / `BridgeDemo2026!`

---

## 7-Step Demonstration Scenario

### 1. Patient Intake & Regional Navigation
- Log in using the **Patient** quick-login button.
- Point out the synthetic data disclaimer and privacy controls.
- Switch the header interface language selector between English, Hindi, and Kannada. Note clearly: *Interface localization adapts UI labels and date formats; it does not fabricate machine translations of patient medical records.*
- Open Intake and enter or edit the reason for visit: *"Exertional shortness of breath when walking uphill for two weeks."* Save changes. Notice the immediate save state and refreshed timeline.

### 2. Document Upload & Extraction Provenance
- In the Records section, upload `demo-data/follow-up.txt` or `demo-data/allergy-conflict-discharge.txt`.
- Observe the upload queue state and processing feedback.
- Open the record viewer: inspect the original file download button, extracted text, and extraction provenance (direct text / OCR method, page count, and status).
- Point out that clinicians can submit corrections with an explicit reason if an extraction discrepancy exists.

### 3. Structured Visit Brief & Visible Uncertainty
- Navigate to **Visit Preparation** and generate the brief.
- Highlight the **Schema 2.0 structured sections**:
  1. *Reason for visit & questions* (with patient intake citations)
  2. *Patient-reported medications & allergies*
  3. *Recorded clinical history & timeline*
  4. *Information to confirm during visit*
- Point out the **Coverage metrics** (number of available records vs. included sources).
- Highlight the **Active Uncertainty badge**: The system detected a conflicting allergy statement (e.g., patient intake reports penicillin allergy, while a discharge record states "no known drug allergies"). *The system surfaces the discrepancy prominently with source links rather than attempting autonomous reconciliation.*

### 4. Clinician Review & Clarification Thread
- Sign out and log in using the **Clinician** quick-login button.
- Select patient **Asha Rao** from the assigned patient list.
- Navigate to Visit Preparation: inspect the citations linking directly to underlying records.
- Initiate a **Clarification request** regarding the allergy discrepancy: *"Please confirm whether the reaction to penicillin involved hives, difficulty breathing, or rash."*
- Switch back to the Patient view: notice the pending clarification alert. The patient types their response: *"Severe hives and facial swelling after amoxicillin in 2018."*
- Return to Clinician view: mark the clarification as **Resolved**.

### 5. Instruction Publication & Versioning
- On the Clinician Instructions tab, author visit instructions:
  - Clinical instructions: *"Hold NSAIDs. Schedule treadmill stress test. Referral to cardiology."*
  - Plain-language patient summary: *"Please do not take ibuprofen or pain relievers. You will have a heart stress test next week."*
  - Care-content language note: Select regional language from the 28 available care languages.
- Publish as **Version 1 (v1)**.
- If published before resolving all uncertainties or without an approved brief, the system requires an explicit **Clinician Override Reason** which is saved immutably with the instruction version.

### 6. Patient Understanding & Version-Bound Acknowledgement
- Return to Patient view: the patient sees the newly published Version 1 instructions and plain-language summary.
- The patient clicks **Acknowledge Instructions**. The acknowledgement is recorded immutably against Version 1.
- *Transparent disclosure: An acknowledgement attests to receipt and review; it does not substitute for clinical comprehension checks.*

### 7. Scoped Deletion & Dependency Invalidation
- Return to Records and withdraw a cited record.
- Show that the previous visit brief immediately transitions to **Outdated** status with an explanatory badge: *"Source records have changed since this brief was prepared. Review the updated timeline and regenerate."*
- Export structured care summary: click **Export Care Summary** in Account settings to download the portable JSON summary with provenance.

---

## Pitch Summary
> *"HealthBridge connects scattered records, patient concerns, and language preferences into a source-linked visit brief, leaving care decisions and instruction approval strictly with qualified human clinicians."*
