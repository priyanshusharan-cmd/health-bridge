# Current handoff — read this first (Oct7 latest)

- User requires NO browser automation/screenshare, quota conservation and concise updates. Preserve current colours (latest correction).
- Working React/Vite + FastAPI + MongoDB Atlas, SQLite offline option; private credentials only in ignored `.env`. Never touch Ridify.
- Latest features: patient/hospital registration, private empty workspaces, email-bound 24h single-use patient invitations and explicit clinician assignments; existing patients can join via profile. Three complete UI languages,28 reviewed-care languages.
- Browser back/forward buttons and horizontal trackpad handler added; native OS gesture parity unverified. Protects fields/dialogs/horizontal tabs/pinch/vertical scrolling; momentum cooldown.
- Latest verification: production build PASS;22 local backend tests PASS;16 frontend tests PASS;3 new onboarding tests on isolated Atlas PASS (cleaned); full real frontend API HTTP flow with signup/invite PASS on SQLite. Earlier full Atlas workflows remain verified.
- Live frontend5173 and backend8000 running; backend was restarted normally after it had stopped. Final proxy health check PASS: status=ok,database=mongodb. Backend exec session77117 (reloader25717,worker25719).
- Pending external submission gates: actual meaningful AMD inference/hardware evidence; Docker container verification when engine starts; user-selected public repo/Render deployment; eligibility/deadline confirmation; final video/deck/cover. Do not guarantee winning or zero bugs.
- Scope boundaries: hospital identity/email/staff credentials unverified; no password recovery or staff-role administration; synthetic data only. Registration scope supersedes earlier historical “no signup” notes. Existing SQLite data retained, not imported into Atlas.

The sections below are historical notes; latest checkpoints supersede earlier status.

# HealthBridge continuation memo
Updated 2026-10-03 after feature audit and light/dark implementation.

## User constraints
Mainstream stack; prefer free/open-source; flexible feature scope; real frontend/backend connection with no frontend business fixtures; conserve quota. **No screenshare, screenshots or browser automation.** Use terminal/API checks. Keep this memo current.

## Current status
Working local care-handoff prototype, not a fully completed hackathon submission. React/TypeScript/Vite + FastAPI + SQLite + local uploads. All patient/record/appointment/review/instruction data comes from API and persists server-side. Synthetic fixtures and public demo credentials live in backend/app/db.py, exposed through demo-only API. Frontend contains static labels/translations/design values only; localStorage stores theme preference, not clinical data.

## Verified this turn
- `npm --prefix frontend run build`: PASS (TypeScript and production bundle).
- `PYTHONPATH=backend .venv/bin/pytest backend/tests -q`: 13 PASS, including real text PDF extraction and installed Tesseract image OCR. One upstream Starlette/httpx deprecation warning; not a functional failure.
- `node --test frontend/tests/theme.test.mjs`: 5 PASS (saved preference, system preference, invalid preference, blocked storage).
- `node frontend/tests/connection.mjs`: PASS. Real frontend/src/api.ts client → Vite proxy → FastAPI → isolated SQLite. Verifies login/logout, persistent language, intake, upload/download, brief generation, patient review denial, clinician approval, instructions, audit. Script starts/stops temporary servers on 15173/18000 and removes its own temporary DB.
- `docker compose config --quiet`: PASS. Container runtime/build still unverified.
- Source search: no patient names/demo emails/passwords/appointment fixtures in frontend/src.
- No browser/screenshare used this turn. Earlier session saw patient login/dashboard; full interactive and final dark-mode visual QA not performed.

## Changes this turn
- ThemeToggle.tsx + public/theme.js: persistent light/dark switch on login and workspace, OS preference initial default, pre-render application to avoid flash, handles unavailable storage.
- Centralized CSS palette with dark surface/text overrides; print remains light; improved small supporting text and narrow-screen care-journey layout.
- Superseded briefs now become outdated so pending counts are accurate. Changed intake/uploads invalidate flagged briefs too. Stale versions cannot be approved.
- Whitespace-only clinician review/instructions rejected server-side.
- Invalid document dates remain unknown.
- Stale workspace refresh guarded when switching patients; VisitPrep keyed by patient to reset review-note form; patient switch disabled while generating.
- Brief notice discloses evidence selection/truncation and 12-document cap.
- Added reproducible terminal-only connection and theme tests.

