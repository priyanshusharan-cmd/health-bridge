import { LanguageSelect } from "./LanguageSelect";
import { useText } from "./locale";
import { useState, type FormEvent } from "react";
import { ArrowDownToLine } from "lucide-react";
import { api } from "./api";
import type { User } from "./types";
import { Spinner } from "./ui";
export function Account({
  user,
  onSaved,
}: {
  user: User;
  onSaved: (user: User) => Promise<void>;
}) {
  const tr = useText();

  const [language, setLanguage] = useState<string>(user.language);
  const [busy, setBusy] = useState(false),
    [exporting, setExporting] = useState(false),
    [error, setError] = useState("");
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      await onSaved(
        await api<User>("/me", {
          method: "PATCH",
          body: JSON.stringify({
            name: form.get("name"),
            specialty: user.role === "clinician" ? form.get("specialty") : undefined,
            age: form.get("age") ? Number(form.get("age")) : null,
            language,
          }),
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="form-body" onSubmit={save}>
      <p className="form-intro">
        {tr(
          "Your initials are generated from your saved name. Changes are stored in your account.",
        )}
      </p>
      <label>
        {tr("Name")}
        <input
          name="name"
          defaultValue={user.name}
          required
          minLength={2}
          maxLength={100}
        />
      </label>
      {user.role === "clinician" && <label>{tr("Medical specialty")}<input name="specialty" defaultValue={user.specialty || ""} placeholder={tr("e.g. Neurologist, Endocrinologist")} maxLength={120} /></label>}
      <label>
        {tr("Age")}
        <input
          name="age"
          type="number"
          min={0}
          max={130}
          step={1}
          defaultValue={user.age ?? ""}
        />
      </label>
      <label>
        {tr("Preferred language")}
        <LanguageSelect interfaceOnly value={language} onChange={setLanguage} />
      </label>
      <p>
        {tr("Account:")}{" "}
        {user.email}
        <br />
        {tr("Role:")}{" "}
        {tr(user.role)}
        {tr(". Account email and role cannot be changed here.")}
      </p>
      {error && (
        <p role="alert" className="field-error">
          {tr(error)}
        </p>
      )}
      <div className="form-footer">
        <button className="button primary" disabled={busy}>
          {busy && <Spinner />}
          {tr("Save profile")}
        </button>
      </div>
      <div className="export-section" style={{ marginTop: "1.5rem", paddingTop: "1rem", borderTop: "1px solid var(--border)" }}>
        <h3>{tr("Export your data")}</h3>
        <p>{tr("Download an authentic structured copy of your care history, intake, and instructions for your records.")}</p>
        <button
          type="button"
          className="button secondary"
          disabled={exporting}
          onClick={async () => {
            setExporting(true);
            try {
              const data = await api<any>(`/patients/${user.id}/export`);
              const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `healthbridge-summary-${user.id}.json`;
              a.click();
              URL.revokeObjectURL(url);
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setExporting(false);
            }
          }}
        >
          {exporting ? <Spinner /> : <ArrowDownToLine size={16} />} {tr("Export my health summary (JSON)")}
        </button>
      </div>
    </form>
  );
}
export function Privacy() {
  const tr = useText();

  return (
    <article className="about-content">
      <h3>{tr("Privacy notice")}</h3>
      <p>
        {tr(
          "Keep your account credentials private. Anyone with access to your account can view and change its information.",
        )}
      </p>
      <h3>{tr("What is stored")}</h3>
      <p>
        {tr(
          "Account details, records, uploaded files and care history are stored in the configured database: MongoDB for hosted deployments or SQLite for local use. Older local uploads may remain on disk. Data stays until the operator removes it; self-service deletion is not available yet.",
        )}
      </p>
      <h3>{tr("Model processing")}</h3>
      <p>
        {tr(
          "Source-only mode processes excerpts on the application server without a model request. When a model endpoint is configured, bounded record excerpts are sent to that endpoint. Its operator and hosting location determine where processing occurs.",
        )}
      </p>
      <h3>{tr("Cookies and appearance")}</h3>
      <p>
        {tr(
          "An HttpOnly session cookie keeps you signed in for up to eight hours. Signing out revokes that session. Browser storage holds your theme preference. Fonts are bundled locally; this app does not include analytics or advertising trackers.",
        )}
      </p>
      <h3>{tr("Access and limitations")}</h3>
      <p>
        {tr(
          "Patients access their own workspace; clinicians access assigned patients. These controls do not constitute HIPAA/GDPR certification. Contact the deployment operator before using any real data.",
        )}
      </p>
    </article>
  );
}
