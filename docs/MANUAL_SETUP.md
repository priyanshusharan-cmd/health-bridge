# What you still need to do

## MongoDB — connected
The separate HealthBridge Atlas project is connected. The local app loads the private root `.env` automatically. `MONGODB_URI` and `MONGODB_DATABASE=healthbridge` select Atlas; an empty URI selects SQLite for offline development. A failed Atlas connection does not silently fall back to SQLite.

Records, profiles, appointments, intake, reviews, instructions, audit events and new uploaded file bytes are persisted in the selected database. MongoDB writes use transactions. Uploads are capped at 10 MiB and stored separately from record metadata, below MongoDB's document size limit. Render does not need a disk for these MongoDB uploads. Old SQLite data remains untouched in `backend/data`; switching databases does not import historical local changes.

The credential supplied in chat was saved only to `.env` (owner-only permissions, ignored by Git and Docker). **Change that exposed password before public deployment** and replace it in `.env` and Render. Prefer a database user restricted to read/write on `healthbridge`; the automatically generated Atlas Admin account has unnecessary privileges. Restrict Atlas network access to your development IP and hosting outbound IPs when available. No further database or collection setup is needed.

## Render — one service for frontend and backend
1. Publish this repository to your chosen GitHub repository. Never include `.env` or `backend/data`.
2. In Render, create a Web Service from the repository and choose Docker. Use the root `Dockerfile`; it builds and serves both UI and API. `render.yaml` is also supplied for a Blueprint deployment. Check the offered plan before confirming costs.
3. Add private environment variables `MONGODB_URI` (new password) and `MONGODB_DATABASE=healthbridge`.
4. Set `COOKIE_SECURE=true`, `DEMO_ENABLED=true` and initially `AI_BACKEND=extractive`.
5. Deploy. The service uses Render's `PORT`; health check is `/api/health`. Render's external URL is accepted as the application origin. For a custom domain, also set `CORS_ORIGINS=https://your-domain`.
6. Open the HTTPS URL and manually check patient and clinician workflows. `/api/health` should report `database: mongodb`. No separate frontend API URL or MongoDB browser key is needed.

Docker packaging has not been executed locally because Docker Desktop's engine is not running. Start Docker Desktop if you want the container checked locally. The equivalent production static-server path is testable without Docker; container verification remains a separate check.

## AMD — required for the hackathon
Obtain the event's AMD cloud access. Personally owning an AMD GPU is not required. Configure the backend with `AI_BACKEND=rocm`, `AI_BASE_URL` (OpenAI-compatible model server `/v1` URL), `AI_MODEL`, and `AI_API_KEY` if that server requires authentication. Use HTTPS and protect the endpoint. Never put the key into frontend variables.

No Gemini, OpenAI or Hugging Face key is required for the current source-only demo. A Hugging Face model may require accepting its license; that depends on the selected model. Source-only mode is not AI inference and does not fulfil the meaningful AMD-workload requirement. Run `scripts/benchmark_model.py` against the real AMD model and retain hardware/runtime evidence.

## Submission
- Confirm registration, exact cutoff, and eligibility of code prepared before the event.
- Supply the public repository and working HTTPS demo URLs.
- Record a synthetic patient case end to end, including clinician review and the real AMD workload.
- Complete the pitch deck/cover/video; current submission files are text drafts and a recording script.

## Language scope
The API lists 28 care-content languages grouped by region. Intake preferences and clinician-reviewed translations support these codes, including right-to-left text. The complete interface languages are English, Hindi and Kannada. Selecting a care language does not automatically translate records or generate medical instructions. Scanned-document OCR is a separate capability; broad validated OCR coverage is not claimed.

## Product scope
Profile, navigation, privacy notice, theme, record uploads/downloads, timeline, intake, appointment details, briefs, review, instructions and audit are wired to real behavior. Appointment details are a personal record, not a clinic booking integration. Demo accounts are deliberately shared synthetic accounts; production medical compliance and hospital/staff identity verification are not implemented. Private account creation and patient invitations are described below. Static interface labels and illustrations are normal UI assets, not fabricated patient data.

## Account creation and hospital workspaces (Oct7 update)
Use **Create account** on the login page to create a patient account or a hospital/clinic workspace. New workspaces contain no seeded clinical records. Hospital owners can use **Patients → Invite a patient** to create a private link bound to the patient's email. It expires in 24 hours and can be accepted once. A new patient enters the code during signup; an existing patient accepts it from their profile. This adds an explicit assignment before the hospital can see that patient's workspace.

These are self-registered prototype accounts. Email verification, staff credential verification, password recovery, multiple clinician/staff roles and hospital identity verification are not implemented. Keep using synthetic data; do not deploy this as a clinical hospital system. Earlier references in this document to “no self-registration” are superseded by this update.

Back/forward controls follow real browser history. A horizontal trackpad handler supports in-app history navigation while preserving vertical scrolling, pinch, fields, dialogs and horizontal tabs. Native macOS/browser two-finger gestures still depend on the host browser; manually check your hardware. Palette was retained at the user's latest request.

### Account-security update (October 7)
New accounts require at least 8 password characters. Signup establishes the session atomically. Account settings offers masked/revealable password fields, password change with current-password confirmation, sign out, and sign out all devices. Password changes revoke other sessions. Shared demo passwords cannot be changed. Email verification, email-based password recovery, and hospital credential verification are not implemented; do not present self-registered hospitals as verified. Before public deployment, rotate the previously exposed database password and restrict database network access appropriately.