## Implemented scope
Two roles, authenticated sessions/assignment checks, intake, record upload/extraction/OCR, metadata keyword classification, library/search/timeline, source viewer/download, source-linked brief, clinician review/flag/correction notes, audit trail, automatic outdated status, clinician-authored instructions with reviewed translation, browser print/save PDF. Core navigation English/Hindi/Kannada; auxiliary UI partly English. Local bundled fonts, responsive CSS, light/dark.

## Honest limits
- AI_BACKEND=extractive is deterministic source selection, NOT LLM inference. Configurable Ollama/ROCm/OpenAI-compatible adapter accepts verified literal excerpts; no remote model run performed. AMD hardware access unavailable. Model failure is explicit, never fake success.
- No automatic translation/simplification: clinician authors and confirms versions. No diagnosis/treatment generation. Source fidelity is not medical correctness.
- No self-registration, scheduling editor, separate admin/billing, voice or medication reminders. Deliberately deferred.
- Synthetic data only. Not production/compliance-certified. Demo-disabled mode does not remove existing public demo accounts.
- No final visual QA due explicit no-browser constraint. Do not claim zero issues.
- No Git repo initialized/public deployment/pitch/video yet. Docker execution and real AMD benchmark remain outstanding.

## Run / layout
README.md has exact commands. Backend: `.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`. Frontend: `npm --prefix frontend run dev` → http://127.0.0.1:5173.
Old long-running server sessions may no longer exist. Restart if needed; do not assume live preview remains running. Integration test uses its own ports and database.
Source: backend/app/{main,db,ai,documents}.py; frontend/src/{App,pages,forms,ui,ThemeToggle}.tsx; tests in both backend/tests and frontend/tests. App.tsx and pages.tsx are large; split by feature if extending.

## Hackathon / next required external work
See docs/HACKATHON.md, docs/AMD.md and docs/DEMO.md. Official event Oct 12–18 2026; meaningful live AMD execution required; Google/Evolus optional. Pasted brochure deadline Oct 18 19:30 IST conflicts with live detailed schedule “To be announced”; confirm. Pre-event code eligibility unverified because linked rulebook retrieval returned no readable body. Disclose this October 3 preparation. Need AMD credentials/runtime, real evidence/metrics, organizer confirmation, public deployment/repo and presentation assets before claiming submission complete.

## Submission preparation update
- User asked to make the project hackathon-ready. Created submission/PROJECT_DESCRIPTION.md and submission/PITCH_SCRIPT.md (recording script and six-slide outline, NOT final deck/video).
- Added .github/workflows/ci.yml: build, theme/API tests, real frontend connection test and Docker build. GitHub workflow has not run yet.
- backend/Dockerfile now installs requirements.lock.txt for reproducibility.
- scripts/benchmark_model.py sends 1–10 explicit synthetic model requests, measures latency/source coverage, saves a report without secrets, refuses extractive mode, does not fake remote GPU verification. Syntax and --help verified; live run requires endpoint.
- scripts/release_check.py checks files/engine and keeps external submission gates explicit. Syntax verified.
- gh auth status under sandbox initially misleadingly failed; escalated check VERIFIED valid GitHub account priyanshusharan-cmd. No repository published, no credentials exposed in files.
- Docker engine socket absent; binary present. Cannot run containers until Docker engine is started.
- Asked user asynchronously for AMD endpoint and desired GitHub/hosting destination; no response received at memo time. Do not ask for secrets in chat; use environment variables.
- Remaining: actual AMD workload/evidence; Docker run; public repo and demo destination; organizer eligibility/cutoff confirmation; final cover/deck/video. Do not label this fully submission-ready.

## Interaction repair update
User reported logo/avatar/privacy label were inert. Added clickable workspace logo → Overview, both avatars → editable account modal, privacy label/footer → substantive demo privacy notice. Account changes (name, age, language, derived initials) persist via PATCH /api/me; email/role remain protected. Added backend regression test. No browser/screenshare. docs/MANUAL_SETUP.md lists exact external tasks; MongoDB is not required. Continue to distinguish static UI copy from seeded backend demo data. No claim of zero issues or full click-level verification.

