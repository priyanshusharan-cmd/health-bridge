import { createContext, useContext } from "react";
import type { Language } from "./types";
import catalog from "./locales/ui.json";
export const LocaleContext = createContext<Language>("en");
export const locales = { en: "en-IN", hi: "hi-IN", kn: "kn-IN" };
export function translate<T>(value: T, language: Language): T {
  if (typeof value !== "string" || language === "en") return value;
  const key = value.trim();
  const entry = (catalog as Record<string, { hi: string; kn: string }>)[key];
  if (entry)
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
