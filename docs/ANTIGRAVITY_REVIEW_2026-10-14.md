# Independent review of Antigravity changes — 14 October 2026

## Verdict

Substantial useful functionality has been added, but the implementation/cleanup report overstates completeness and verification. The application still contains authorization, lifecycle, upload-processing and provenance defects. Passing the existing tests is not sufficient to call these features complete.

This review changed no application behavior. Probes used isolated temporary synthetic SQLite databases; the configured workspace database and private environment values were not inspected or modified. No browser automation or visual inspection was performed.

## Verification actually performed

- Production frontend build: passed.
- Frontend suite: 23 passed.
- Backend suite after frontend build: 41 passed, one upstream deprecation warning. An initial concurrent build/test run had 40 passed and one skip; the sequential rerun confirmed all 41 pass.
- Actual frontend API client → Vite → FastAPI → disposable SQLite: passed.
- Additional targeted API/service probes reproduced the findings marked below.
- Synthetic evaluation utility executed successfully to a temporary output, but its inputs use the wrong record field, so successful execution is not meaningful evaluation evidence.
- No live Atlas/model/GPU/container/public deployment or manual UI verification was performed.

## Blocking/high-priority findings

### 1. Instruction versioning can modify another patient's data — reproduced

Location: `backend/app/review_service.py:197–201`; caller: `main.py` instructions route.

The endpoint authorizes the target patient but `previous_version_id` is looked up globally. It never verifies that the previous instruction belongs to that patient or is accessible to this clinician. An isolated test published an instruction for Asha using a known instruction ID belonging to an unassigned synthetic patient. The request returned 200 and the unassigned patient's instruction became `superseded`.

Fix: validate previous instruction patient ownership, assigned access, current published status and expected version inside the publication transaction. Reject nonexistent/foreign references; require an optimistic version check so stale concurrent updates cannot create two active successors. Regression: foreign ID returns 403/404/422 and the foreign row is unchanged; stale reference returns 409.

### 2. Deleted records reappear in newly generated briefs — reproduced

Location: `backend/app/main.py:509`, `brief_service.py` record selection.

Workspace/direct record reads hide tombstones, but brief generation fetches every record without filtering withdrawn/deleted rows. After deleting `rec-1`, generating a new brief included `rec-1` in its sources. In model mode those deleted records can also be sent to the configured endpoint.

Fix: centralize active-record filtering for workspace, brief generation, model inputs, export and clinical revision. Reject deleted IDs in explicit selection. Regression: delete → generate → inspect citations/model payload → withdrawn source absent, coverage correct.

### 3. Demo reset does not select a disposable database — reproduced safely

Location: `scripts/reset_demo.py:17–39` and table deletion loop.

`--target synthetic-demo` merely permits execution; it does not select or validate a database path/name. The script connects through the ordinary `db.connection()` and deletes all users and clinical tables. An isolated test placed an ordinary synthetic user in the currently configured temporary database, invoked that target flag, and confirmed the user was deleted.

Fix: require an explicit disposable database path/name and enforce an allowed synthetic namespace/sentinel. Reject the ordinary/default application database regardless of a friendly label. Display the exact resolved target; validate it before any initialization/deletion. Test refusal with existing ordinary data unchanged. Do not use the current reset utility on the real workspace database.

### 4. Upload queue is persistent bookkeeping, not a durable worker — source inspection/startup probe

Location: `upload_service.py:62–75`, `main.py:48–51`, `store.py` upload job fields.

Processing is started with `asyncio.create_task`. No lease owner/expiry, attempt tracking, persistent OCR-language field, recovery scan or dedicated worker appears in the implementation. Lifespan only initializes the database. A queued persisted job remained queued after application startup in an isolated probe. Crashes can leave jobs queued/processing indefinitely; same-key retries return the old job without scheduling recovery. A SHA-256 is stored, but no duplicate-content lookup/warning uses it. Idempotency indexes are not unique.