## Latest continuation — completed interaction/localization repair
- My workspace is now a navigation button to Overview; workspace logo and both avatars are functional. Privacy notice reachable in top bar and footer.
- Central LocaleContext/useText plus 270+ bilingual phrases in frontend/src/locales/ui.json (editable source ui.tsv). Static headings, forms, tooltips, account/privacy, system activity labels and dates now localized. Theme controls localized too. Clinical records, patient prose and reviewer notes intentionally preserve source language. Do not use automatic medical translation.
- Added frontend/tests/localization.test.mjs using React server rendering (no browser): Hindi/Kannada activity, account/privacy, source preservation and dictionary coverage. npm test now runs all *.test.mjs.
- Checks: production build PASS; backend 14 PASS; frontend 11 PASS; real frontend API → proxy → SQLite integration PASS, now including profile name/age/initials and persisted language.
- Critical running-instance issue found: port 8000 was serving OLD Profile schema with only language. Verified PID 2733 command/cwd belonged to this repo, stopped it gracefully, restarted with --reload --reload-dir backend/app. New process exec session 59954 (reloader 3335, worker 3338 at start). SQLite preserved. Frontend PID 2755 belongs to frontend directory and Vite hot reload remains running.
- No screenshots, screenshare or automated browser used. No MongoDB needed. docs/MANUAL_SETUP.md explains only external steps remaining.
- Source-only model mode, actual AMD, Docker/deployment and submission limitations described earlier still apply. Do not claim zero defects or automatic clinical translation.

## 2026-10-06 — MongoDB and regional-language continuation (supersedes old SQLite-only notes)
- User chose a NEW HealthBridge Atlas project/cluster; **never use or change Ridify**. User explicitly authorized placing the screenshot-provided credential into root `.env`. Stored there only, chmod 0600; ignored by Git and Docker. Do not print or copy the credential into memos. User should rotate exposed password before publication and restrict the Atlas Admin user. No browser/screenshare used.
- Added repository operations in backend/app/store.py. Routes now use explicit CRUD, not SQL. SQLite remains offline option; MONGODB_URI chooses MongoDB with transactional writes, indexes, audit counter. Root `.env` auto-loads, process env takes precedence. Mongo failures never fall back to SQLite.
- Upload bytes now stored atomically in separate `files` collection/table with metadata/audit (10MiB maximum). Mongo document cap is 16MiB. Legacy SQLite uploads can still download from disk. Existing SQLite data remains untouched; no import of its old edits into Atlas.
- Live Atlas ping PASS. Running localhost:8000 health was checked and reports `database: mongodb`, `ai_backend: extractive`, `amd_verified:false`.
- Tests: 17 backend pass with isolated SQLite AND with isolated real Atlas databases, cleaned afterward. Real frontend API -> Vite -> FastAPI -> Atlas workflow PASS with isolated temporary database and cleanup; includes profile, language list, appointments, files, brief/review/instructions. Frontend 11 tests and production build passed before latest small navigation/focus edits; rerun final checks as needed.
- Added editable appointment details (API checks ownership and future timezone-aware time; not real booking). Appointment changes invalidate briefs and generate audit. Removed fixed IST display; device timezone used consistently.
- Backend `/api/languages` exposes 28 care languages in regional groups. Shared LanguageSelect fetches options. Intake preference and clinician-authored reviewed translations accept those codes; RTL fields use dir=auto. **Full interface translations remain EN/HI/KN**, do not claim 28 translated interfaces or automatic clinical translations.
- Fixed record-viewer request race, added session-expiry handling and hash navigation (back/forward), keyboard focus and reduced-motion polish. Light/dark retained.
- Root Dockerfile + render.yaml bundle frontend and backend into ONE Render service. STATIC_DIR mounts built frontend. RENDER_EXTERNAL_URL allowed for same-origin CSRF checks; custom domains need CORS_ORIGINS. Cookie secure true for hosted deployment. Docker engine still unavailable, container build/run not verified. No public deployment/repo publication performed.
- Updated docs/MANUAL_SETUP.md, TRACK_READINESS.md, README and submission description. Track alignment: traceable visit preparation with human review, not diagnosis. Real AMD workload/evidence, organizer eligibility/cutoff confirmation, public repo/demo and final recording/deck/cover remain outstanding.

### Final continuation guide — conserve quota
User reports 25% quota remaining. Avoid broad repeated scans and browser tools. Start with this memo and docs/MANUAL_SETUP.md. Do not read or print `.env`; secrets are already configured.

