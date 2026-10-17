import {useState,type FormEvent} from 'react';
import {post} from './api';
import {useText} from './locale';
import {PasswordField} from './PasswordField';
import {Spinner} from './ui';
export function AccountSecurity({demo}:{demo:boolean}) {
 const tr=useText();const [busy,setBusy]=useState(false),[error,setError]=useState(''),[saved,setSaved]=useState(false);
 async function submit(event:FormEvent<HTMLFormElement>) {
  event.preventDefault();const form=event.currentTarget,fields=Object.fromEntries(new FormData(form));setError('');setSaved(false);
  if(fields.new_password!==fields.confirm_password){setError('The new passwords do not match.');return;}
  setBusy(true);
  try {await post('/auth/password',fields);form.reset();setSaved(true);}catch(e){setError((e as Error).message);}finally{setBusy(false);}
 }
 return <section className="account-security form-body"><h3>{tr('Password & Security')}</h3>{demo?<p>{tr('This shared account’s password cannot be changed. Create your own account.')}</p>:<form className="form-body" onSubmit={submit}><PasswordField name="current_password" label={tr('Current password')}/><PasswordField name="new_password" label={tr('New password')} minLength={8} autoComplete="new-password"/><PasswordField name="confirm_password" label={tr('Confirm new password')} minLength={8} autoComplete="new-password"/><small>{tr('Use at least 8 characters. Other sessions will be signed out.')}</small>{error&&<p role="alert" className="field-error">{tr(error)}</p>}{saved&&<p role="status">{tr('Password updated. Other sessions were signed out.')}</p>}<button className="button secondary" disabled={busy}>{busy&&<Spinner/>}{tr('Change password')}</button></form>}</section>;
}