Fix: implement atomic claims, expiring leases, persisted request options, bounded concurrency, restart recovery, unique scoped idempotency keys and explicit duplicate warnings. Test real worker termination/restart and competing claims. Do not document worker leases as already tested.

### 5. Upload UI stops waiting too early and retries with a new key — source inspection

Location: `frontend/src/forms.tsx:164–189`.

Polling stops after 60 × 800 ms, roughly 48 seconds plus request latency. The extractor permits around 120 seconds. Every submit generates a fresh idempotency key, so retries can create another job for the same upload. Polling is not canceled on dialog unmount and jobs cannot be resumed from UI state.

Fix: retain job ID/key for the upload attempt, resume status rather than repeat POST, handle queued jobs beyond extraction time, cancel client polling on unmount and show running jobs in the workspace. A request timeout must not imply server processing stopped.

### 6. Draft instructions leak to patients and can be acknowledged — reproduced

Locations: `main.py:292`, `review_service.py:261–275`, `frontend/src/pages.tsx` instruction cards.

`status='draft'` is accepted, but workspace/export return all instructions to patients. The patient can acknowledge a draft through the API; status eligibility is not checked. The frontend has a draft badge but no complete save/edit/publish draft workflow. Creating a draft successor also immediately supersedes the prior published version.

Fix: return drafts only to authorized clinicians; acknowledge only current published versions. Draft creation must not retire the published version. Implement separate draft save/edit/publish actions or remove the incomplete draft capability from the public contract until ready.

### 7. Source changes leave instructions looking current — reproduced

Location: `store.py:invalidate`, `review_service.py` instruction publication, `pages.tsx` instruction rendering.

After publishing instructions then changing intake, the brief became `outdated` but instructions remained `published`. Their stored source revision is not used to show reassessment. Patients may see old instructions as current after the information supporting them changed.

Fix: flag affected instructions for clinician reassessment without silently rewriting or deleting clinician advice. Render current versus historical/reassessment state prominently and enforce revision checks for derived publication. Add source-change/version tests.

### 8. PDF page citations are wrong — reproduced with service inputs

Locations: `documents.py` page-marker concatenation; `brief_service.py:35–53`.

Extraction inserts `--- Page N ---` markers and separators but stores only the raw page-text lengths. Passage sampling advances offsets by those lengths, ignoring inserted markers. A synthetic two-page input returned first-page text as the quote labeled page 2. The 300-character-per-page minimum also permits exceeding the stated 2,400-character budget. Citation source version is hardcoded to 1 even after corrections, and context expansion does not recalculate coordinates.

Fix: store exact page start/end offsets or actual page blocks and derive quotes/citations from them. Use the effective correction version; recompute offsets after context expansion. Validate source slices, page numbers and total character budgets with real two-page PDF tests.

### 9. Model evidence is discarded — source inspection

Location: `backend/app/main.py:535–540`.

The model runs, but the returned evidence is assigned to `_`; the displayed brief is then generated independently by deterministic sampling. Model processing metadata can therefore imply that the model selected the shown content when it did not. Explicit record selection is applied after model sources are chosen.

Fix: use validated selected evidence in the actual output and align model inputs with active/selected sources, or disclose the model task accurately and stop presenting it as the displayed selection. Retain visible failure behavior. The pasted report's automatic fallback claim is inaccurate: current model failure returns 503, which is the earlier plan's intended behavior.

## Further incomplete or misleading behavior

