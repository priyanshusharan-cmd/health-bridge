import { useEffect, useState } from "react";
import { api } from "./api";
import { useText } from "./locale";

type Option = { code: string; name: string; region: string; interface: boolean };
let catalog: Promise<Option[]> | null = null;
function loadLanguages() {
  return catalog ??= api<Option[]>("/languages").catch(error => { catalog = null; throw error; });
}
export function LanguageSelect({value, onChange, interfaceOnly = false, name, label}: {
  value: string; onChange: (value: string) => void; interfaceOnly?: boolean; name?: string; label?: string;
}) {
  const tr = useText();
  const [items, setItems] = useState<Option[]>([]);
  const [failed, setFailed] = useState(false);
  const [attempt, retry] = useState(0);
  useEffect(() => {
    let active = true;
    setFailed(false);
    loadLanguages().then(rows => { if(active) setItems(rows); }).catch(() => { if(active) setFailed(true); });
    return () => { active = false; };
  }, [attempt]);
  const options = items.filter(item => !interfaceOnly || item.interface);
  const regions = [...new Set(options.map(item => item.region))];
  return <>
    <select name={name} value={value} aria-label={label || tr("Language")} onChange={e => onChange(e.target.value)} disabled={!items.length}>
      {!items.length && <option value={value}>{value.toUpperCase()}</option>}
      {regions.map(region => <optgroup key={region} label={tr(region)}>
        {options.filter(item => item.region === region).map(item => <option value={item.code} key={item.code}>{item.name}</option>)}
      </optgroup>)}
    </select>
    {failed && <button type="button" className="text-button" onClick={() => retry(n => n + 1)}>{tr("Retry languages")}</button>}
  </>;
}
