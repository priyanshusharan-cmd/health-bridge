import {PasswordField} from "./PasswordField";
import { useState, type FormEvent } from "react";
import { post } from "./api";
import { useText } from "./locale";
import { LanguageSelect } from "./LanguageSelect";
import { Spinner } from "./ui";
import type { User } from "./types";
export function RegistrationForm({
  onCreated,
  onExisting,
  connected = true,
  initialEmail = "",
  onBack,
}: {
  onCreated: (user: User) => void;
  onExisting?: (email: string) => void;
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
      if (onExisting) {
        const result = await post<{ registered: boolean }>("/auth/check-email", { email: emailStr });
        if (result.registered) {
          onExisting(emailStr);
          return;
        }
      }
      const user = await post<User>("/auth/register", {
        ...fields,
        account_type: type,
        language,
        invitation: "",
      });
      // Keep the invitation until the patient explicitly accepts after signup.
      const hash = user.role === "clinician" ? "#patients" : "#overview";
      window.history.replaceState(
        { ...window.history.state, healthbridgePath: hash },
        "",
        window.location.pathname + (type === "patient" && invitation ? window.location.search : "") + hash,
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
      {type === "hospital" && <label>{tr("Medical specialty")}<input name="specialty" placeholder={tr("e.g. Neurologist, Endocrinologist")} maxLength={120} /></label>}
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
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[link,setLink]=useState(''),[copied,setCopied]=useState(false),[sent,setSent]=useState(false);
  async function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();setBusy(true);setError('');setLink('');setCopied(false);setSent(false);
    try {
      const email=new FormData(event.currentTarget).get('email');
      const result=await post<{invitation:string | null; registered:boolean}>('/hospital/invitations',{email});
      if (result.registered) setSent(true);
      else if (result.invitation) setLink(`${window.location.origin}/?invite=${encodeURIComponent(result.invitation)}#overview`);
    }catch(error){setError((error as Error).message);}finally{setBusy(false);}
  }
  return <form className="form-body" onSubmit={submit}>
    <p>{tr("Enter the patient’s email. Existing patients receive a request in their account. For new patients, share the signup link. Requests expire in 24 hours.")}</p>
    <label>{tr("Patient email")}<input type="email" name="email" required maxLength={200} /></label>
    {error&&<p className="field-error" role="alert">{tr(error)}</p>}
    <button className="button primary" disabled={busy}>{busy&&<Spinner />}{tr("Invite patient")}</button>
    {sent && <p role="status">{tr("Invitation ready. The patient will see it when they sign in or while their account is open.")}</p>}
    {link&&<div className="invitation-result"><label>{tr("Share this link privately with the patient")}<input readOnly value={link} onFocus={e=>e.currentTarget.select()} /></label><button type="button" className="button secondary" onClick={async()=>{try{await navigator.clipboard.writeText(link);setCopied(true);}catch{setError(tr("Select and copy the link manually."));}}}>{tr(copied?'Copied':'Copy link')}</button></div>}
  </form>;
}
export function JoinHospital({onJoined, invitationId, hospital, doctor, specialty}: {onJoined:(user:User)=>void; invitationId?:string; hospital?:string; doctor?:string; specialty?:string}) {
  const tr=useText();
  const linkCode=new URLSearchParams(window.location.search).get("invite") || "";
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  return <form className="form-body join-hospital" onSubmit={async event=>{
    event.preventDefault();
    let invitation=String(new FormData(event.currentTarget).get('invitation') || '').trim();
    if (invitation.includes('://')) {
      try { invitation=new URL(invitation).searchParams.get('invite') || ''; }
      catch { setError('Enter a valid invitation link.'); return; }
    }
    if (!invitation && !invitationId) { setError('Enter your invitation link.'); return; }
    setBusy(true);setError('');
    try {
      const user=await post<User>(invitationId ? `/patient/invitations/${encodeURIComponent(invitationId)}/accept` : '/hospital/join',{invitation});
      const url=new URL(window.location.href);url.searchParams.delete('invite');url.hash='overview';
      window.history.replaceState(window.history.state,'',url.pathname+url.search+url.hash);
      onJoined(user);
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }}>
    {hospital && <h3>{hospital}</h3>}
    {doctor && <p><strong>{doctor}</strong><br />{specialty || tr("Specialty not provided")}</p>}
    <p>{tr("This doctor is requesting access to your care workspace. Accepting lets them view your shared records and help manage your care.")}</p>
    {!linkCode && !invitationId && <h3>{tr("Connect to your care team")}</h3>}
    <p>{tr("Accept to connect your account with the care team that invited you. Sign in with the email they invited.")}</p>
    {invitationId ? null : linkCode ? <input type="hidden" name="invitation" value={linkCode} /> :
      <label>{tr("Invitation link")}<input name="invitation" placeholder={tr("Paste the link from your care team")} required maxLength={2000} /></label>}
    {error&&<p role="alert" className="field-error">{tr(error)}</p>}
    <button className="button primary" disabled={busy}>{busy&&<Spinner />}{tr("Accept & connect")}</button>
  </form>;
}
