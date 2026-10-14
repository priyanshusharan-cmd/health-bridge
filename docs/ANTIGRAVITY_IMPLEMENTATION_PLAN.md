# HealthBridge — detailed implementation plan for Antigravity

Prepared 14 October 2026. Workspace: `/Users/priyanshusharan/Documents/project/health-bridge`.

## 1. Assignment

Complete HealthBridge as a reproducible, safe, synthetic-data demonstration for the supplied Track 2 Health and Wellbeing brief. Focus on one journey: patient intake and uploaded records → source-linked visit preparation → explicit clinician review/clarification → reviewed instructions → patient understanding.

Read `docs/PROJECT_AUDIT_2026-10-14.md`, this plan, README and the latest applicable instructions before changing code. Historical HANDOFF entries contain superseded decisions; do not restore removed controls or older password policies. Reinspect source because these findings describe the current checkout, not future changes.

Implement the hackathon phases below in order. Production phases are a separate workstream and are not a prerequisite for a disclosed synthetic demonstration. Do not invent clinical validation, hardware evidence, translations, user studies, deployment URLs or credentials. Clearly report any external dependency that remains unavailable.

## 2. Preserve these constraints

- Keep React/TypeScript/Vite, FastAPI, existing SQLite/MongoDB persistence and current visual palette. Prefer small changes and existing dependencies.
- Preserve working registration, patient assignment, hashed passwords/session tokens, password changes, logout/revocation, languages, original downloads and stale-brief protection.
- All clinical state must come from the API and persist on the server. No business-state localStorage or frontend fixture fallback. Theme preference may remain local.
- Keep real patient data out of this prototype. Shared demo accounts must remain visibly synthetic.
- Do not inspect, print, copy, commit or place private `.env` secrets into reports/prompts. Do not modify other projects.
- The recorded user restriction prohibits browser automation/screenshare. Use terminal/API checks and provide a manual UI checklist. Do not claim manual checks passed without user evidence.
- Do not generate autonomous diagnoses, prescriptions, dosing changes or treatment advice. Any generated organization/simplification must remain a draft requiring appropriately authorized human review.
- Keep passwords masked initially and preserve the current eight-character minimum unless the user changes it. Preserve the absence of visible browser back/forward buttons.
- Never run destructive tests against the configured workspace database. Default tests to disposable SQLite; use uniquely named disposable Atlas databases only when expressly enabled and permitted.
- Apply additive migrations; never drop/reseed existing user data automatically. No public publication or external messages as an implicit consequence of this plan.

## 3. Verified frontend/backend connection status

### Result

The current frontend/backend connection works through the actual API client and Vite proxy. Every API operation found in frontend source has a corresponding backend route. The real HTTP test passed again on 14 October with temporary local servers and an isolated synthetic SQLite database. This verifies API connectivity and the tested workflow, not browser click behavior or all deployment environments.

The already-existing services at `127.0.0.1:8000` and `127.0.0.1:5173` both refused connections during this audit: no application was listening there at check time. Do not describe this as a route mismatch. The temporary integration servers ran successfully and were cleaned up.

The preceding audit also freshly passed the production build, 25 backend tests and 18 frontend tests. No live Atlas test, public deployment check or real model run was performed in this audit.

### Connection design

- `frontend/src/api.ts`: relative `/api` prefix, same-origin cookies, JSON bodies except multipart uploads, explicit error handling, default timeouts.
- `frontend/vite.config.ts`: development `/api` proxy to port 8000, overridable for isolated tests.
- `frontend/nginx.conf`: Compose frontend `/api/` proxy to backend service; API path is preserved.
- Root `Dockerfile`: builds React and serves UI/API from one FastAPI origin through `STATIC_DIR`.
- `main.py`/`onboarding.py`: authentication, authorization, persistence and response data.
- Mutation callbacks normally reload workspace state rather than fabricate local clinical results.

### Route inventory

Paths below include the `/api` prefix supplied by the shared client.