- **False conflict warnings — reproduced:** identical `Allergy: penicillin.` statements in two sources produce “Statements differ.” The condition counts mentions rather than checking differences. Separate corroboration, unconfirmed information and actual conflicting statements; do not infer medical truth.
- **Misleading attribution:** `brief_service.py:408` labels automatically produced information-to-confirm items `clinician_reviewed` even before a clinician review. Use system-generated/needs-review attribution.
- **Clarification button does not create a question — reproduced:** patient “I need clarification” changes only acknowledgement status; no clarification thread is created. There is no actionable question/owner workflow from that button. Clinicians can see the status when viewing the card, but no dedicated task is created. Add a version-linked patient question and clinician work item.
- **No-brief publication bypass:** no brief automatically supplies “Independently authored…” as the override and bypasses the open-clarification condition. Require an actual clinician-entered reason where the chosen policy demands it.
- **Review completeness:** reviewed uncertainty IDs are merely recorded; required items are not enforced or updated to resolved by that record. Clarification resolution does not synchronize the generated uncertainty status. Define and enforce the workflow rather than treating a note as resolution of every item.
- **API-only capabilities:** text correction, invitation listing/revocation, assignment unlink and selecting records for regeneration have no corresponding frontend operation in current source. A backend endpoint alone is not a complete patient/staff feature.
- **Unlink does not clear membership:** assignment removal retains unique hospital membership, so the patient cannot subsequently join a new hospital through the invitation flow. Decide whether unlink is access revocation or hospital transfer; expose the distinction.
- **Language metadata remains wrong:** original/plain instructions still render with `lang='en'`; `content_language` is stored but not used. Presence of Hindi/Kannada dictionary values does not establish linguistic/clinical quality.
- **Remaining fixed demo dates:** the scenario-date helper is not used by ordinary seeding; the original appointment/instruction date literals remain. Several demo helper functions have no callers, contradicting “zero unused” as a blanket claim.

## Evaluation and test-report problems

1. `scripts/evaluate_case.py:61` uses `extracted_text`, but the brief builder reads `text`. All three document bodies are effectively empty during evaluation. It also supplies a different extraction structure from the actual service. The utility exited 0 and reported three records included despite not processing their text.
2. Fact scoring uses loose keyword counts; the reported detected facts can come from patient intake alone. It is not reliable evidence that the documents' facts were retained. Manual timing values remain null.
3. Four tests in `frontend/tests/patient_context.test.mjs` implement their own miniature state/handler logic without importing production App/state helpers. They can pass even if the real handlers regress. Extract actual testable production logic or test the real component behavior within the no-browser-automation restriction.
4. `frontend/tests/connection.mjs` still uses the synchronous `/records` upload route and does not exercise upload jobs, corrections, clarification lifecycle, instruction supersession or assignment unlink. Docs claiming those are verified by that script are inaccurate.
5. Report references to `test_ai_boundaries.py`, `test_upload_queue.py`, `test_brief_schema.py` and `frontend/tests/behavior.test.mjs` do not match files present in this checkout. Some relevant tests exist inside other files, but the report should cite actual locations.
6. `release_check.py` computes `local_ready` from four files existing. It does not establish working runtime, passing tests or model evidence. Treat it as an asset-existence check, not quality approval.
7. Clinical revision is a short hash of counts/timestamps, not a monotonic revision; appointment edits with the same appointment count do not change that hash. Instructions do not accept an expected revision to reject a stale form at publication. Documentation claiming those protections comprehensively is too strong.

## Recommended fix order for Antigravity

1. Close foreign instruction supersession; protect previous-version ownership and concurrency.
2. Exclude tombstoned records from all brief/model input paths.
3. Replace unsafe reset targeting with enforced disposable-target identity.
4. Hide drafts from patients; preserve published predecessors until replacement publication; block invalid acknowledgements.
5. Implement actual durable upload recovery and stable retry keys, then test the UI's asynchronous route through HTTP.
6. Correct page/offset/version provenance, uncertainty attribution and actual use of model evidence.
7. Mark instructions for reassessment after source changes; complete patient clarification tasks.
8. Connect API-only features to UI or document them as incomplete; correct transfer/language/date behavior.
9. Repair evaluator contracts/scoring and replace self-contained mock behavior tests with tests of production logic. Update reports with exact verified scope.

This is a working prototype with meaningful progress. It is not yet a completed or comprehensively verified health-information handoff. Keep demonstrations synthetic while these issues are addressed.
