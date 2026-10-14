# HealthBridge Authorization and Membership Architecture

## 1. Single-Hospital Membership Bound

In HealthBridge, clinician/hospital accounts have an explicit single-organization boundary (`memberships` table):
- Each hospital user (`role: clinician`) is linked to exactly one organization (`memberships.organization_id`).
- Patient accounts are created either unassigned or explicitly linked to an organization via single-use, 24-hour invitation tokens (`/api/hospital/invitations` and `/api/hospital/join` or `/api/auth/register`).
- A patient can belong to only one hospital organization at any given time. Attempting to accept an invitation to a second hospital returns `HTTP 409: This account already belongs to a hospital workspace.`

## 2. Explicit Assignment Model vs. All-Staff Access

HealthBridge strictly rejects implicit "all-staff" or cross-hospital access:
- A clinician belonging to an organization can only read or modify patient data if an explicit record exists in the `assignments` table (`clinician_id` and `patient_id`).
- When an assignment is unlinked via `/api/hospital/assignments/{patient_id}/unlink`:
  - The link is severed atomically.
  - Future reads/writes by that clinician are immediately rejected with `HTTP 403 Forbidden`.
  - The patient's records, briefs, corrections, and instructions remain 100% intact.
- Multi-staff or inter-hospital referral capabilities require an explicit authorization model (e.g. delegated access tokens, dual-party approval) and cannot be implemented as blanket staff privileges.

## 3. Scoped Record Removal and Provenance Invalidation

- Removing or withdrawing a record marks it as `withdrawn` (tombstone) and records a clinical audit event.
- Crucially, record removal invalidates dependent visit briefs (`con.invalidate(patient_id)` marks them as `outdated`), ensuring that no stale excerpt or broken citation can be presented as verified clinical evidence.
- Raw file bytes for withdrawn records are immediately inaccessible via `GET /api/records/{id}/file`.

## 4. Instruction Lifecycle and Review Safeguards

- Publishing instructions requires either an approved visit brief and resolved clarification questions, or an explicit clinician override reason.
- Historical instructions remain immutable with version numbering (`v1`, `v2`, etc.).
- Patient acknowledgements are version-bound and explicitly recorded as patient assertions, not proof of clinical comprehension.
