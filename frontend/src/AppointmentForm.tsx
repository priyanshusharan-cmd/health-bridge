import { useState, type FormEvent } from "react";
import type { Workspace } from "./types";
import { post } from "./api";
import { useText } from "./locale";
import { Spinner } from "./ui";
export function AppointmentForm({patientId, initial, onSaved}: {
  patientId: string; initial?: Workspace['appointments'][number]; onSaved: () => Promise<void>;
}) {
  const tr = useText();
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const localDate = initial ? new Date(new Date(initial.starts_at).getTime() - new Date(initial.starts_at).getTimezoneOffset()*60000).toISOString().slice(0,16) : '';
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError('');
    const values = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await post(`/patients/${patientId}/appointments`, {...values, id: initial?.id, starts_at: new Date(String(values.starts_at)).toISOString()});
      await onSaved();
    } catch(e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <form className="form-body" onSubmit={save}>
    <p className="form-intro">{tr("Keep the details of an appointment you have arranged. This does not book a visit with the clinic.")}</p>
    <label>{tr("Clinician")}<input name="clinician" required minLength={2} maxLength={120} defaultValue={initial?.clinician} /></label>
    <label>{tr("Specialty")}<input name="specialty" required minLength={2} maxLength={120} defaultValue={initial?.specialty} /></label>
    <label>{tr("Location")}<input name="location" required minLength={2} maxLength={250} defaultValue={initial?.location} /></label>
    <label>{tr("Date and time")}<input name="starts_at" type="datetime-local" required defaultValue={localDate} /></label>
    <small>{tr("Times use your device timezone.")}</small>
    {error && <p role="alert" className="field-error">{tr(error)}</p>}
    <div className="form-footer"><button className="button primary" disabled={busy}>{busy && <Spinner />}{tr("Save appointment")}</button></div>
  </form>;
}
