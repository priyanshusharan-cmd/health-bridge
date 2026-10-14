import { LanguageSelect } from "./LanguageSelect";
import { useText, useLocale, locales } from "./locale";
import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Check,
  FileText,
  ShieldCheck,
  Upload,
  X,
} from "lucide-react";
import { api, post } from "./api";
import type { Intake, Language, RecordItem, Instruction } from "./types";
import { translations } from "./i18n";
import { Badge, useDate, Spinner } from "./ui";
export function IntakeForm({
  patientId,
  initial,
  language,
  t,
  onSaved,
}: {
  patientId: string;
  initial: Intake | null;
  language: Language;
  t: typeof translations.en;
  onSaved: () => Promise<void>;
}) {
  const tr = useText();
  const date = useDate();
  const locale = locales[useLocale()];

  const [careLanguage, setCareLanguage] = useState(initial?.language || language);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    const fields = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await post(`/patients/${patientId}/intake`, { ...fields, language: careLanguage });
      await onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="form-body">
      <p className="form-intro">{tr(t.intakeHint)}</p>
      <label>{tr("Preferred care language")}<LanguageSelect value={careLanguage} onChange={setCareLanguage} /></label>
      <small>{tr("Care languages apply to your intake and reviewed instructions. Interface languages are English, Hindi and Kannada.")}</small>
      <Badge tone="blue">
        {tr("Patient-provided information · clinician review required")}
      </Badge>
      <label>
        {tr(t.reason)}
        <textarea
          name="reason"
          required
          minLength={5}
          maxLength={3000}
          defaultValue={initial?.reason}
          rows={3}
          placeholder={tr("Tell us what brought you here…")}
        />
      </label>
      <div className="form-grid">
        <label>
          {tr(t.duration)}
          <input
            name="duration"
            maxLength={200}
            defaultValue={initial?.duration}
          />
        </label>
        <label>
          {tr(t.allergies)}
          <input
            name="allergies"
            maxLength={1000}
            defaultValue={initial?.allergies}
            placeholder={tr(t.notProvided)}
          />
        </label>
      </div>
      <label>
        {tr(t.medications)}
        <textarea
          name="medications"
          maxLength={1000}
          rows={2}
          defaultValue={initial?.medications}
          placeholder={tr(t.notProvided)}
        />
      </label>
      <label>
        {tr(t.questions)}
        <textarea
          name="questions"
          maxLength={2000}
          rows={3}
          defaultValue={initial?.questions}
        />
      </label>
      {error && (
        <div className="error-banner" role="alert">
          {tr(error)}
        </div>
      )}
      <div className="form-footer">
        <small>
          {tr("Saving new information makes earlier briefs outdated.")}
        </small>
        <button className="button primary" disabled={busy}>
          {busy ? <Spinner /> : <Check size={17} />} {tr(t.save)}
        </button>
      </div>
    </form>
  );
}
export function UploadForm({
  patientId,
  onSaved,
}: {
  patientId: string;
  onSaved: () => Promise<void>;
}) {
  const tr = useText();
  const date = useDate();
  const locale = locales[useLocale()];

  const [file, setFile] = useState<File | null>(null),
    [ocrLang, setOcrLang] = useState<string>("en"),
    [busy, setBusy] = useState(false),
    [progressMsg, setProgressMsg] = useState(""),
    [error, setError] = useState(""),
    [drag, setDrag] = useState(false);
  const select = (f: File | undefined) => {
    setError("");
    if (!f) return;
    if (f.size > 10 * 1024 * 1024) {
      setError("Please choose a file smaller than 10 MB.");
      return;
    }
    if (!/\.(pdf|png|jpe?g|txt)$/i.test(f.name)) {
      setError("Choose a PDF, PNG, JPG or TXT file.");
      return;
    }
    setFile(f);
  };
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    setProgressMsg("Queuing document for extraction…");
    const body = new FormData();
    body.append("file", file);
    body.append("ocr_lang", ocrLang);
    const key = `upload-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    body.append("idempotency_key", key);
    try {
      const job = await api<{ id: string; state: string; error_message?: string; record_id?: string }>(
        `/patients/${patientId}/upload-jobs`,
        { method: "POST", body }
      );
      let attempts = 0;
      let currentJob = job;
      while (currentJob.state !== "completed" && currentJob.state !== "failed" && attempts < 60) {
        await new Promise((r) => setTimeout(r, 800));
        attempts++;
        setProgressMsg(
          currentJob.state === "processing"
            ? "Extracting document pages and OCR…"
            : "Queued for processing…"
        );
        currentJob = await api<{ id: string; state: string; error_message?: string; record_id?: string }>(
          `/upload-jobs/${job.id}`
        );
      }
      if (currentJob.state === "failed") {
        throw new Error(currentJob.error_message || "Document extraction failed.");
      }
      if (currentJob.state !== "completed") {
        throw new Error("Document processing is taking longer than expected. Please check your workspace in a moment.");
      }
      await onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setProgressMsg("");
    }
  };
  return (
    <form className="form-body" onSubmit={submit}>
      <p className="form-intro">
        {tr("A report, a referral, a visit note — keep it together here.")}
      </p>
      <label
        className={`drop-zone ${drag ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          select(e.dataTransfer.files[0]);
        }}
      >
        <span className="upload-icon">
          <Upload size={26} />
        </span>
        <strong>{tr(file ? file.name : "Drop your record here")}</strong>
        <span>
          {tr(
            file
              ? `${(file.size / 1024).toFixed(1)} KB · ${tr("Click to replace")}`
              : "or click to browse files",
          )}
        </span>
        <small>{tr("PDF, PNG, JPG or TXT · up to 10 MB · 20 PDF pages")}</small>
        <input
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.txt"
          onChange={(e) => select(e.target.files?.[0])}
          disabled={busy}
        />
      </label>
      <label>
        {tr("OCR language pack")}
        <select value={ocrLang} onChange={(e) => setOcrLang(e.target.value)} disabled={busy}>
          <option value="en">English (eng)</option>
          <option value="hi">Hindi (hin)</option>
          <option value="kn">Kannada (kan)</option>
        </select>
      </label>
      <div className="info-strip">
        <ShieldCheck size={18} />{" "}
        {tr(
          "Synthetic demo records only. Please do not upload real medical data.",
        )}
      </div>
      {error && (
        <div className="error-banner" role="alert">
          {tr(error)}
        </div>
      )}
      <div className="form-footer">
        <small>
          {progressMsg
            ? tr(progressMsg)
            : tr(
                busy
                  ? "Extracting text and saving your record…"
                  : "Original files stay available for review.",
              )}
        </small>
        <button className="button primary" disabled={!file || busy}>
          {busy ? <Spinner /> : <Upload size={16} />}{" "}
          {tr(busy ? "Processing…" : "Add record")}
        </button>
      </div>
    </form>
  );
}
export function RecordViewer({
  id,
  clinician = false,
  onUpdated,
  onDeleted,
}: {
  id: string;
  clinician?: boolean;
  onUpdated?: () => Promise<void> | void;
  onDeleted?: () => void;
}) {
  const tr = useText();
  const date = useDate();
  const locale = locales[useLocale()];

  const [record, setRecord] = useState<RecordItem | null>(null),
    [error, setError] = useState(""),
    [correcting, setCorrecting] = useState(false),
    [corrKind, setCorrKind] = useState(""),
    [corrDate, setCorrDate] = useState(""),
    [corrProvider, setCorrProvider] = useState(""),
    [corrReason, setCorrReason] = useState(""),
    [corrBusy, setCorrBusy] = useState(false),
    [corrError, setCorrError] = useState("");

  const load = () => {
    api<RecordItem>(`/records/${id}`)
      .then((value) => {
        setRecord(value);
        setCorrKind(value.kind);
        setCorrDate(value.date || "");
        setCorrProvider(value.provider);
      })
      .catch((e) => setError(e.message));
  };

  useEffect(() => {
    setRecord(null);
    setError("");
    load();
  }, [id]);

  const submitCorrection = async (e: FormEvent) => {
    e.preventDefault();
    if (!record) return;
    setCorrBusy(true);
    setCorrError("");
    const latestVersion =
      record.corrections && record.corrections.length > 0
        ? record.corrections[record.corrections.length - 1].version
        : 1;
    try {
      const updated = await api<RecordItem>(`/records/${id}/metadata`, {
        method: "PATCH",
        body: JSON.stringify({
          kind: corrKind,
          date: corrDate || null,
          provider: corrProvider,
          reason: corrReason,
          expected_version: latestVersion,
        }),
      });
      setRecord(updated);
      setCorrecting(false);
      setCorrReason("");
      onUpdated?.();
    } catch (err) {
      setCorrError((err as Error).message);
    } finally {
      setCorrBusy(false);
    }
  };

  return (
    <div className="record-viewer">
      {error ? (
        <div className="error-banner" role="alert">
          {tr(error)}
        </div>
      ) : !record ? (
        <div className="empty">
          <Spinner />
          {tr("Loading original source…")}
        </div>
      ) : (
        <>
          <div className="viewer-title">
            <div>
              <Badge>{tr(record.kind)}</Badge>
              <h2>{record.title}</h2>
              <p>
                {record.provider} · {date(record.date)}
              </p>
            </div>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              {clinician && (
                <button
                  className="button secondary"
                  type="button"
                  onClick={() => setCorrecting((v) => !v)}
                >
                  {tr(correcting ? "Cancel correction" : "Correct metadata")}
                </button>
              )}
              <button
                className="button secondary"
                type="button"
                style={{ color: "var(--red, #dc2626)" }}
                onClick={async () => {
                  if (window.confirm(tr("Withdraw this record? Any visit brief referencing this record will be marked outdated."))) {
                    try {
                      await api(`/records/${id}`, { method: "DELETE" });
                      onDeleted?.();
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }
                }}
              >
                {tr("Withdraw record")}
              </button>
              <a
                className="button secondary"
                href={`/api/records/${id}/file`}
                download
              >
                <ArrowDownToLine size={16} /> {tr("Original file")}
              </a>
            </div>
          </div>
          {record.extraction && (
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", margin: "0.5rem 0" }}>
              <Badge tone="blue">
                {record.extraction.method === "tesseract_ocr"
                  ? "OCR Extraction"
                  : record.extraction.method === "mixed_pdf"
                  ? "Mixed PDF / OCR"
                  : "Direct Text Extraction"}
              </Badge>
              {record.extraction.ocr_lang && (
                <Badge tone="gray">
                  {record.extraction.ocr_lang === "hin"
                    ? "Hindi (hin)"
                    : record.extraction.ocr_lang === "kan"
                    ? "Kannada (kan)"
                    : "English (eng)"}
                </Badge>
              )}
              {record.extraction.pages && record.extraction.pages.length > 0 && (
                <small style={{ color: "var(--text-muted)" }}>
                  {record.extraction.pages.length} {record.extraction.pages.length === 1 ? "page" : "pages"}
                </small>
              )}
            </div>
          )}
          {record.extraction?.warnings && record.extraction.warnings.length > 0 && (
            <div className="error-banner" style={{ margin: "0.5rem 0" }}>
              {record.extraction.warnings.map((w, idx) => (
                <div key={idx}>{w}</div>
              ))}
            </div>
          )}
          {correcting && (
            <form onSubmit={submitCorrection} className="form-body" style={{ margin: "1rem 0", padding: "1rem", border: "1px solid var(--border)", borderRadius: "8px" }}>
              <h3>{tr("Correct metadata")}</h3>
              <div className="form-grid">
                <label>
                  Type
                  <select value={corrKind} onChange={(e) => setCorrKind(e.target.value)}>
                    <option value="Visit note">Visit note</option>
                    <option value="Lab report">Lab report</option>
                    <option value="Referral">Referral</option>
                    <option value="Discharge summary">Discharge summary</option>
                    <option value="Prescription">Prescription</option>
                    <option value="Other">Other</option>
                  </select>
                </label>
                <label>
                  Date
                  <input type="date" value={corrDate} onChange={(e) => setCorrDate(e.target.value)} />
                </label>
              </div>
              <label>
                Provider
                <input value={corrProvider} onChange={(e) => setCorrProvider(e.target.value)} required minLength={2} />
              </label>
              <label>
                {tr("Reason for correction")}
                <input value={corrReason} onChange={(e) => setCorrReason(e.target.value)} required minLength={3} placeholder="e.g. Corrected provider name based on letterhead" />
              </label>
              {corrError && <div className="error-banner">{corrError}</div>}
              <button className="button primary" disabled={corrBusy} type="submit">
                {corrBusy ? <Spinner /> : <Check size={16} />} {tr("Save correction")}
              </button>
            </form>
          )}
          {record.corrections && record.corrections.length > 0 && (
            <div style={{ margin: "0.75rem 0", fontSize: "0.85rem", color: "var(--text-muted)" }}>
              <strong>{tr("Reviewed corrections:")}</strong>
              <ul style={{ margin: "0.25rem 0", paddingLeft: "1.2rem" }}>
                {record.corrections.map((c) => (
                  <li key={c.id}>
                    v{c.version} by {c.reviewer_name}: {c.reason} ({date(c.created_at)})
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="source-label">
            <FileText size={16} /> {tr("Extracted source text")}{" "}
            <Badge tone="amber">{tr("Verify against original")}</Badge>
          </div>
          <pre className="source-text" dir="auto">{record.text}</pre>
          <p className="field-help">
            {tr(
              "Classification uses document keywords. Missing dates and providers remain unknown. OCR may contain errors; the original file is authoritative.",
            )}
          </p>
        </>
      )}
    </div>
  );
}
export function InstructionForm({
  patientId,
  onSaved,
  previousInstruction,
}: {
  patientId: string;
  onSaved: () => Promise<void>;
  previousInstruction?: Instruction;
}) {
  const tr = useText();
  const date = useDate();
  const locale = locales[useLocale()];

  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [language, setLanguage] = useState<string>(previousInstruction?.language || "en");
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setError("");
    try {
      await post(`/patients/${patientId}/instructions`, {
        ...data,
        language,
        confirmed: data.confirmed === "on",
        previous_version_id: previousInstruction?.id || undefined,
        override_reason: (data.override_reason as string)?.trim() || undefined,
      });
      await onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="form-body">
      {previousInstruction && (
        <div style={{ marginBottom: "0.5rem" }}>
          <Badge tone="blue">
            {tr("Updating instruction to version")} v{(previousInstruction.version || 1) + 1}
          </Badge>
        </div>
      )}
      <p className="form-intro">
        {tr(
          "Author and review each version before sharing it. Translations are not generated automatically.",
        )}
      </p>
      <label>
        {tr("Original clinician instructions")}
        <textarea
          name="original"
          defaultValue={previousInstruction?.original || ""}
          minLength={10}
          maxLength={6000}
          required
          rows={3}
        />
      </label>
      <label>
        {tr("Plain-language version")}
        <textarea
          name="plain"
          defaultValue={previousInstruction?.plain || ""}
          minLength={10}
          maxLength={6000}
          required
          rows={3}
        />
      </label>
      <label>
        {tr("Translation language")}
        <LanguageSelect value={language} onChange={setLanguage} />
      </label>
      {language !== "en" && (
        <label>
          {tr("Reviewed translation")}
          <textarea
            name="translated"
            defaultValue={previousInstruction?.translated || ""}
            lang={language}
            dir="auto"
            required
            maxLength={6000}
            rows={3}
          />
        </label>
      )}
      <label>
        {tr("Clinical override reason (optional)")}
        <input
          name="override_reason"
          defaultValue={previousInstruction?.override_reason || ""}
          maxLength={500}
        />
      </label>
      <label className="checkbox-label">
        <input type="checkbox" name="confirmed" required />
        {tr(
          "I have checked every version against the original. No medication, dosage, timing, or clinical meaning has been changed.",
        )}
      </label>
      {error && (
        <div className="error-banner" role="alert">
          {tr(error)}
        </div>
      )}
      <div className="form-footer">
        <Badge tone="green">{tr("Clinician review required")}</Badge>
        <button className="button primary" disabled={busy}>
          {busy ? <Spinner /> : <ShieldCheck size={17} />}{" "}
          {tr("Publish instructions")}
        </button>
      </div>
    </form>
  );
}