| Frontend operation | Backend method/path | Current verification |
| --- | --- | --- |
| Runtime health | GET `/api/health` | HTTP integration |
| Language options | GET `/api/languages` | HTTP integration |
| Demo account discovery | GET `/api/demo-accounts` | HTTP integration |
| Register | POST `/api/auth/register` | HTTP integration and backend tests |
| Sign in | POST `/api/auth/login` | HTTP integration |
| Sign out | POST `/api/auth/logout` | HTTP integration |
| Sign out all devices | POST `/api/auth/logout-all` | Backend session-revocation tests; route matched |
| Change password | POST `/api/auth/password` | HTTP integration and backend tests |
| Read profile/session | GET `/api/me` | HTTP integration |
| Edit profile/interface language | PATCH `/api/me` | HTTP integration |
| Assigned patient list | GET `/api/patients` | HTTP integration |
| Patient workspace | GET `/api/patients/{patient_id}/workspace` | HTTP integration |
| Save intake | POST `/api/patients/{patient_id}/intake` | HTTP integration |
| Upload original | POST `/api/patients/{patient_id}/records` | Multipart HTTP integration |
| Read extracted record | GET `/api/records/{record_id}` | HTTP integration |
| Download original | GET `/api/records/{record_id}/file` | Authenticated HTTP download |
| Prepare brief | POST `/api/patients/{patient_id}/brief` | Source-only HTTP integration |
| Approve/flag brief | POST `/api/briefs/{brief_id}/review` | HTTP integration, unauthorized/stale review tests |
| Publish instructions | POST `/api/patients/{patient_id}/instructions` | HTTP integration |
| Save/edit appointment notes | POST `/api/patients/{patient_id}/appointments` | HTTP integration and backend tests |
| Create invitation | POST `/api/hospital/invitations` | HTTP integration |
| Accept existing-account invitation | POST `/api/hospital/join` | Backend acceptance tests; route matched |

### Known integration risks to address

1. Patient switch is disabled during brief generation, but not during intake/upload/appointment/instruction dialogs. Dialog forms receive the mutable global `patientId`; existing form values can survive a change of patient. This is a code-observed risk, not a reproduced browser incident. Capture the dialog's patient identity and prevent stale cross-patient submission.
2. All ordinary requests have a 30-second timeout, including OCR uploads that can take substantially longer.
3. API expiry handling excludes `/me` for every method. This is reasonable for initial anonymous GET but also excludes an expired profile PATCH. Make that distinction explicit.
4. A mutation may succeed while its refresh fails. Current callbacks can show a generic error and leave a filled form ready to resubmit, risking duplicates.
5. Retry in the global error banner refreshes workspace; it does not reliably retry the failed operation or reload an initially failed patient list.
6. Frontend TypeScript response assertions do not validate data at runtime. New state machines require response models and contract tests.

## 4. Completion stages

| Stage | Scope | Exit condition |
| --- | --- | --- |
| A | Existing integration and safety repairs | Correct patient targeting, clear save/retry semantics, model validation regression cases |
| B | Documents, brief and human handoff | Durable extraction, visible coverage/unknowns, clarification resolution, versioned instructions |
| C | Hackathon demonstration and release evidence | Reproducible case, observed metrics, runtime verification, final assets |
| D | Optional real-world readiness | Verified identity, governance, recovery, staff roles, operational controls |

Do not label Stage D complete merely because Stages A–C pass.

## 5. Phase A1 — protect patient context and refresh behavior

**Files:** `frontend/src/App.tsx`, `forms.tsx`, `AppointmentForm.tsx`, `pages.tsx`, `Onboarding.tsx`, `api.ts`, relevant frontend tests and HTTP integration script.

Tasks:

1. Replace bare mutation modal strings with a typed dialog context containing modal kind, captured patient ID and initiating account ID where appropriate. Keep purely account/about dialogs separate.
2. Pass the captured ID into patient-specific forms. Key forms by captured patient ID. Disable patient switching while a patient mutation dialog is open, and dismiss/cancel stale dialogs on account change/session expiry.
3. Guard asynchronous completion by both account and patient context. A request for patient A must not refresh patient B, display A's success as B's result, or reopen a closed session.
4. Separate request success from refresh success. After an acknowledged save, show “Saved; refresh failed” with a refresh action, not an invitation to repeat the mutation.
5. Give errors an operation-specific retry action. Patient-list failures must retry `/patients`; failed health must retry health; failed reads must not repeat writes.
6. Retain old valid data only with an explicit stale-data label when refresh fails. Never fabricate a successful state.