Completed checks: frontend production build; 11 frontend tests; 17 backend workflows on both SQLite and REAL Atlas; frontend real-HTTP integration on both stores. One additional production static-server/secure-cookie/origin test was added (18 local total when it passes). Docker engine absent; no need to repeat Docker probes until user starts it.

Precise changed files: backend/app/{db,store,main,languages}.py; backend/tests/test_workflow.py; requirements and lock; frontend/src/{App,Account,forms,pages,api,types,LanguageSelect,AppointmentForm}.tsx/ts; CSS and locale catalogs; integration and localization tests; root Dockerfile/.dockerignore/render.yaml; scripts/cleanup_test_database.py; CI/docs.

Live app health on port8000 confirmed MongoDB; Vite5173 proxies it. Existing server was already running with reload; no unrelated processes stopped. Atlas tests use unique test DB names and clean only those. App workspace uses healthbridge, with explicit synthetic fixtures. Prior SQLite data is retained, not imported.

Continue only where evidence warrants: actual AMD endpoint/configuration and benchmark; Docker build when engine available; user-selected GitHub/Render deployment; manual UI walkthrough (user prohibits agent browser use); final deck/video/cover and eligibility confirmation. A fresh UI language beyond EN/HI/KN needs a complete reviewed translation catalog, not a flag or English fallback. 28 care languages means stored intake language and human-reviewed instruction text, not 28 UI translations.

Known boundaries: public shared demo accounts, no signup or clinical production readiness, no automatic clinical translation, appointment editor records an arranged appointment rather than booking with a provider. Never claim zero defects or fully submitted. Exposed password should be rotated by user; store new value only privately.

Final verification confirmed: **18/18 local backend tests**, **11/11 frontend tests**, production frontend build PASS. The extra production-serving check passed (built UI and API on one origin, secure session cookie, valid origin accepted, foreign origin rejected). Earlier live Atlas run remains **17/17** plus real frontend HTTP integration PASS; the additional production-serving test is deliberately local. No outstanding test failures.

## Focused follow-up at user's 20% quota warning
No browser/screenshare, no redesign or new service dependencies. Fixed observable workflow edge cases:
- `frontend/src/pages.tsx`: instruction version selection is now independent per card (previously clicking one changed every card); selected buttons expose aria-pressed. Review notes/errors reset when brief ID changes, preventing old draft corrections carrying into a newly generated brief. Missing ages no longer render a dangling age label.
- `frontend/src/App.tsx`: clinician-list fetch ignores results after account changes/unmount. Workspace refresh checks both patient AND account identity, and rechecks before applying refreshed patient lists. This prevents late requests restoring stale clinician data after logout.
- `backend/app/main.py`: appointments sorted by parsed timezone-aware instants, not ISO-string order. `frontend/src/ui.tsx`: date-only record dates parsed as local calendar dates, so western timezones do not show the previous day.
- Regression tests: mixed-offset appointments in backend workflow tests; calendar-date rendering with America/Los_Angeles in frontend localization tests.
- Verified production build PASS, 19 local backend tests PASS, 12 frontend tests PASS. Targeted new Atlas timezone regression launched separately; confirm result below. Prior full Atlas/HTTP evidence remains above. No need to rerun unchanged full suites just to continue.
- Remaining external work unchanged: rotate exposed credential, actual AMD model run/evidence, Docker engine/container check, chosen public repository/Render deployment, final submission assets and eligibility confirmation. Still 3 full UI languages and 28 care-content languages, not 28 translated interfaces. Do not overstate readiness.
Targeted Atlas timezone regression: PASS (1 test, isolated test database cleaned). No known failing tests at this stopping point.

## 2026-10-07 continuation — responsive layout and connection recovery
- Last Oct6 frontend restart was rejected because automatic approval review hit the account usage limit (not because the action was unsafe). CSS build nevertheless passed; frontend5173 was stopped, backend8000 still listened. Do not bypass approval checks; retry only through normal approved tools.
- Responsive CSS appended to styles.css: fluid grid/type/spacing, single-column login at <=900px, shorter laptop layout at height<=800px, dynamic viewport dialog height, min-width zero on grid children, scrollable tabs/sidebar, mobile 44px primary touch targets and 16px form text. Handles <=430px topbar/forms and wrapped patient selectors. No browser visual QA performed, as prohibited.
- Added API request timeouts (30s ordinary,180s model brief), actionable network errors, and explicit caller-abort preservation. Added Login retry-connection action; successful health retry reloads backend demo accounts. Sign-in actions disabled while disconnected, preventing futile submissions.
- Decisions: preserve current restrained visual design; do not use static fake clinical fallbacks when backend fails. Layout checks cannot replace actual visual QA; user can resize the preview manually. Existing Atlas and workflow evidence remains valid; only changed client checks/build needed this turn.
- Never print/read .env contents or mention credential values in this handoff. Ridify must remain untouched. User wants concise updates and conservation of quota. Save implementation decisions/evidence, not hidden reasoning.

