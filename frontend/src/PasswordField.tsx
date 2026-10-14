import {useId,useState} from 'react';
import {Eye,EyeOff} from 'lucide-react';
import {useText} from './locale';
export function PasswordField({name,label,minLength=1,autoComplete='current-password',autoFocus=false}:{name:string;label:string;minLength?:number;autoComplete?:string;autoFocus?:boolean}) {
 const tr=useText(),id=useId();const [visible,setVisible]=useState(false);
 return <div className="password-field"><label htmlFor={id}>{label}</label><div className="password-control"><input id={id} name={name} type={visible?'text':'password'} required minLength={minLength} maxLength={200} autoComplete={autoComplete} autoFocus={autoFocus}/><button type="button" aria-label={tr(visible?'Hide password':'Show password')} aria-pressed={visible} onClick={()=>setVisible(value=>!value)}>{visible?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></div>;
}