Acceptance/tests:

- Test mutation targets are captured before a patient switch and cannot silently change.
- Simulate logout/account switch while a read/write is outstanding; no stale state is applied.
- Simulate successful POST followed by failed refresh; only one POST occurs and a refresh action remains available.
- Empty hospital workspaces remain usable; retrying a failed patient-list fetch actually reloads patients.
- Manual checklist: open each patient-specific dialog as clinician, attempt switching patient, confirm correct visible patient and destination. No automated browser claim.

## 6. Phase A2 — API contracts, session expiry and meaningful model output

**Files:** `backend/app/main.py`, `ai.py`, `frontend/src/api.ts`, `types.ts`, `backend/tests/test_workflow.py`, `frontend/tests/api.test.mjs`, `frontend/tests/connection.mjs`.

Tasks:

1. Restrict the initial-GET `/me` expiry exception to that specific anonymous bootstrap operation. Expired authenticated profile writes should trigger centralized session cleanup.
2. Use typed error codes for new APIs while retaining readable messages. Keep legacy clients compatible during migration.
3. Add explicit response models for changed endpoints, covering nullable values and state enums. Keep domain types synchronized with those contracts; avoid a major tooling migration solely to generate types.
4. In `ai.py`, reject blank/whitespace quotes and duplicate evidence. Require valid nonblank source IDs and at least one useful evidence item.
5. Validate the provider response envelope before indexing into it. Convert malformed shapes into a bounded verification failure instead of an uncaught server exception. Preserve one bounded retry and visible endpoint errors.
6. Preserve sentence/neighbor context, especially negation, uncertainty, dose units and temporal qualifiers. Do not equate source matching with clinical validation.
7. Record processing mode, model identifier and selection-policy version with generated output. Do not store provider keys or full endpoint URLs in evidence reports.

Acceptance/tests:

- Whitespace-only output fails verification; no brief is saved.
- Duplicate/unknown-source quotes, invalid envelope, null content and malformed JSON fail predictably.
- Test invalid first response followed by valid retry and both responses invalid.
- Model timeout/outage does not silently switch a configured model run to source-only success.
- A quote from “Do not…” must preserve the negation/context in the final displayed evidence.
- Expired PATCH `/me` clears authenticated state; initial anonymous GET does not display a spurious expiry error.

## 7. Phase B1 — durable uploads, extraction provenance and corrections

**Files:** `documents.py`, `store.py`, `db.py`, `main.py`, `forms.tsx`, `types.ts`, API client, containers and tests. Prefer separate document/job router/service modules rather than expanding `main.py` indefinitely.

### Proposed additive data model

- `upload_jobs`: ID, patient ID, initiating user ID, idempotency key, original file reference, state, timestamps, error code, progress, attempt count and worker lease/expiry.
- `record_extractions`: record ID, extraction version, page/section blocks, method, OCR language, quality warnings and extraction-policy version.
- `record_corrections`: record ID, correction version, corrected metadata/text, reason, reviewer ID, timestamp and previous version reference.

Keep existing record IDs/original bytes intact. Legacy records without provenance remain readable and should show “extraction details unavailable.” Do not claim they underwent measured OCR.

### Proposed API

- POST `/api/patients/{id}/upload-jobs`: bounded multipart upload, OCR language and client-generated idempotency key; returns 202 and job ID promptly.
- GET `/api/upload-jobs/{job_id}`: authorized status/progress/result.
- PATCH `/api/records/{record_id}/metadata`: reviewed metadata correction with reason and expected version.
- POST `/api/records/{record_id}/corrections`: new reviewed extraction correction; preserve original text and file.

Jobs must persist in the database. A bare FastAPI background task or thread is not durable completion. Use a small persistent queue/worker with lease recovery, a global concurrency bound and restart recovery; keep deployment simple. Do not process full OCR while holding a database transaction. Persist a record atomically only after successful extraction, then invalidate affected briefs once.

Tasks:

