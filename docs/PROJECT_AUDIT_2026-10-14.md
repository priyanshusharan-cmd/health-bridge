# HealthBridge project audit — 14 October 2026

## Verdict and scope

HealthBridge fits the supplied Track 2 Health and Wellbeing brief as a patient-to-clinician visit preparation and care handoff product. It has an implemented, persistent workflow rather than just screens. It is not yet a complete, evidenced hackathon submission or a system ready for real patient information.

Reviewed backend application modules, frontend components/client/types/localization/navigation, workflow tests, deployment configurations, verification utilities and project/submission documentation. No application behavior was changed. Private `.env` values and existing patient/database contents were not inspected. No browser automation or visual inspection was performed, respecting the recorded project restriction. This is a source and automated workflow audit, not a clinical validation, penetration test, dependency vulnerability audit or certification.

The supplied track brief is the basis for this review. Historical documentation mentions additional AMD/event requirements; those are not independently confirmed here. Do not treat old dates or event rules as current verification.

## Fresh verification

- Frontend TypeScript and production build: passed.
- Frontend tests: 18 passed.
- Backend tests: 25 passed; one upstream Starlette/httpx deprecation warning.
- Actual frontend API client → Vite → FastAPI → isolated SQLite integration: passed, including signup, hospital invitation, access checks, upload, review, instructions, password change and persistence. Initial sandbox run could not bind ports; approved rerun passed.
- Two additional isolated probes reproduced acceptance of whitespace-only model evidence and instruction publication with a flagged latest brief.
- Docker Compose configuration: passed. Release preflight found no model benchmark report and no accessible Docker engine; container runtime was not verified.
- These checks do not establish visual/mobile/accessibility quality, live model quality, live Atlas health or public deployment availability. The integration run explicitly used disposable SQLite, not the private configured database.

## Alignment with the supplied brief

| Expectation | Current implementation | Remaining evidence or behavior |
| --- | --- | --- |
| Defined patient/staff need | Visit preparation and traceable care handoff | Keep this focus explicit in the pitch |
| Realistic first input to final result | Intake/upload → brief → clinician review → clinician instructions → patient view | Record a fresh complete case and a clarification/failure case |
| Incorrect/unsupported responses | Strict response schema and verbatim source checks; failures are visible | Reject meaningless evidence; preserve clinical context and measure omissions |
| Sensitive information | Assignment/role checks, hashed passwords/tokens, HttpOnly sessions, demo privacy notice | Provider disclosure/consent, deletion/retention and verified staff identity before real data |
| Visible uncertainty | Pending/flagged/outdated badges, missing values, OCR warning and source links | Case-specific unknowns, conflicts, extraction quality and exact coverage |
| High-risk decisions | No autonomous diagnosis, prescribing or treatment generator | Make unresolved safety questions visible and require appropriate human resolution |
| Human review/takeover | Assigned clinician approval/flagging, review notes, publication confirmation | Structured clarification/resolution and instruction version policy |
| Understandable output | Source excerpts, clinician-authored plain language and translations | Concise organized brief and independently reviewed language quality |
| Measurable improvement | Model latency/source coverage utility exists | Actual manual-vs-assisted timing and error/omission evaluation |

## What is already implemented

- Patient and hospital-owner signup with empty private workspaces; login, logout, password changes, logout across devices and expiring sessions.
- Hospital invitations: hashed tokens, 24-hour expiry, single use, email binding, acceptance and explicit patient assignment. Links are generated; no email delivery service is connected.
- Database-backed profiles, intake, records, uploaded original files, appointments, briefs, instructions and activity. SQLite and MongoDB implementations; MongoDB errors do not silently switch to SQLite.
- PDF/TXT extraction and image/scanned-page OCR with byte/page/pixel/text limits; original download, extracted-text viewer, record search and timeline.
- Traceable excerpts, model/source-only mode disclosure, clinician review notes and stale-brief invalidation when intake, records or appointments change.
- Clinician-written original/plain/translated instructions with publication confirmation.
- Three interface languages (English/Hindi/Kannada), 28 selectable care-content languages, theme preference, responsive styles, loading/error/empty states and keyboard modal handling.

