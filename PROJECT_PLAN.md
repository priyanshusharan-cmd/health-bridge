# HealthBridge build plan

Decision date: 3 October 2026. The supplied feature lists are inspiration; prioritize a complete, credible care handoff over a large hospital suite.

## Product
A patient brings scattered records and concerns. HealthBridge prepares a source-linked visit brief. A clinician corrects and approves it, then publishes understandable follow-up instructions. Synthetic data only.

## Stack
React + TypeScript + Vite, Tailwind CSS, Lucide; FastAPI + Pydantic; SQLite (zero-service local setup); pdfplumber + Tesseract; OpenAI-compatible inference interface for Ollama locally or vLLM on AMD ROCm. No paid API required. PostgreSQL is a future migration, not a hackathon dependency.

## Delivery
1. Persistent backend, demo accounts, role checks, record extraction, review/audit workflow.
2. Calm, polished responsive patient and clinician workspaces; functional intake, uploads, timeline, source viewer, brief, instructions, print/export.
3. Strict source validation for model extraction; visibly labeled extractive fallback; no fabricated inference or AMD telemetry.
4. Focused security and workflow tests, browser smoke checks, Docker, deployment and demo documentation.
5. AMD live inference and benchmark evidence require actual AMD access; distinguish implemented support from verified execution.

## Scope choices
Keep patient and clinician roles, English/Hindi/Kannada navigation and intake, document provenance, review gating, portable summary. Defer separate admin suite, billing/insurance, voice, vector databases, fine-tuning and medication reminders. Translations are drafts requiring human review; never claim language validation not performed.

## Hackathon findings
Source: https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii (checked 2026-10-03).
Online phase: October 12–18, 2026. Meaningful AMD execution in the demonstrated product is required. Health track requires uncertainty handling and human review; no autonomous medical advice. Google/Evolus are optional. Public repository, application URL, cover, demo video and pitch are submission items. Current detailed schedule says “To be announced”; do not assume the pasted October 18 19:30 IST deadline is confirmed.
The linked general rulebook and submission guide returned no readable body through web retrieval. Pre-event code policy and exact submission cutoff remain unverified; disclose all work prepared before kickoff and confirm policy with organizers. Do not represent this preparation as event-period work.

## Budget discipline
One model request per explicit generation, bounded source length/output, one retry for invalid output, persistent results, no automatic background inference. Deterministic extraction mode for UI/testing without downloads or cloud spend. No partner services until core journey works.