1. Keep existing 10 MB, page/pixel/text bounds; add a total processing deadline and explicit partial-page failure policy.
2. Poll jobs from UI with bounded intervals, cancellation on unmount and clear queued/processing/complete/failed states.
3. Reusing an idempotency key returns the same job/result; scope keys by user/patient. Add a file hash for duplicate warning; do not automatically erase legitimate repeated uploads.
4. Persist page boundaries, extraction method, warnings and OCR language. Do not discard page identity while joining text.
5. Activate only explicitly supported installed OCR languages using `lang`; return actionable errors when a pack is unavailable. Typed 28-language intake must not imply 28-language OCR.
6. Provide side-by-side extracted content and original/page access where practical; downloads remain available. Show manual metadata correction for unrecognized dates/providers rather than pretending parsing is accurate.
7. Apply corrections as new versions with reviewer attribution. Default correction approval to assigned clinicians; patient-entered corrections become proposals requiring review.

Acceptance/tests:

- Multi-page slow scan does not hit the ordinary request timeout.
- Restart worker during extraction; the job completes or fails explicitly without duplicate records.
- Unauthorized users cannot inspect jobs or their uploaded bytes.
- Repeated upload retry creates one completed record and one clinical invalidation.
- A partially unreadable page is visible as a warning or causes a clearly explained failure according to policy.
- Real English OCR sample and installed Hindi/Kannada samples are tested; quality claims remain limited to measured samples.
- Corrections preserve the original and invalidate current/approved/flagged dependent briefs.

## 8. Phase B2 — structured visit brief with visible uncertainty and coverage

**Files:** `ai.py`, new brief service/schema module, `main.py`, `store.py`, `types.ts`, `pages.tsx`, localization catalogs and tests.

### Proposed content contract

Retain legacy `evidence`, `sources`, `intake`, `note`, `notice` fields while introducing a versioned content schema:

```text
schema_version
source_revision
sections[]: {key, label, items[]}
items[]: {text, attribution, citations[]}
citations[]: {source_id, source_version, page, start_offset, end_offset, quote}
uncertainties[]: {id, kind, description, citations[], status}
coverage: {available_records, included_records, excluded_sources[], shortened_sources[]}
processing: {mode, model, policy_version, latency_ms}
```

Tasks:

1. Build sections for patient reason/questions, patient-reported medications/allergies, relevant recorded history, and information to confirm. Preserve patient-reported versus document-recorded versus clinician-reviewed attribution.
2. Select relevant passages across the whole allowed document, including later pages. Use bounded chunking rather than a silent beginning-only cutoff.
3. Report resource-budget exclusions explicitly. If keeping a record cap, show which records were excluded and permit clinician selection for regeneration.
4. Start with deterministic structure and exact-context excerpts. If adding model paraphrases, require claim-level citations and human review; maintain a faithful source-only path labeled correctly.
5. Surface unknowns explicitly: “Not provided” is different from confirmed “None.” Never convert missing allergies into “no allergies.”
6. Conflicting source statements should become “Statements differ; confirm with a clinician,” linked to both sources. Do not infer a diagnosis or determine which medical statement is true.
7. Show extraction warnings and unresolved uncertainty before the approval action. Source link opens the relevant original/extracted context, not merely an unrelated document list.
8. Preserve source revision checking during generation. Use a monotonic clinical revision for relevant changes rather than treating every unrelated audit action as a clinical change.
9. Ensure printed briefs retain patient identity, status, timestamp, coverage notice and citations. Pending/flagged/outdated output must retain prominent status in print.

Acceptance/tests:

- Important late-document fact is included or explicitly reported as excluded.
- Long-record and >12-record scenarios display exact coverage limitations.
- Every output item has a valid citation or is an explicitly labeled unknown; no fabricated source IDs/page coordinates.
- Differing allergy statements appear together for review, without resolving them automatically.
- Concurrent source change prevents saving an apparently current brief.
- Legacy brief JSON still renders after schema introduction.

## 9. Phase B3 — clarification, review history and instruction lifecycle

**Files:** new review/instruction modules, `store.py`, `db.py`, backend routes, `pages.tsx`, `forms.tsx`, `types.ts`, App dialog context and tests.