## Priority 1 — finish the useful, safe demonstration

### 1. Make the visit brief more useful than a collection of copied beginnings

Evidence: `backend/app/ai.py:21–26`, `backend/app/main.py:322–334`, `frontend/src/pages.tsx:660–701`.

Source-only mode takes the first 1,800 characters of each source. Model mode selects literal excerpts from only the first 2,400 characters of each source. Neither mode currently builds a structured clinical summary, contradiction list, missing-information checklist or clinician question agenda. Up to 12 records are selected by upload time, not relevance or clinical date.

Implement a concise, source-linked structure: reason for visit, patient questions, patient-reported medications/allergies, relevant history, unknowns and items requiring confirmation. Start with structured source selection; if adding paraphrases, retain citations and review every generated claim. Never infer diagnoses or recommend treatments. No LLM is inherently required by the supplied brief, but demonstrate real model use if the event's separate technology rules require it.

Acceptance: an important fact near the end of a long record can be found; fewer relevant records produce a readable brief; skipped material is explicitly counted. Claims remain traceable.

### 2. Close the model validation quality gap

Evidence: `backend/app/ai.py:8–15,37–41`. Reproduced: a model response containing only a single space is accepted when the source contains a space.

Reject whitespace-only, duplicate and otherwise unusable evidence. Validate response envelope shapes as well as the inner JSON; some malformed provider shapes can raise uncaught type errors. Add regression cases for malformed envelopes, empty responses, retry success, timeout and unsupported excerpts. Context matters: a literal substring can omit a preceding negation or following qualifier. Use sentence/context boundaries and show neighboring source text; substring matching alone is not clinical correctness.

Acceptance: unusable output cannot save a brief, errors remain understandable, and negative statements/qualifiers are preserved.

### 3. Make uncertainty specific to the case

Evidence: brief content only stores evidence/sources/intake/note/latency/notice (`main.py:333–334`); document extraction returns text and media type (`documents.py:10–30`).

Store extraction method and page locations, missing fields, excluded document counts, truncated sections and unresolved discrepancies. Expose them in the brief and review checklist. Confidence must reflect measured extraction quality, not an invented medical certainty score. A generic OCR warning cannot tell a reviewer which pages actually underwent OCR or failed partially.

Acceptance: a missing medication list, conflicting allergy statement or partially extracted scan yields a visible item requiring a person's review.

### 4. Complete the clarification and publication policy

Evidence: `main.py:345–377`. Reproduced: publishing instructions succeeds with HTTP 200 while the latest brief is flagged. The API requires an assigned clinician and a confirmation checkbox, but does not link instructions to a brief/version or require resolution of flagged items.

This is a workflow policy gap, not autonomous medical advice: the instructions are authored by a clinician. Decide whether publication requires an approved current brief or permits an explicit clinician override with a reason. Implement that policy on the server. Add questions, clarification responses, resolved items, reviewer identity and a clear next owner. Add instruction drafts, correction/supersession and withdrawal so obsolete instructions do not remain indistinguishable from current ones. Review notes currently overwrite prior notes in the brief; audit events retain earlier text, but no dedicated review-version model exists.

Acceptance: flagged/stale information cannot silently be treated as a completed handoff, and patients can identify the current instruction version.

### 5. Fix upload processing time and extraction repair

Evidence: `documents.py:19–29`, `frontend/src/api.ts:9`. Ordinary requests time out after 30 seconds; image OCR alone can take 30 seconds, and a 20-page scan uses a 20-second timeout per page. Slow valid uploads can therefore time out in the client while processing continues on the server, encouraging duplicate retries.

