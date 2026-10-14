import { useText, useLocale, locales, translate } from "./locale";
import { useEffect, useRef, type ReactNode } from "react";
import {
  Activity,
  ArrowUpRight,
  Check,
  FileText,
  LoaderCircle,
  ShieldCheck,
  X,
} from "lucide-react";
export function Logo() {
  const tr = useText();

  return (
    <div className="brand">
      <span className="brand-mark">
        <Activity size={23} />
      </span>
      <span>
        HealthBridge<span className="brand-dot">.</span>
      </span>
    </div>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  const tr = useText();

  return (
    <span className={`badge ${tone}`}>
      {tone === "green" && <Check size={12} />} {tr(children)}
    </span>
  );
}
export function Spinner() {
  const tr = useText();

  return <LoaderCircle className="spin" size={18} />;
}
export function Empty({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  const tr = useText();

  return (
    <div className="empty">
      <span className="empty-icon">
        <FileText size={28} />
      </span>
      <h3>{tr(title)}</h3>
      <p>{tr(description)}</p>
      {tr(action)}
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const tr = useText();

  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const bodyOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    ref.current?.focus();
    const handle = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const nodes = ref.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled),a[href],input,select,textarea,[tabindex="0"]',
        );
        if (!nodes?.length) return;
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (
          e.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === ref.current)
        ) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handle);
    return () => {
      document.body.style.overflow = bodyOverflow;
      document.removeEventListener("keydown", handle);
      previous?.focus();
    };
  }, [onClose]);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={tr(title)}
        className={`modal ${wide ? "wide" : ""}`}
      >
        <div className="modal-head">
          <div>
            <span className="eyebrow">HEALTHBRIDGE</span>
            <h2>{tr(title)}</h2>
          </div>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label={tr("Close dialog")}
          >
            <X size={20} />
          </button>
        </div>
        {tr(children)}
      </div>
    </div>
  );
}
export function Safety() {
  const tr = useText();

  return (
    <div className="safety-note">
      <ShieldCheck size={17} />
      <span>
        {tr(
          "Information, with a human touch. HealthBridge organizes records; your clinician makes care decisions.",
        )}
      </span>
    </div>
  );
}
export function SectionTitle({
  title,
  subtitle,
  action,
  onAction,
}: {
  title: string;
  subtitle?: string;
  action?: string;
  onAction?: () => void;
}) {
  const tr = useText();

  return (
    <div className="section-title">
      <div>
        <h2>{tr(title)}</h2>
        {subtitle && <p>{tr(subtitle)}</p>}
      </div>
      {action && (
        <button className="text-button" onClick={onAction}>
          {tr(action)}
          <ArrowUpRight size={16} />
        </button>
      )}
    </div>
  );
}
export function date(
  value: string | null,
  options?: Intl.DateTimeFormatOptions,
  language: import("./types").Language = "en",
) {
  if (!value) return translate("Date not provided", language);
  // A document date is a calendar day, not midnight UTC.
  const d = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00` : value);
  return Number.isNaN(d.getTime())
    ? translate("Date not provided", language)
    : d.toLocaleDateString(
        locales[language],
        options || { day: "numeric", month: "short", year: "numeric" },
      );
}

export function useDate() {
  const language = useLocale();
  return (value: string | null, options?: Intl.DateTimeFormatOptions) =>
    date(value, options, language);
}
