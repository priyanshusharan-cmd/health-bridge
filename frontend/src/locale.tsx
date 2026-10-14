import { createContext, useContext } from "react";
import type { Language } from "./types";
import catalog from "./locales/ui.json";
export const LocaleContext = createContext<Language>("en");
const baseLocales: Record<string, string> = {
  en: "en-IN",
  hi: "hi-IN",
  kn: "kn-IN",
  as: "as-IN",
  bn: "bn-IN",
  brx: "brx-IN",
  doi: "doi-IN",
  gu: "gu-IN",
  ks: "ks-IN",
  kok: "kok-IN",
  mai: "mai-IN",
  ml: "ml-IN",
  mni: "mni-IN",
  mr: "mr-IN",
  ne: "ne-IN",
  or: "or-IN",
  pa: "pa-IN",
  sa: "sa-IN",
  sat: "sat-IN",
  sd: "sd-IN",
  ta: "ta-IN",
  te: "te-IN",
  ur: "ur-IN",
};
export const locales: Record<string, string> = new Proxy(baseLocales, {
  get(target, prop: string) {
    return target[prop] || `${prop}-IN`;
  },
});
export function translate<T>(value: T, language: Language): T {
  if (typeof value !== "string" || language === "en") return value;
  const key = value.trim();
  const entry = (catalog as Record<string, Record<string, string>>)[key];
  if (entry && entry[language])
    return (value.slice(0, value.indexOf(key)) +
      entry[language] +
      value.slice(value.indexOf(key) + key.length)) as T;
  const match = key.match(/^(\d+) (records in one place|awaiting review)$/);
  if (match)
    return `${match[1]} ${language === "hi" ? (match[2] === "awaiting review" ? "समीक्षा की प्रतीक्षा में" : "रिकॉर्ड एक जगह") : match[2] === "awaiting review" ? "ಪರಿಶೀಲನೆಗಾಗಿ ಕಾಯುತ್ತಿದೆ" : "ದಾಖಲೆಗಳು ಒಂದೇ ಕಡೆ"}` as T;
  return value;
}
export function useText(explicit?: Language) {
  const context = useContext(LocaleContext);
  return <T,>(value: T) => translate(value, explicit ?? context);
}
export function useLocale() {
  return useContext(LocaleContext);
}