Use an upload job with progress/status and a total processing deadline; preserve idempotency across retries. Add extraction/metadata correction, original-page comparison and duplicate detection. Metadata currently depends on a few English keywords and exact `Date: YYYY-MM-DD` / `Provider:` headers; normal records in other formats often become unknown. Uncertainty is appropriate, but staff need a way to correct it without altering the original.

Acceptance: multi-page scans finish with progress or fail cleanly; retrying does not duplicate a record; corrections preserve provenance and invalidate affected briefs.

### 6. Prepare an honest, stronger synthetic demo and measure the benefit

Evidence: `db.py:60–79`, `demo-data/follow-up.txt`, `scripts/benchmark_model.py` and `submission/`.

The seed deliberately omits numerical lab results and contains mostly administrative prose. Good for avoiding unsafe interpretation, but too simple to demonstrate robust document handling. Add synthetic long documents, an uncertain/missing field, a conflicting source, and a scan. A reviewer must resolve the conflict. Show model failure without fake output and reject an unauthorized review.

Measure the same preparation task manually and with HealthBridge, including human review. Report timings, omissions, corrections and sample size. Model response latency or number of sources quoted is not evidence of reduced clinician workload or medical accuracy. No measured task-improvement report was found.

## Priority 2 — important product completion

- **Language truthfulness:** `documents.py` never supplies Tesseract's `lang` option, so installing Hindi/Kannada OCR packs in Docker does not activate them. Add explicit supported OCR languages and test real samples. The 28 care-language options permit typed content and human translations; they do not provide 28-language UI or automated translation. Add pre-login language selection and screen-reader language metadata for original/plain content; `pages.tsx` currently labels those instruction versions `lang="en"` regardless of their actual language. Independent linguistic review remains needed.
- **Record lifecycle:** no public record edit/delete routes, no patient export bundle and no self-service account deletion. Add controlled deletion, retention policy and provenance-preserving corrections; invalidate dependent output.
- **Instruction understanding:** optional patient acknowledgement and “I need clarification” action would close the care loop. Do not treat a click as proof of medical comprehension.
- **Invitations/assignments:** no invite delivery, listing/revocation interface, patient unlinking or clinician reassignment. Membership is unique per user; a patient cannot join another hospital after the first. Support the intended single-hospital scope explicitly or design transfer/multiple organizations.
- **Appointments:** editable personal appointment notes exist; clinic booking, cancellation, availability and reminders do not. Those are optional integrations for this track. Keep the existing “does not book a visit” wording.
- **Demo recovery:** shared users can change profile/intake/data. Seeding happens only when users are empty, so a populated fresh database can lack demo users while demo mode is enabled. Add a safe operator-only demo reset or isolated per-session synthetic workspace; do not overwrite existing data automatically.
- **Visual QA:** manually inspect narrow screens, dialogs, empty hospital workspaces, print/PDF, keyboard navigation, Hindi/Kannada overflow, dark mode and gestures. Current automated tests do not exercise a complete browser click flow.

## Priority 3 — required before real patient use

- Verify email ownership and hospital/professional identity; hospital signup currently grants the clinician role immediately. Assignment limits access but does not establish clinical qualifications.
- Password recovery, staff invitations/roles, revocation and account recovery are absent.
- Make model provider/processing location/retention clear before sending records; record appropriate consent and permit revocation of access. The signup checkbox is client-side and its acceptance is not persisted by the registration API.
- Define deployment-specific encryption, backups, restore drills, retention/deletion, access monitoring and incident handling. Uploaded bytes are stored directly; no application-level record encryption is implemented. Infrastructure encryption may exist but was not verified.
- Audit stable actor IDs as well as display names, record reads/downloads and security/account events, and protect audit integrity. Existing clinical actions are useful but do not form a complete access audit.
- Replace process-local authentication rate limiting with shared storage and a bounded lifecycle; add model/upload/storage quotas. Records, intake history and instruction history have no aggregate per-account cap or pagination.
- Verify proxy-aware origins, HTTPS/cookie configuration, resource isolation and multi-instance behavior in the actual deployment. Sensitive real information remains outside the supported prototype scope.