### Proposed data

- `clarifications`: patient ID, brief ID, question, originating uncertainty, creator ID, assigned owner, status, timestamps.
- `clarification_messages`: clarification ID, author ID/role, text and timestamp.
- `brief_reviews`: brief ID, expected source revision, reviewer ID, outcome, note and timestamp. Append records; retain prior decisions.
- Instruction metadata: brief/source revision reference, author/reviewer stable IDs, status, original language, plain language, translation language, reviewed timestamp, superseded-by and withdrawal reason.

### Proposed operations

- Clinician creates a clarification; patient responds; clinician resolves/reopens with reason.
- Review request contains expected brief/source revision and reviewed uncertainty IDs.
- Save instruction draft, publish reviewed draft, create corrected version, withdraw/supersede version.

### Default publication policy

For the hackathon handoff, require the current brief to be approved and required clarification items to be resolved before publishing derived instructions. If supporting independently authored instructions without an approved brief, require an explicit clinician override with a reason, preserve that origin, and surface it to the patient. Do not silently attach stale instructions to the new brief. Existing independently authored seed/legacy instructions remain readable with a legacy provenance label.

Tasks:

1. Enforce ownership, assigned clinician role and current revisions server-side for every operation.
2. Keep clarification text in the user's words. Resolution is a human action, not an automatic confidence threshold.
3. Treat checkbox confirmation as an attestation, not proof of clinically correct meaning.
4. Store separate content-language fields rather than assume original/plain text is English.
5. Make current instructions prominent; historical/superseded/withdrawn versions stay accessible but visibly marked.
6. Add optional patient acknowledgement and “I need clarification.” Persist acknowledgements against a specific version; never interpret them as proof of comprehension.
7. Preserve historical authors even after profile renaming; display stable attribution while allowing current profile data elsewhere.

Acceptance/tests:

- Pending/flagged/outdated brief cannot silently yield a normal completed instruction handoff.
- Stale review/publish requests receive 409 with a refresh instruction.
- Patient cannot approve/resolve clinician-only items or publish instructions.
- Another clinician/hospital cannot read or modify unassigned clarifications/instructions.
- Changing sources invalidates dependent review state; existing instructions are marked for reassessment rather than invisibly rewritten.
- Correction creates a new version; withdrawal/supersession is visible; acknowledgement is version-bound.

## 10. Phase B4 — scoped lifecycle, languages and demo stability

**Files:** record/account/onboarding routes, `store.py`, `db.py`, `Account.tsx`, `Onboarding.tsx`, `LanguageSelect.tsx`, `locale.tsx`, `pages.tsx`, demo assets and tests.

Tasks:

1. Implement scoped record removal/retention behavior with dependency invalidation and an audit event. Decide hard-delete versus tombstone retention explicitly; do not destroy original evidence while claiming it is still available. Clear file/job/correction dependencies consistently.
2. Provide authenticated patient export, with plain explanation and provenance. Keep print/save-PDF where sufficient for the demo; a broader interoperable EHR export is not required.
3. Add invitation listing/revocation and explicit assignment unlink/transfer behavior if included in scope. Require patient authorization for a new assignment. Preserve accepted-invitation audit history.
4. Document current one-hospital membership limit. Do not silently change it into all-staff access; multi-hospital/multi-staff features need an explicit authorization model.
5. Add pre-login interface language preference in UI state without misrepresenting clinical content translation. Retain English/Hindi/Kannada interface scope. Set actual content language/RTL direction per version.
6. Create richer synthetic case files: long text, a realistic text PDF, scan, missing medication list and differing patient/document allergy statements. Keep synthetic marking on every fixture.
7. Make scenario date configurable. Provide a safe disposable-demo reset utility that refuses the ordinary configured database unless a specific synthetic target is selected. Do not introduce an unauthenticated public reset endpoint.
8. Demo identities/password policy should live in one backend module/configuration source. Do not let UI depend on a known email suffix.

Acceptance/tests:

- Deletion/withdrawal cannot leave broken citations presented as verified originals.
- Revoked/unlinked access blocks future API reads and writes; patient data remains intact.
- Changing interface language preserves original content verbatim.
- All added UI strings have Hindi/Kannada entries; human review is recorded separately from translation presence tests.
- Demo reset only affects its disposable target and produces the same repeatable case.