Oct7 final results: frontend production build PASS; **15 frontend tests PASS** (new network failure/timeout/cancellation/upload validation coverage); actual frontend API -> Vite -> FastAPI -> isolated SQLite integration PASS. Live http://127.0.0.1:5173/api/health returns status=ok,database=mongodb. Vite preview running in exec session7537 at5173. Last backend suite remains19 PASS and prior Atlas evidence remains above; backend unchanged this turn, so no repeated remote suite. Automatic approval succeeded normally when retried Oct7; previous quota-review failure is resolved for the frontend restart. No browser/screenshare used. No remaining test failures. Visual viewport verification and AMD/public submission gates still outstanding.

## Oct7 extended onboarding/navigation — WORK IN PROGRESS checkpoint
User requested patient/hospital account creation and two-finger navigation. Latest steering says colours are nice; **preserve palette**, do not recolour. No browser/screenshare authorized; continue terminal-only.
Added backend/app/onboarding.py with public patient/hospital registration, hospital organizations/memberships, email-bound 24h single-use patient invitations, existing patient acceptance. Hospital accounts have clinician role but see no patients until invitation acceptance adds an explicit assignment. Uses actual database, password hashes, transaction, duplicate email checks; registration does NOT verify professional credentials. New collections/tables added via store.py/db.py initialize, preserving existing users/fixtures. Main mounts onboarding router before static UI. Frontend Onboarding.tsx provides register/invite/join, hospital patient toolbar, private invite link/copy, Account org label; User.organization optional. Complete localization entries added for EN/HI/KN.
Added useHistoryNavigation.ts: real browser hash history with back/forward controls and bounded horizontal trackpad wheel handler. Does not consume pinch, vertical scrolling, editable fields, dialogs or horizontally scrollable tabs. Has 650ms momentum cooldown. Native OS gesture behavior remains browser-dependent and unverified. No promise of Chrome-identical native gestures.
Build/tests pending at this checkpoint. Inspect only these changes and run relevant checks. Critical next checks: fresh registered patient has EMPTY workspace; hospital has EMPTY assignments; wrong-email/expired/reused invitation rejected; cross-hospital access denied; tokens stored hashed; duplicate signup clean conflict; refresh/session persistence. Run real isolated Atlas subset after local tests. Do not expose secrets or test real workspace mutations.

Oct7 onboarding checkpoint: production build PASS, 16 frontend tests PASS (includes wheel gesture protection/momentum via simulated events, no browser); 22 local backend tests PASS. New account isolation/email-bound invitation/rollback tests added. New real frontend client integration includes patient/hospital signup, empty workspaces, invitation acceptance and assignment checks. Live Atlas onboarding subset and updated local HTTP test running; results below when complete.
Demo-account labels now read persisted user names/roles from backend, instead of fixed labels after profile edits. Sample identities remain intentionally seeded and disclosed. Hospital invitation creation capped at30 active invitations per clinician. Palette preserved. Self-registered hospital owners are not professionally verified; email verification/password recovery/staff-role administration remain explicit limitations. docs/MANUAL_SETUP.md appended account flow and gesture caveats, superseding earlier no-registration scope.

Final extended onboarding/navigation results: 22 backend tests PASS locally,16 frontend tests PASS, production build PASS, updated real client HTTP integration PASS (including signup/invite). Three focused onboarding tests on real Atlas PASS and isolated test DBs cleaned. Backend startup completed; live frontend proxy health PASS with MongoDB. Preserve colours per latest user correction. No browser/screenshare used, no hardware gesture visual verification. Native gestures and final visual polish require user manual check; submission gates remain explicit above.