## Hardcoded and static behavior inventory

| Location | What is fixed | Assessment / action |
| --- | --- | --- |
| `backend/app/db.py:60–79` | Synthetic names, clinic, records, allergy/intake and instructions | Intentional demo seed; keep clearly synthetic and resettable |
| `backend/app/db.py:68–70` | Appointments on 15 October 2026 | Become past after that date; use a chosen scenario date or generate relative demo dates |
| `backend/app/main.py:144–150` | Demo user IDs and public shared password | Acceptable only for isolated synthetic demo; disabling discovery does not revoke those accounts |
| `main.py:107,189` | Demo identity checks repeated as fixed ID lists | Centralize demo-account policy to avoid divergence |
| `main.py:138` | `amd_verified: False` | Conservative placeholder, not hardware detection; base claims on recorded server evidence |
| `backend/app/ai.py:19–35` | Default extractive mode, default model/endpoint, excerpt limits | Model/endpoint are configurable; limits are real omissions that need coverage reporting |
| `documents.py:33–36` | English keyword classifier and header patterns | Functional heuristic, not a medically validated classifier; add manual correction |
| `backend/app/languages.py` | Language catalog | Legitimate static capability catalog; avoid claiming abilities just because a language is listed |
| `frontend/src/locales`, `i18n.ts`, CSS | Labels, translations, colors, icons and layout | Normal static frontend resources, not fake patient data |
| `frontend/src/api.ts:9` | 30-second ordinary / 180-second brief timeouts | Functional configuration; OCR timeout mismatch needs correction |
| `render.yaml` | Demo enabled and extractive processing | Sample deployment stays in source-only demo mode until configured |
| `scripts/release_check.py` | `submission_ready` always false | Conservative reminder, not a readiness calculation; add evidence-backed completion fields if needed |

No frontend fixture database or clinical business state in localStorage was found. Clinical pages fetch persisted backend data. Theme storage and static UI translations are not problematic hardcoding. No savings/accuracy percentages are implemented as measured product evidence.

## Deployment, documentation and submission work

- The current folder is not an initialized Git repository. A remote public repository cannot be inferred from CI files. Publish only after excluding private configuration and local data.
- CI defines builds/tests and Docker builds, but no evidence of a completed hosted CI run is available in this checkout. Add container runtime health/workflow smoke tests.
- Docker/Render files are setup assets, not proof of a deployed working application. Test the built container and HTTPS demonstration independently.
- The submission description and pitch script exist. A finished cover, presentation, recorded demonstration and measured impact report were not found.
- If meaningful AMD inference is required by the actual event rules, configure a real endpoint, use it in the product and retain matching GPU/server/request evidence. The adapter and benchmark script are not hardware execution evidence.
- Reconfirm organizer eligibility, pre-event code policy and actual submission requirements. Historical event notes were not revalidated in this audit.
- Documentation needs consolidation: VERIFICATION retains older test counts, and HANDOFF contains superseded chronological notes. Create one current status/checklist and consistently distinguish implemented prototype signup from verified production provisioning.

## Practical completion order and done criteria

1. Fix meaningless model evidence and upload timeout/retry behavior.
2. Build a concise organized brief, coverage disclosure and case-specific review checklist.
3. Implement clarification resolution and explicit instruction publication/version policy.
4. Add original-preserving extraction corrections and scoped record lifecycle operations.
5. Prepare richer synthetic fixtures and a deterministic demo reset.
6. Record task comparison metrics, run language/manual UI checks and demonstrate one human takeover case.
7. Verify container runtime and public HTTPS workflow; publish a sanitized repository and updated status documentation.
8. Complete event-specific model/hardware evidence if required and produce final submission assets.

A complete hackathon demonstration is one reproducible, useful handoff with honest uncertainty, human review, an observed improvement and accessible deployment/recording. It does not require billing, insurance, hospital-wide scheduling, voice, wearable integrations or autonomous diagnosis. A production healthcare product has a separate, larger completion bar.