## 11. Phase C1 — evidence, benchmark and manual demonstration

**Files:** `scripts/benchmark_model.py`, new task evaluation utility/report template, `docs/DEMO.md`, `docs/VERIFICATION.md`, `docs/TRACK_READINESS.md`, `submission/`.

Tasks:

1. Record one complete scenario: patient enters concerns, uploads records, sees processing/unknowns, clinician inspects sources, asks a clarification, patient responds, clinician resolves/approves, publishes instructions, patient reads/asks for clarification.
2. Demonstrate at least one failure: unsupported model output or unavailable endpoint; show that no fake brief is saved. Demonstrate unauthorized review denial and stale-version prevention.
3. Measure manual versus assisted preparation using the same synthetic case and a stated task/checklist. Count missing facts, incorrect claims, review corrections and time including review. Include sample size, conditions and limitations. Do not equate model latency/source count with productivity or clinical accuracy.
4. If event rules require AMD inference, execute the product's actual selection task against a genuine AMD-hosted model endpoint. Keep matching request/server/GPU evidence; configuration flags and local model strings are insufficient. Hardware availability and credentials are external dependencies.
5. Independently review clinical-language examples. Avoid claiming that a translation dictionary test establishes clinical translation quality.
6. Prepare final cover, concise deck and working demonstration recording. Existing scripts/outlines are preparation assets, not completed submissions.

Manual QA checklist, performed by the user or authorized human:

- Patient and clinician journey at desktop and narrow mobile widths.
- Dialog patient context, keyboard focus/Escape/tab behavior and protected scrolling.
- Hindi/Kannada label wrapping, screen-reader content-language metadata and dark contrast.
- Slow upload progress, interrupted connection, retry after successful save and expired session.
- Empty hospital workspace, invitation copy/acceptance and fresh patient isolation.
- Pending/flagged/outdated/current brief and instruction status in print/PDF.
- Original download, source location, correction history and patient clarification.

Record results as passed/failed/not performed with actual evidence. Do not populate every row with “passed” automatically.

## 12. Phase C2 — container/runtime and release checklist

**Files:** root/backend/frontend Dockerfiles, `docker-compose.yml`, `frontend/nginx.conf`, `render.yaml`, `.github/workflows/ci.yml`, `scripts/release_check.py`, README and submission documentation.

Tasks:

1. Align worker deployment, upload limits and proxy deadlines with job processing. Keep UI/API same-origin and secure cookies for HTTPS deployment.
2. Run built container health and authenticated synthetic workflow smoke checks; Docker build/Compose syntax alone are insufficient.
3. Add CI checks for meaningful new regression cases and a container runtime smoke test. Keep ordinary tests isolated from private `.env` configuration.
4. Verify persistence across container/application restarts, original file downloads and stale-source protection.
5. Record release evidence as files with timestamps/results. Refactor `release_check.py` to report `passed`, `failed`, `missing` or `requires_human_evidence` per gate; derive readiness from required gates rather than permanently hardcoding false or trusting environment labels.
6. Consolidate current verification counts and limitations; preserve honest synthetic/AI-mode disclosures. Avoid stale historical claims in main setup instructions.
7. Prepare sanitized repository/deployment assets. Publishing and cloud/provider provisioning require the user's chosen destination and any required credentials; leave these as external actions until supplied/authorized.
8. Reconfirm actual event rules, eligibility and cutoff through official organizer information when preparing submission. Do not rely on historical HANDOFF dates as fresh verification.

Exit criteria:

- Clean setup from documented steps; all required local checks pass.
- Container starts, recovers jobs and preserves data correctly.
- HTTPS demonstration is independently reachable if a public deployment is selected.
- Final source-only/model mode and any hardware claims match retained evidence.
- No secrets or private patient data in source, fixtures, logs or submission assets.

## 13. Stage D — production readiness backlog

Implement separately before accepting real patient information. A successful demo does not complete these items.