## Oct7 account security and typography — current checkpoint
User explicitly wants no visible back/forward buttons, preserved colours, no browser automation/screenshare, and clear spacing. Fixed login `to better care`, mobile `Good care starts with understanding`, and Account/Role label spaces. Removed visible history controls; gesture hook retained. Build passed before final localization additions.
Auth: registration issues cookie in same transaction as account creation; successful logins no longer consume failed-attempt quota; switching accounts invalidates previous browser session. Added current-password-verified password change (15-character minimum, rate-limited), revokes other sessions, rotates current cookie; logout-all endpoint. Shared demo passwords protected. Added backend-derived is_demo flag. Password fields masked with accessible Show/Hide buttons, account modal has visible logout/all-devices/privacy actions, sticky Close header. Signup back-to-sign-in actually opens login form. Added security headers and production same-origin CSP. Preserved palette.
New HI/KN strings added to ui.json/ui.tsv. Local backend suite running session74917; latest build previously passed. Must finish frontend checks/build, real HTTP integration, and record results. Tests added for old-cookie replay, password session revocation, demo protection, atomic signup despite exhausted login limiter. Email verification/recovery and professional hospital verification remain unavailable; do not claim production medical readiness. AMD actual run/evidence and public submission gates remain outstanding. Never store secrets or private chain-of-thought here; this memo records implementation decisions, evidence and next actions.

### Final results for account security / typography update
- **24 local backend tests PASS; 18 frontend tests PASS; production build PASS.** Heading SSR regression verifies `to better care.` and `Good care starts with understanding.` retain spaces when mobile line breaks are hidden. Password fields start masked. Heading tracking now uses proportional, less-tight values; palette unchanged.
- Real frontend client -> Vite -> FastAPI -> isolated SQLite workflow PASS, including private signup/hospital invitations. Two focused security/session tests on real isolated Atlas databases PASS; cleanup completed. Tests cover password changes, old-session rejection, logout/all-device invalidation, atomic signup and failed-attempt quota behavior. Initial HTTP run hit sandbox port restrictions; normal approved rerun passed. No browser automation or screen sharing used.
- Shared-demo status now comes from backend `is_demo`, not email suffix. Visible in-app back/forward controls removed; account modal logout visible on narrow screens. Password fields include reveal controls, current-password validation, and new-password confirmation. EN/HI/KN strings updated. docs/MANUAL_SETUP.md updated.
- Remaining limits: no email verification/recovery provider, no independent hospital credential verification; rate limiter is process-local (needs shared storage for multi-instance deployments). UI still only fully localized EN/HI/KN, with28 regional care-content options. No claim every real browser/device interaction has been visually verified. Actual AMD workload/evidence, Docker runtime check, public deployment, credential rotation and submission assets remain outstanding. Preserve user restrictions and current palette. This is an implementation handoff, not private reasoning.

## Oct7 latest: eight-character passwords and account-flow review
Supersedes the previous15-character policy: user explicitly requested8. Signup AND password-change backend validation and both frontend forms now require8; helper copy translated EN/HI/KN. Login continues accepting existing passwords without imposing a new minimum. Signup adds confirm-password validation, removes confirmation before request, blocks duplicate/inactive-connection submits. Sign-in form shown by default rather than hidden. Mask/reveal remains user-controlled.
Reviewed onboarding/app state beyond tests. Added hospital patient-list Refresh action, preserving selected patient if still assigned and guarding async updates against account switches. Hospital owner can retrieve a patient after invitation acceptance without a page reload. Invitation code trims accidental surrounding spaces; accepted invitations no longer consume pending-invitation cap; invitations to hospital owners/already-associated patient accounts rejected rather than producing unusable links.
Validation:25 local backend tests PASS;18 frontend tests PASS;production build PASS. Expanded real HTTP integration uses8-character signup, password change, logout, login and persisted identity; result recorded below. No browser/screenshare used. Complete visual interaction verification still not performed. Email recovery/verification, professional hospital verification, shared multi-instance rate limiting, AMD evidence and deployment remain explicit gaps; never claim all logic is complete or guarantee hackathon win. Colours preserved.
Eight-character real HTTP integration PASS (frontend API through Vite/FastAPI/isolatedSQLite), including password change and re-login. No known failing automated checks at this checkpoint.

Oct7 footer copy: user requested removing hackathon mentions from website. Replaced login footer with plain HealthBridge and updated EN/HI/KN catalog entries. Source search found no other hackathon wording in frontend/src or backend/app. Kept internal submission documentation and factual synthetic-data notices. Production build PASS.
