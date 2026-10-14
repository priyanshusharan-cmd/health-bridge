import {PasswordField} from "./PasswordField";
import { useState, type FormEvent } from "react";
import { post } from "./api";
import { useText } from "./locale";
import { LanguageSelect } from "./LanguageSelect";
import { Spinner } from "./ui";
import type { User } from "./types";
export function RegistrationForm({
  onCreated,
  connected = true,
  initialEmail = "",
  onBack,
}: {
  onCreated: (user: User) => void;
  connected?: boolean;
  initialEmail?: string;
  onBack?: () => void;
}) {
  const tr = useText();
  const [type, setType] = useState("patient"),
    [language, setLanguage] = useState("en"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const invitation =
    new URLSearchParams(window.location.search).get("invite") || "";
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !connected) return;
    setError("");
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    const emailStr = String(fields.email || "").trim().toLowerCase();
    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    if (!emailStr || !emailRegex.test(emailStr)) {
      setError("Please enter a valid email address.");
      return;
    }
    if (fields.password !== fields.confirm_password) {
      setError("The new passwords do not match.");
      return;
    }
    delete fields.confirm_password;
    setBusy(true);
    try {
      const user = await post<User>("/auth/register", {
        ...fields,
        account_type: type,
        language,
        invitation: type === "patient" ? String(fields.invitation || "") : "",
      });
      // Remove the invitation secret from the visible URL once consumed.
      const hash = user.role === "clinician" ? "#patients" : "#overview";
      window.history.replaceState(
        { ...window.history.state, healthbridgePath: hash },
        "",
        window.location.pathname + hash,
      );
      onCreated(user);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="form-body" onSubmit={submit} noValidate>
      <div className="progressive-auth-header">
        <p className="form-intro">
          {tr("Looks like you’re new to HealthBridge. Let’s create your account.")}
        </p>
        {onBack && (
          <button type="button" className="text-button change-email-btn" onClick={onBack}>
            ← {tr("Change email")}
          </button>
        )}
      </div>
      <label>
        {tr("Account type")}
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          disabled={!!invitation}
        >
          <option value="patient">{tr("Patient")}</option>
          <option value="hospital">{tr("Hospital or clinic")}</option>
        </select>
      </label>
      <label>
        {tr("Name")}
        <input name="name" required minLength={2} maxLength={100} autoComplete="name" />
      </label>
      {type === "hospital" && (
        <label>
          {tr("Hospital or clinic name")}
          <input
            name="hospital_name"
            required
            minLength={2}
            maxLength={160}
          />
        </label>
      )}
      <label>
        {tr("Email ID")}
        <input
          type="email"
          name="email"
          defaultValue={initialEmail}
          placeholder={tr("Enter your Email ID")}
          required
          maxLength={200}
          autoComplete="email"
        />
      </label>
      <PasswordField
        name="password"
        label={tr("Password")}
        minLength={8}
        autoComplete="new-password"
      />
      <small>{tr("Use at least 8 characters.")}</small>
      <PasswordField
        name="confirm_password"
        label={tr("Confirm new password")}
        minLength={8}
        autoComplete="new-password"
      />
      <label>
        {tr("Preferred language")}
        <LanguageSelect interfaceOnly value={language} onChange={setLanguage} />
      </label>
      {type === "patient" && (
        <label>
          {tr("Hospital invitation code (optional)")}
          <input
            name="invitation"
            defaultValue={invitation}
            maxLength={200}
            autoComplete="off"
          />
        </label>
      )}
      {error && (
        <p className="field-error" role="alert">
          {tr(error)}
        </p>
      )}
      <div className="form-footer">
        <button className="button primary full" disabled={busy || !connected}>
          {busy && <Spinner />}
          {tr("Create account & sign in")}
        </button>
      </div>
    </form>
  );
}
export function InvitePatient() {
  const tr=useText();
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[link,setLink]=useState(''),[copied,setCopied]=useState(false);
  async function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();setBusy(true);setError('');setLink('');setCopied(false);
    try {
      const email=new FormData(event.currentTarget).get('email');
      const result=await post<{invitation:string}>('/hospital/invitations',{email});
      setLink(`${window.location.origin}/?invite=${encodeURIComponent(result.invitation)}#register`);
    }catch(error){setError((error as Error).message);}finally{setBusy(false);}
  }
  return <form className="form-body" onSubmit={submit}>
    <p>{tr("Create an invitation for a patient email. The patient must accept it before their workspace appears here. Invitations expire after 24 hours.")}</p>
    <label>{tr("Patient email")}<input type="email" name="email" required maxLength={200} /></label>
    {error&&<p className="field-error" role="alert">{tr(error)}</p>}
    <button className="button primary" disabled={busy}>{busy&&<Spinner />}{tr("Create invitation")}</button>
    {link&&<div className="invitation-result"><label>{tr("Share this link privately with the patient")}<input readOnly value={link} onFocus={e=>e.currentTarget.select()} /></label><button type="button" className="button secondary" onClick={async()=>{try{await navigator.clipboard.writeText(link);setCopied(true);}catch{setError(tr("Select and copy the link manually."));}}}>{tr(copied?'Copied':'Copy link')}</button></div>}
  </form>;
}
export function JoinHospital({onJoined}: {onJoined:(user:User)=>void}) {
  const tr=useText();const [busy,setBusy]=useState(false),[error,setError]=useState('');
  return <form className="form-body join-hospital" onSubmit={async event=>{
    event.preventDefault();const invitation=new FormData(event.currentTarget).get('invitation');setBusy(true);setError('');
    try{const user=await post<User>('/hospital/join',{invitation});window.history.replaceState(window.history.state,'',window.location.pathname+window.location.hash);onJoined(user);}catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }}><h3>{tr("Join your hospital workspace")}</h3><p>{tr("Use the invitation code from your care team. It must match your account email.")}</p><label>{tr("Invitation code")}<input name="invitation" defaultValue={new URLSearchParams(window.location.search).get("invite") || ""} required minLength={20} maxLength={200} /></label>{error&&<p role="alert" className="field-error">{tr(error)}</p>}<button className="button secondary" disabled={busy}>{busy&&<Spinner />}{tr("Accept invitation")}</button></form>;
}