| Workstream | Implementation requirements | Verification |
| --- | --- | --- |
| Email ownership/recovery | Provider integration, expiring hashed verification/recovery tokens, replay prevention, enumeration-resistant responses, session revocation | Email delivery and token lifecycle tests; provider dependency explicit |
| Professional identity | Verified organization onboarding and clinician credentials, approval/revocation state, privilege escalation restrictions | Unverified accounts cannot gain real clinical authority |
| Staff roles | Owner/staff roles, scoped patient assignments, invite/revoke/reassign, least privilege | Cross-tenant and revoked-role denial tests |
| Consent and privacy | Persist versioned consent, disclose actual model processor/region, retention and revocation, patient-controlled access | Consent withdrawal and access-deletion/export checks |
| Data lifecycle | Account deletion, file/correction/job cleanup, legal retention decisions, deletion receipts | Restore/deletion policy evidence; no orphaned private bytes |
| Operational security | Shared rate limiting, model/upload/storage quotas, proxy-aware identity, resource isolation and monitoring | Multi-instance abuse/recovery tests and bounded storage |
| Audit | Stable actor IDs, reads/downloads/account/access events, protected retention and integrity | Clinical access trace can be reconstructed without relying on mutable names |
| Backup and recovery | Deployment encryption verification, encrypted backups, restore drills, incident runbook | Actual timed restore evidence, not just a configured backup switch |

Select providers/configuration with the user. Do not fabricate email delivery, clinician verification or compliance certification.

## 14. Testing strategy and execution commands

Run baseline checks first and after relevant changes:

```sh
npm --prefix frontend run build
npm --prefix frontend test
PYTHONPATH=backend .venv/bin/pytest backend/tests -q
node frontend/tests/connection.mjs
docker compose config --quiet
```

The HTTP integration script starts temporary servers on ports 15173/18000 and deletes its temporary SQLite database. Local socket permissions may require normal approved execution. Do not reinterpret an EPERM startup failure as an application bug; repeat only with the appropriate permission and retain the result.

Expand `frontend/tests/connection.mjs` as capabilities are added to cover existing-account join, logout-all, slow upload jobs, corrections, structured coverage, clarification resolution, version publication and current-patient reads. Check real HTTP responses and subsequent persisted reads, not just internal function returns.

Add backend tests for authorization, invalid input, version conflict, atomic rollback, worker restart/idempotency and model failure. Add frontend tests where they verify behavior, such as context capture, retry semantics and state transitions; avoid tests that merely repeat JSX/source text.

Optional Atlas regression:

```sh
HEALTHBRIDGE_TEST_MONGO=1 PYTHONPATH=backend .venv/bin/pytest backend/tests -q
HEALTHBRIDGE_TEST_MONGO=1 node frontend/tests/connection.mjs
```

Only run these against uniquely named disposable databases with explicit enablement and adequate create/drop permissions. Verify cleanup. Never run destructive reset/migration experiments on the ordinary configured database.

## 15. Delivery format and definition of done

For each phase, report:

1. Concrete behavior implemented and files changed.
2. Migration/backward-compatibility approach.
3. Automated checks with actual results.
4. Manual checks still pending.
5. External dependencies or remaining limitations.

Hackathon completion requires: one realistic persistent journey; safe patient targeting; source-linked useful output; visible specific uncertainty; human resolution and publication; clear failure behavior; recorded time/error evidence; runnable release artifacts; and event-specific evidence/assets where required.

Do not add billing, insurance, hospital-wide scheduling, voice, wearables, vector databases or fine-tuning just to increase feature count. Do not report “fully production-ready” or “zero bugs.” Finish the agreed handoff and distinguish its verification from the production backlog.

## 16. Suggested Antigravity starting instruction

Read this plan and the audit, then implement Phase A1 and A2 first. Preserve the current palette and working API-backed workflows. Start by capturing immutable patient dialog context, fixing acknowledged-save/refresh retry semantics and `/me` session expiry, and rejecting whitespace/malformed/context-losing model evidence. Use disposable synthetic databases for tests. Continue through the hackathon phases in order, keeping additive migrations and clear evidence. Do not publish, provision services, inspect secrets, use browser automation, invent model/hardware/clinical claims or treat production dependencies as completed. Report completed phases and actual remaining gates.
