import { useText, useLocale, locales } from "./locale";
import { useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Clock3,
  FileText,
  Files,
  Flag,
  Heart,
  MapPin,
  MessageSquare,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
  UserRound,
} from "lucide-react";
import type { User, Workspace, RecordItem, Instruction } from "./types";
import { translations } from "./i18n";
import { Badge, useDate, Empty, SectionTitle, Spinner } from "./ui";
import { post } from "./api";
type T = typeof translations.en;
type Base = { w: Workspace; t: T };
const kindClass = (kind: string) =>
  kind === "Lab report" ? "lavender" : kind === "Referral" ? "peach" : "sage";
function RecordIcon({ kind }: { kind: string }) {
  const tr = useText();
  const date = useDate();
  const locale = locales[useLocale()];

  return (
    <span className={`record-icon ${kindClass(kind)}`}>
      {kind === "Lab report" ? (
        <Files size={21} />
      ) : kind === "Referral" ? (
        <ArrowUpRight size={21} />
      ) : (
        <FileText size={21} />
      )}
    </span>
  );
}
function RecordRow({ r, open }: { r: RecordItem; open: (id: string) => void }) {
  const tr = useText();
  const date = useDate();
  const locale = locales[useLocale()];

  return (
    <button className="record-row" onClick={() => open(r.id)}>
      <RecordIcon kind={r.kind} />
      <div className="record-row-title">
        <strong>{r.title}</strong>
        <small>
          {r.provider} <span>·</span> {date(r.date)}
        </small>
      </div>
      <Badge>{tr(r.kind)}</Badge>
      <ChevronRight size={17} />
    </button>
  );
}
export function Overview({
  w,
  t,
  clinician,
  navigate,
  onIntake,
  onUpload,
  onAppointment,
  openRecord,
}: Base & {
  clinician: boolean;
  navigate: (p: "records" | "prep" | "timeline" | "instructions") => void;
  onIntake: () => void;
  onUpload: () => void;
  onAppointment: () => void;
  openRecord: (id: string) => void;
}) {
  const tr = useText();
  const date = useDate();
  const locale = locales[useLocale()];

  const next = w.appointments.find((a) => new Date(a.starts_at) > new Date()),
    approved = w.brief?.status === "approved";
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{tr(clinician ? w.patient.name : t.welcome)}</h1>
          <p>
            {tr(
              clinician
                ? "The details that matter, with the sources behind them."
                : t.subtitle,
            )}
          </p>
        </div>
        <button className="button secondary" onClick={onUpload}>
          <Plus size={17} />
          {tr(t.upload)}
        </button>
      </div>
      <div className="overview-grid">
        <div className="overview-main">
          <section className="welcome-card">
            <div className="welcome-copy">
              <span className="welcome-kicker">
                <span /> {tr("LET’S TAKE THE NEXT STEP")}
              </span>
              <h2>
                {tr(clinician ? "A clearer handoff starts here." : t.ready)}
              </h2>
              <p>{tr(t.readySub)}</p>
              <button
                className="button primary"
                onClick={() => navigate("prep")}
              >
                {tr(clinician ? "Open visit brief" : t.prepare)}
                <ArrowRight size={17} />
              </button>
              <div className="welcome-foot">
                <ShieldCheck size={14} />{" "}
                {tr("Prepared with sources. Reviewed with care.")}
              </div>
            </div>
            <div className="care-illustration" aria-hidden="true">
              <div className="orbit" />
              <div className="orbit orbit-inner" />
              <div className="illustration-sheet">
                <div className="sheet-cross">
                  <Plus />
                </div>
                <div className="sheet-line long" />
                <div className="sheet-line" />
                <div className="sheet-line short" />
                <div className="sheet-rule" />
                <div className="sheet-check">
                  <Check size={14} />
                  <span />
                </div>
                <div className="sheet-check">
                  <Check size={14} />
                  <span />
                </div>
              </div>
              <div className="floating-heart">
                <Heart size={23} />
              </div>
              <div className="floating-check">
                <ShieldCheck size={21} />
              </div>
              <span className="illustration-dot one" />
              <span className="illustration-dot two" />
            </div>
          </section>
          <div className="stats-grid">
            <button className="stat-card" onClick={() => navigate("records")}>
              <span className="stat-icon sage">
                <Files size={19} />
              </span>
              <div>
                <strong>{w.records.length.toString().padStart(2, "0")}</strong>
                <span>{tr("Health records")}</span>
              </div>
              <ArrowUpRight size={15} />
            </button>
            <button className="stat-card" onClick={() => navigate("prep")}>
              <span className="stat-icon peach">
                <ClipboardCheck size={19} />
              </span>
              <div>
                <strong>
                  {tr(
                    w.brief &&
                      ["pending", "flagged", "outdated"].includes(
                        w.brief.status,
                      )
                      ? "01"
                      : "00",
                  )}
                </strong>
                <span>{tr("Briefs to review")}</span>
              </div>
              <ArrowUpRight size={15} />
            </button>
            <button
              className="stat-card"
              onClick={() => navigate("instructions")}
            >
              <span className="stat-icon lavender">
                <Heart size={19} />
              </span>
              <div>
                <strong>
                  {w.instructions.length.toString().padStart(2, "0")}
                </strong>
                <span>{tr("Care updates")}</span>
              </div>
              <ArrowUpRight size={15} />
            </button>
          </div>
          <section className="panel journey-panel">
            <SectionTitle title={tr(t.journey)} subtitle={t.journeySub} />
            <div className="journey-steps">
              {[
                {
                  label: "Share your story",
                  detail: w.intake
                    ? "Your intake is saved"
                    : "Tell us what’s on your mind",
                  done: !!w.intake,
                  action: onIntake,
                },
                {
                  label: "Bring it together",
                  detail: `${w.records.length} records in one place`,
                  done: w.records.length > 0,
                  action: () => navigate("records"),
                },
                {
                  label: "Prepare & review",
                  detail: approved
                    ? "Reviewed by your clinician"
                    : w.brief
                      ? "Brief ready for review"
                      : "Your next step",
                  done: approved,
                  action: () => navigate("prep"),
                },
                {
                  label: "Know what’s next",
                  detail: w.instructions.length
                    ? "Your care team has shared updates"
                    : "Clear, reviewed instructions",
                  done: w.instructions.length > 0,
                  action: () => navigate("instructions"),
                },
              ].map((s, i) => (
                <button
                  className={`journey-step ${s.done ? "done" : ""}`}
                  key={s.label}
                  onClick={s.action}
                >
                  <span className="step-circle">
                    {s.done ? <Check size={15} /> : i + 1}
                  </span>
                  <strong>{tr(s.label)}</strong>
                  <small>{tr(s.detail)}</small>
                </button>
              ))}
            </div>
          </section>
          <section className="panel records-panel">
            <SectionTitle
              title={tr(t.recent)}
              action={tr(t.view)}
              onAction={() => navigate("records")}
            />
            {w.records.length ? (
              w.records
                .slice(0, 3)
                .map((r) => <RecordRow r={r} key={r.id} open={openRecord} />)
            ) : (
              <Empty
                title={tr(t.noRecords)}
                description={tr(t.noRecordsSub)}
                action={
                  <button className="button secondary" onClick={onUpload}>
                    {tr(t.upload)}
                  </button>
                }
              />
            )}
          </section>
        </div>
        <aside className="overview-aside">
          <section className="panel appointment-card">
            <span className="eyebrow">
              <CalendarDays size={15} /> {tr(t.next)}
            </span>
            {next ? (
              <>
                <div className="appointment-date">
                  <span>
                    {date(next.starts_at, { month: "short" }).toUpperCase()}
                  </span>
                  <strong>{date(next.starts_at, { day: "2-digit" })}</strong>
                  <small>{date(next.starts_at, { weekday: "long" })}</small>
                </div>
                <h3>{next.clinician}</h3>
                <p>{next.specialty}</p>
                <div className="appointment-details">
                  <span>
                    <Clock3 size={15} />
                    {new Date(next.starts_at).toLocaleTimeString(locale, {
                      hour: "numeric",
                      minute: "2-digit",
                      timeZoneName: "short",
                    })}{" "}
                  </span>
                  <span>
                    <MapPin size={15} />
                    {next.location}
                  </span>
                </div>
                <button
                  className="button secondary full"
                  onClick={() => navigate("prep")}
                >
                  {tr("Let’s get you ready")}
                  <ArrowRight size={15} />
                </button>
              </>
            ) : (
              <Empty
                title={tr("No upcoming visit")}
                description={tr(
                  "Your next scheduled appointment will appear here.",
                )}
              />
            )}
            <button className="text-button appointment-edit" onClick={onAppointment}>{tr(next ? "Edit appointment" : "Add appointment")}</button>
          </section>
          <section className="questions-card">
            <span className="question-icon">
              <MessageSquare size={21} />
            </span>
            <h3>{tr("Your questions matter.")}</h3>
            <p>
              {tr("A small note now can make a big difference in the room.")}
            </p>
            <button className="text-button" onClick={onIntake}>
              {tr(w.intake ? "Review my questions" : "Add my questions")}
              <ArrowRight size={15} />
            </button>
          </section>
          <section className="trust-card">
            <span className="trust-icon">
              <ShieldCheck size={20} />
            </span>
            <div>
              <h4>{tr("You’re in the loop.")}</h4>
              <p>
                {tr(
                  "Every brief keeps its sources. Every care decision stays with your clinician.",
                )}
              </p>
            </div>
          </section>
        </aside>
      </div>
    </>
  );
}
export function Records({
  w,
  t,
  onUpload,
  openRecord,
}: Base & { onUpload: () => void; openRecord: (id: string) => void }) {
  const tr = useText();
  const date = useDate();
  const locale = locales[useLocale()];

  const [query, setQuery] = useState(""),
    [kind, setKind] = useState("All records");
  const kinds = ["All records", ...new Set(w.records.map((r) => r.kind))];
  const rows = w.records.filter(
    (r) =>
      (kind === "All records" || r.kind === kind) &&
      `${r.title} ${r.provider} ${r.kind}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{tr(t.recordsTitle)}</h1>
          <p>{tr(t.recordsSub)}</p>
        </div>
        <button className="button primary" onClick={onUpload}>
          <Plus size={17} />
          {tr(t.upload)}
        </button>
      </div>
      <div className="library-toolbar">
        <div className="tabs" aria-label={tr("Record categories")}>
          {kinds.map((k) => (
            <button
              className={kind === k ? "selected" : ""}
              key={k}
              onClick={() => setKind(k)}
            >
              {tr(k)}
              {k === "All records" && <span>{tr(w.records.length)}</span>}
            </button>
          ))}
        </div>
        <label className="search-input">
          <Search size={17} />
          <input
            aria-label={tr("Search records")}
            placeholder={tr(t.search)}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </div>
      <div className="record-grid">
        {rows.map((r) => (
          <button
            className="record-card"
            onClick={() => openRecord(r.id)}
            key={r.id}
          >
            <div className="record-card-top">
              <RecordIcon kind={r.kind} />
              <ArrowUpRight size={18} />
            </div>
            <Badge>{tr(r.kind)}</Badge>
            <h3>{r.title}</h3>
            <p>{r.provider}</p>
            <div className="record-card-bottom">
              <span>{date(r.date)}</span>
              <span>
                {tr("View record")}
                <ChevronRight size={14} />
              </span>
            </div>
          </button>
        ))}
      </div>
      {!rows.length && (
        <Empty
          title={tr(query ? "No matching records" : t.noRecords)}
          description={tr(
            query ? "Try another search or category." : t.noRecordsSub,
          )}
        />
      )}
      <div className="info-strip">
        <ShieldCheck size={17} />{" "}
        {tr(
          "Records are source information, not AI medical advice. Open any record to see its original text.",
        )}
      </div>
    </>
  );
}
export function Timeline({
  w,
  t,
  openRecord,
}: Base & { openRecord: (id: string) => void }) {
  const tr = useText();
  const date = useDate();
  const locale = locales[useLocale()];

  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{tr(t.timeline)}</h1>
          <p>
            {tr("Every record is part of your story. Keep the original close.")}
          </p>
        </div>
        <Badge>
          {tr(w.records.length)} {tr("records")}
        </Badge>
      </div>
      <section className="panel timeline-panel">
        {w.records.length ? (
          w.records.map((r, i) => (
            <div className="timeline-event" key={r.id}>
              <div className="timeline-date">
                <strong>
                  {date(r.date, { day: "2-digit", month: "short" })}
                </strong>
                <span>{r.date?.slice(0, 4) || "Undated"}</span>
              </div>
              <div className="timeline-track">
                <span className={i === 0 ? "latest" : ""} />
              </div>
              <button
                className="timeline-content"
                onClick={() => openRecord(r.id)}
              >
                <RecordIcon kind={r.kind} />
                <div>
                  <Badge>{tr(r.kind)}</Badge>
                  <h3>{r.title}</h3>
                  <p>
                    {r.provider} {tr("· Source document")}
                  </p>
                </div>
                <ArrowUpRight size={19} />
              </button>
            </div>
          ))
        ) : (
          <Empty title={tr(t.noRecords)} description={tr(t.noRecordsSub)} />
        )}
      </section>
    </>
  );
}
export function VisitPrep({
  w,
  t,
  clinician,
  generate,
  generating,
  onIntake,
  openRecord,
  refresh,
  notify,
}: Base & {
  clinician: boolean;
  generate: () => void;
  generating: boolean;
  onIntake: () => void;
  openRecord: (id: string) => void;
  refresh: () => Promise<void>;
  notify: (s: string) => void;
}) {
  const tr = useText();
  const date = useDate();
  const locale = locales[useLocale()];

  const [note, setNote] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [replyText, setReplyText] = useState<Record<string, string>>({});
  const [showClarModal, setShowClarModal] = useState(false);
  const [clarQuestion, setClarQuestion] = useState("");
  const [clarUncertaintyId, setClarUncertaintyId] = useState<string | null>(null);
  const [clarBusy, setClarBusy] = useState(false);

  const b = w.brief;
  useEffect(() => { setNote(""); setError(""); }, [b?.id]);

  const askClarification = (desc?: string, uncId?: string) => {
    setClarQuestion(desc ? `${tr("Clarification regarding:")} ${desc}` : "");
    setClarUncertaintyId(uncId || null);
    setShowClarModal(true);
  };

  const submitClarification = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clarQuestion.trim()) return;
    setClarBusy(true);
    try {
      await post(`/patients/${w.patient.id}/clarifications`, {
        question: clarQuestion.trim(),
        brief_id: b?.id || null,
        originating_uncertainty_id: clarUncertaintyId,
      });
      await refresh();
      setShowClarModal(false);
      setClarQuestion("");
      setClarUncertaintyId(null);
      notify("Clarification question posted.");
    } catch (err) {
      notify((err as Error).message);
    } finally {
      setClarBusy(false);
    }
  };

  const sendReply = async (clarId: string) => {
    const text = replyText[clarId]?.trim();
    if (!text) return;
    try {
      await post(`/clarifications/${clarId}/messages`, { text });
      setReplyText({ ...replyText, [clarId]: "" });
      await refresh();
    } catch (err) {
      notify((err as Error).message);
    }
  };

  const resolveClar = async (clarId: string) => {
    const reason = window.prompt(tr("Resolution reason"));
    if (!reason || reason.trim().length < 3) return;
    try {
      await post(`/clarifications/${clarId}/resolve`, { reason: reason.trim() });
      await refresh();
      notify("Clarification resolved.");
    } catch (err) {
      notify((err as Error).message);
    }
  };

  const review = async (status: "approved" | "flagged") => {
    if (!note.trim()) {
      setError("Add a review note or correction before continuing.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await post(`/briefs/${b?.id}/review`, {
        status,
        note,
        expected_source_revision: b?.content.source_revision,
      });
      await refresh();
      notify(
        status === "approved"
          ? "Brief approved. Your review is visible to the patient."
          : "Brief flagged for clarification.",
      );
      setNote("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="page-heading no-print">
        <div>
          <h1>
            {tr(
              clinician ? "A complete story. A considered next step." : t.prep,
            )}
          </h1>
          <p>
            {tr(
              "Source-linked information, prepared for a conversation with your clinician.",
            )}
          </p>
        </div>
        <button className="button secondary" onClick={onIntake}>
          <MessageSquare size={17} />
          {tr(w.intake ? "Edit my intake" : "Add my intake")}
        </button>
      </div>
      <div className="prep-layout">
        <div>
          <section className="panel intake-summary no-print">
            <SectionTitle
              title={tr("The conversation starts with you")}
              action={tr("Edit intake")}
              onAction={onIntake}
            />
            {w.intake ? (
              <>
                <Badge tone="blue">{tr("Patient provided")}</Badge>
                <blockquote>{w.intake.reason}</blockquote>
                <div className="intake-details">
                  <div>
                    <span>{tr("Duration")}</span>
                    <strong>{w.intake.duration || t.notProvided}</strong>
                  </div>
                  <div>
                    <span>{tr("Questions to discuss")}</span>
                    <strong>{w.intake.questions || t.notProvided}</strong>
                  </div>
                </div>
              </>
            ) : (
              <Empty
                title={tr("Tell your care team what matters")}
                description={tr(t.intakeHint)}
                action={
                  <button className="button primary" onClick={onIntake}>
                    {tr("Start my intake")}
                    <ArrowRight size={16} />
                  </button>
                }
              />
            )}
          </section>
          <section className="panel brief-panel">
            <div className="section-title">
              <div>
                <span className="eyebrow">
                  {tr("PATIENT HEALTHBRIDGE SUMMARY")}
                </span>
                <h2>{tr("Your visit brief")}</h2>
              </div>
              {b && (
                <Badge
                  tone={
                    b.status === "approved"
                      ? "green"
                      : b.status === "flagged"
                        ? "red"
                        : "amber"
                  }
                >
                  {tr(
                    b.status === "approved"
                      ? "Clinician reviewed"
                      : b.status === "outdated"
                        ? "Outdated · regenerate"
                        : b.status === "flagged"
                          ? "Needs clarification"
                          : "Review required",
                  )}
                </Badge>
              )}
            </div>
            <p className="brief-patient">
              {w.patient.name} · {w.patient.age != null && <>{w.patient.age} {tr("years ·")}</>}{" "}
              {w.patient.language.toUpperCase()}
            </p>
            {b ? (
              <>
                <div className="brief-notice">
                  <ShieldCheck size={17} />
                  {tr(b.content.notice)}
                </div>
                {b.content.coverage && (
                  <div className="coverage-notice" style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "1rem", padding: "0.5rem 0.75rem", background: "var(--ink-f5f5f5)", borderRadius: "6px" }}>
                    <ShieldCheck size={16} />
                    <span>
                      {b.content.coverage.included_records} {tr("records included")}
                      {b.content.coverage.excluded_sources && b.content.coverage.excluded_sources.length > 0 && ` · ${b.content.coverage.excluded_sources.length} ${tr("excluded due to limit")}`}
                    </span>
                  </div>
                )}
                {b.content.uncertainties && b.content.uncertainties.length > 0 && (
                  <div className="uncertainties-panel" style={{ border: "1px solid var(--ink-cccccc)", borderRadius: "8px", padding: "1rem", marginBottom: "1.25rem", background: "var(--background-soft)" }}>
                    <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: 0, fontSize: "1rem", color: "var(--amber)" }}>
                      <AlertCircle size={18} />
                      {tr("Items requiring clinician confirmation")}
                    </h3>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                      {b.content.uncertainties.map((u) => (
                        <div key={u.id} style={{ padding: "0.5rem 0.75rem", background: "var(--panel-bg)", borderRadius: "6px", border: "1px solid var(--border)" }}>
                          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.25rem", justifyContent: "space-between" }}>
                            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                              <Badge tone={u.kind === "conflicting_sources" ? "red" : u.kind === "extraction_warning" ? "amber" : "blue"}>
                                {tr(u.kind === "conflicting_sources" ? "Statements differ" : u.kind === "extraction_warning" ? "Extraction warning" : "Information needed")}
                              </Badge>
                              <strong>{u.description}</strong>
                            </div>
                            <button
                              className="text-button"
                              onClick={() => askClarification(u.description, u.id)}
                            >
                              <MessageSquare size={14} /> {tr("Ask clarification")}
                            </button>
                          </div>
                          {u.citations?.map((c, cIdx) => (
                            <div key={cIdx} style={{ fontSize: "0.85rem", display: "flex", gap: "0.5rem", alignItems: "center" }}>
                              <span>“{c.quote}”</span>
                              {w.records.some(r => r.id === c.source_id) && (
                                <button className="text-button" onClick={() => openRecord(c.source_id)}>
                                  {tr("View source")} <ArrowUpRight size={12} />
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {/* Clarifications Panel */}
                <div className="section-card no-print" style={{ marginBottom: "1.5rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border)", paddingBottom: "0.5rem" }}>
                    <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <MessageSquare size={18} />
                      {tr("Clarifications")}
                    </h3>
                    <button
                      className="button secondary"
                      onClick={() => askClarification()}
                    >
                      <Plus size={14} /> {tr("Ask clarification")}
                    </button>
                  </div>
                  {showClarModal && (
                    <div style={{ margin: "1rem 0", padding: "1rem", borderRadius: "8px", border: "1px solid var(--border)", background: "var(--panel-bg)" }}>
                      <form onSubmit={submitClarification} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                        <textarea
                          value={clarQuestion}
                          onChange={(e) => setClarQuestion(e.target.value)}
                          placeholder={tr("Write a response…")}
                          rows={3}
                          required
                          minLength={3}
                        />
                        <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
                          <button type="button" className="button secondary" onClick={() => setShowClarModal(false)}>
                            {tr("Cancel")}
                          </button>
                          <button type="submit" className="button primary" disabled={clarBusy}>
                            {clarBusy ? <Spinner /> : <Check size={16} />} {tr("Ask clarification")}
                          </button>
                        </div>
                      </form>
                    </div>
                  )}
                  {w.clarifications && w.clarifications.length > 0 ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "1rem" }}>
                      {w.clarifications.map((c) => (
                        <div key={c.id} style={{ padding: "0.75rem", borderRadius: "8px", background: "var(--panel-bg)", border: "1px solid var(--border)" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <strong>{c.question}</strong>
                            <Badge tone={c.status === "resolved" ? "green" : "amber"}>
                              {tr(c.status === "resolved" ? "Resolved" : "Open clarification")}
                            </Badge>
                          </div>
                          <div style={{ fontSize: "0.8rem", color: "var(--muted)", margin: "0.25rem 0" }}>
                            {c.creator_name} · {date(c.created_at)}
                          </div>
                          {c.resolution_reason && (
                            <div style={{ fontSize: "0.85rem", color: "var(--green, #16a34a)", marginTop: "0.25rem" }}>
                              <strong>{tr("Resolved by")} {c.resolved_by}:</strong> {c.resolution_reason}
                            </div>
                          )}
                          {/* Messages thread */}
                          {c.messages && c.messages.length > 1 && (
                            <div style={{ marginTop: "0.5rem", paddingLeft: "0.5rem", borderLeft: "2px solid var(--border)", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                              {c.messages.slice(1).map((m) => (
                                <div key={m.id} style={{ fontSize: "0.85rem" }}>
                                  <span style={{ fontWeight: 600 }}>{m.author_name} ({tr(m.role)}): </span>
                                  <span>{m.text}</span>
                                </div>
                              ))}
                            </div>
                          )}
                          {/* Reply / Resolve controls */}
                          {c.status === "open" && (
                            <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                              <input
                                placeholder={tr("Write a response…")}
                                value={replyText[c.id] || ""}
                                onChange={(e) => setReplyText({ ...replyText, [c.id]: e.target.value })}
                                style={{ flex: 1, minWidth: "150px" }}
                              />
                              <button
                                className="button secondary"
                                onClick={() => sendReply(c.id)}
                              >
                                {tr("Reply")}
                              </button>
                              {clinician && (
                                <button
                                  className="button secondary"
                                  onClick={() => resolveClar(c.id)}
                                >
                                  {tr("Resolve")}
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p style={{ color: "var(--muted)", fontSize: "0.9rem", marginTop: "0.75rem" }}>
                      {tr("No clarification questions requested yet.")}
                    </p>
                  )}
                </div>
                {b.content.sections && b.content.sections.length > 0 ? (
                  b.content.sections.map((sec) => (
                    <div className="section-card" key={sec.key} style={{ marginBottom: "1.5rem" }}>
                      <h3 style={{ borderBottom: "1px solid var(--border)", paddingBottom: "0.5rem" }}>{tr(sec.label)}</h3>
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.5rem" }}>
                        {sec.items.map((it, idx) => (
                          <div key={idx} style={{ padding: "0.75rem", borderRadius: "6px", background: "var(--panel-bg)", border: "1px solid var(--border)" }}>
                            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.25rem" }}>
                              <Badge tone={it.attribution === "patient_reported" ? "blue" : it.attribution === "clinician_reviewed" ? "amber" : "neutral"}>
                                {tr(it.attribution === "patient_reported" ? "Patient provided" : it.attribution === "clinician_reviewed" ? "Clinician confirmed" : "Document recorded")}
                              </Badge>
                              <strong>{it.text}</strong>
                            </div>
                            {it.citations?.map((c, cIdx) => (
                              <div key={cIdx} style={{ fontSize: "0.85rem", color: "var(--muted)", display: "flex", gap: "0.5rem", alignItems: "center", marginTop: "0.25rem" }}>
                                <span>“{c.quote.length > 120 ? c.quote.slice(0, 120) + '…' : c.quote}”</span>
                                {c.page != null && <span>({tr("Page")} {c.page})</span>}
                                {w.records.some(r => r.id === c.source_id) && (
                                  <button className="text-button" onClick={() => openRecord(c.source_id)}>
                                    {tr("View source")} <ArrowUpRight size={12} />
                                  </button>
                                )}
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))
                ) : (
                  b.content.evidence.map((e, i) => {
                    const source = b.content.sources.find(
                      (s) => s.id === e.source_id,
                    );
                    return (
                      <div className="evidence-block" key={`${e.source_id}-${i}`}>
                        <div className="evidence-heading">
                          <span className="source-number">
                            {String(i + 1).padStart(2, "0")}
                          </span>
                          <h3>{source?.title || "Source"}</h3>
                          <Badge
                            tone={
                              e.source_id === b.content.intake?.id
                                ? "blue"
                                : "neutral"
                            }
                          >
                            {tr(
                              e.source_id === b.content.intake?.id
                                ? "Patient provided"
                                : "Source excerpt",
                            )}
                          </Badge>
                        </div>
                        <p>{e.quote}</p>
                        {w.records.some((r) => r.id === e.source_id) && (
                          <button
                            className="text-button no-print"
                            onClick={() => openRecord(e.source_id)}
                          >
                            {tr(t.source)}
                            <ArrowUpRight size={14} />
                          </button>
                        )}
                      </div>
                    );
                  })
                )}
                {b.content.note && (
                  <div
                    className={`review-note ${b.status === "approved" ? "approved" : ""}`}
                  >
                    <strong>
                      {tr(
                        b.status === "approved"
                          ? "Clinician review"
                          : "Review note",
                      )}
                    </strong>
                    <p>{b.content.note}</p>
                    <small>
                      {tr(b.reviewed_by)} · {date(b.reviewed_at)}
                    </small>
                  </div>
                )}
                <div className="brief-meta">
                  <span>{tr(b.engine)}</span>
                  <span>
                    {date(b.created_at)}
                    {tr(
                      b.content.latency_ms > 0
                        ? ` · ${b.content.latency_ms} ms`
                        : "",
                    )}
                  </span>
                </div>
                <div className="brief-actions no-print">
                  <button
                    className="button secondary"
                    onClick={() => window.print()}
                  >
                    <ArrowDownToLine size={16} />
                    {tr(t.print)}
                  </button>
                  <button
                    className="text-button"
                    disabled={generating}
                    onClick={generate}
                  >
                    {generating ? <Spinner /> : <Sparkles size={15} />}{" "}
                    {tr("Refresh brief")}
                  </button>
                </div>
              </>
            ) : (
              <Empty
                title={tr("A little preparation goes a long way")}
                description={tr(
                  "Bring your intake and records together in a source-linked brief. Your clinician reviews it before you rely on it.",
                )}
                action={
                  <button
                    className="button primary"
                    disabled={generating || (!w.intake && !w.records.length)}
                    onClick={generate}
                  >
                    {generating ? <Spinner /> : <Sparkles size={17} />}{" "}
                    {tr(
                      generating
                        ? "Preparing your brief…"
                        : "Prepare my visit brief",
                    )}
                  </button>
                }
              />
            )}
          </section>
        </div>
        <aside className="prep-aside no-print">
          {clinician && b && (
            <section className="panel review-panel">
              <span className="large-icon">
                <ClipboardCheck />
              </span>
              <h3>{tr("Make the handoff yours.")}</h3>
              <p>
                {tr(
                  "Check the sources, record corrections, and confirm the brief. Approval applies to this version only.",
                )}
              </p>
              <label>
                {tr("Review note / corrections")}
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  maxLength={4000}
                  placeholder={tr(
                    "Document what you verified or what needs clarification…",
                  )}
                  rows={5}
                />
              </label>
              {error && (
                <p className="field-error" role="alert">
                  {tr(error)}
                </p>
              )}
              <button
                className="button primary full"
                disabled={busy || b.status === "outdated"}
                onClick={() => review("approved")}
              >
                {busy ? <Spinner /> : <CheckCircle2 size={17} />}{" "}
                {tr("Approve brief")}
              </button>
              <button
                className="button secondary full"
                disabled={busy || b.status === "outdated"}
                onClick={() => review("flagged")}
              >
                <Flag size={16} /> {tr("Needs clarification")}
              </button>
            </section>
          )}
          <section className="questions-card">
            <ShieldCheck size={25} />
            <h3>{tr("Clarity, without assumptions.")}</h3>
            <p>
              {tr(
                "Missing details stay missing. Source excerpts remain unchanged. We don’t generate diagnoses or treatment advice.",
              )}
            </p>
            <div className="checklist">
              <span>
                <Check size={15} /> {tr("Original sources included")}
              </span>
              <span>
                <Check size={15} /> {tr("Unknowns kept visible")}
              </span>
              <span>
                <Check size={15} /> {tr("Human review required")}
              </span>
            </div>
          </section>
        </aside>
      </div>
    </>
  );
}
export function Instructions({
  w,
  t,
  clinician,
  create,
  refresh,
  notify,
}: Base & {
  clinician: boolean;
  create: (prev?: Instruction) => void;
  refresh: () => Promise<void>;
  notify: (msg: string) => void;
}) {
  const tr = useText();
  const date = useDate();
  const locale = locales[useLocale()];

  const [tabs, setTabs] = useState<Record<string, "plain" | "original" | "translated">>({});

  const acknowledge = async (instructionId: string, status: "acknowledged" | "needs_clarification") => {
    try {
      await post(`/instructions/${instructionId}/acknowledge`, { status });
      await refresh();
      notify(status === "acknowledged" ? "Instructions acknowledged." : "Clarification requested from care team.");
    } catch (e) {
      notify((e as Error).message);
    }
  };

  const withdraw = async (instructionId: string) => {
    const reason = window.prompt(tr("Please provide a reason for withdrawal"));
    if (!reason || reason.trim().length < 3) return;
    try {
      await post(`/instructions/${instructionId}/withdraw`, { reason: reason.trim() });
      await refresh();
      notify("Instruction withdrawn.");
    } catch (e) {
      notify((e as Error).message);
    }
  };

  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{tr(t.instructions)}</h1>
          <p>{tr(t.instructionsSub)}</p>
        </div>
        {clinician && (
          <button className="button primary" onClick={() => create()}>
            <Plus size={17} /> {tr("Add instructions")}
          </button>
        )}
      </div>
      {!w.instructions.length ? (
        <Empty
          title={tr("Next steps will appear here")}
          description={tr(
            "Your clinician can publish reviewed instructions after your visit.",
          )}
        />
      ) : (
        w.instructions.map((item) => {
          const tab = tabs[item.id] ?? "plain";
          return (
          <section className="panel instruction-card" key={item.id}>
            <div className="section-title">
              <div className="instruction-author">
                <span className="stat-icon sage">
                  <Heart size={20} />
                </span>
                <div>
                  <h3>{tr("A note from your care team")}</h3>
                  <p>
                    {item.author} · {date(item.created_at)}
                  </p>
                </div>
              </div>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <Badge tone="blue">{tr("Version")} {item.version || 1}</Badge>
                {item.status === "withdrawn" ? (
                  <Badge tone="red">{tr("Withdrawn")}</Badge>
                ) : item.status === "superseded" ? (
                  <Badge tone="neutral">{tr("Superseded")}</Badge>
                ) : item.status === "draft" ? (
                  <Badge tone="amber">{tr("Draft")}</Badge>
                ) : (
                  <Badge tone="green">{tr("Published")}</Badge>
                )}
                {item.override_reason && (
                  <Badge tone="amber">{tr("Clinician override note")}</Badge>
                )}
              </div>
            </div>
            {item.status === "withdrawn" && item.withdrawal_reason && (
              <div className="error-banner" style={{ margin: "0.5rem 0" }}>
                <strong>{tr("Withdrawn by clinician")}:</strong> {item.withdrawal_reason}
              </div>
            )}
            {item.override_reason && (
              <div style={{ margin: "0.5rem 0", fontSize: "0.85rem", color: "var(--muted)" }}>
                <strong>{tr("Clinician override note")}:</strong> {item.override_reason}
              </div>
            )}
            <div className="tabs instruction-tabs">
              {(["plain", "original", "translated"] as const).map((k) => (
                <button
                  className={tab === k ? "selected" : ""}
                  onClick={() => setTabs(current => ({...current, [item.id]: k}))}
                  aria-pressed={tab === k}
                  key={k}
                >
                  {tr(
                    k === "plain"
                      ? "Plain language"
                      : k === "original"
                        ? "Original"
                        : "Translation",
                  )}
                </button>
              ))}
            </div>
            {tab === "translated" && !item.translated ? (
              <Empty
                title={tr("No reviewed translation yet")}
                description={tr(
                  "Ask your care team for instructions in your preferred language.",
                )}
              />
            ) : (
              <div
                className="instruction-text"
                lang={tab === "translated" ? item.language : "en"}
                dir="auto"
              >
                <span className="instruction-quote">“</span>
                <p>{item[tab]}</p>
              </div>
            )}
            <p>
              {tr(
                "Original clinical content stays in its source language. Ask your care team for a reviewed translation.",
              )}
            </p>
            <div className="instruction-footer">
              <ShieldCheck size={16} />
              <span>
                {tr(
                  tab === "translated"
                    ? `${tr("Language")}: ${item.language.toUpperCase()}. `
                    : "",
                )}
                {tr(
                  "If anything is unclear, confirm it with your healthcare provider.",
                )}
              </span>
            </div>
            {/* Acknowledgement and Clinician actions */}
            <div style={{ marginTop: "1rem", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem", borderTop: "1px solid var(--border)", paddingTop: "0.75rem" }}>
              {(!item.status || item.status === "published") && !clinician && (
                item.acknowledgement_status ? (
                  <Badge tone={item.acknowledgement_status === "acknowledged" ? "green" : "amber"}>
                    {tr(item.acknowledgement_status === "acknowledged" ? "Acknowledged by patient" : "Patient requested clarification")}
                  </Badge>
                ) : (
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button className="button secondary" onClick={() => acknowledge(item.id, "acknowledged")}>
                      <Check size={15} /> {tr("I understand these instructions")}
                    </button>
                    <button className="button secondary" onClick={() => acknowledge(item.id, "needs_clarification")}>
                      <Flag size={15} /> {tr("I need clarification")}
                    </button>
                  </div>
                )
              )}
              {clinician && (!item.status || item.status === "published") && (
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button className="button secondary" onClick={() => create(item)}>
                    {tr("New version")}
                  </button>
                  <button className="button secondary" style={{ color: "var(--red, #dc2626)" }} onClick={() => withdraw(item.id)}>
                    {tr("Withdraw")}
                  </button>
                </div>
              )}
            </div>
          </section>
        );})
      )}
    </>
  );
}
export function ActivityLog({ w }: { w: Workspace }) {
  const tr = useText();
  const date = useDate();
  const locale = locales[useLocale()];

  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{tr("A transparent trail of care.")}</h1>
          <p>
            {tr("See what changed, when it happened, and who was involved.")}
          </p>
        </div>
        <Badge>
          {tr(w.activity.length)} {tr("recent events")}
        </Badge>
      </div>
      <section className="panel activity-panel">
        {w.activity.length ? (
          w.activity.map((a) => (
            <div className="activity-row" key={a.id}>
              <span className="activity-dot">
                <Check size={14} />
              </span>
              <div>
                <h3>{tr(a.action)}</h3>
                <p>
                  {[
                    "Brief prepared",
                    "Demo created",
                    "Intake saved",
                    "Instructions published",
                  ].includes(a.action)
                    ? tr(a.detail)
                    : a.detail}
                </p>
                <small>{a.actor}</small>
              </div>
              <time>
                {date(a.created_at)}
                <small>
                  {new Date(a.created_at).toLocaleTimeString(locale, {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </small>
              </time>
            </div>
          ))
        ) : (
          <Empty
            title={tr("No activity yet")}
            description={tr(
              "Saved records and clinician reviews will appear here.",
            )}
          />
        )}
      </section>
    </>
  );
}
export function PatientList({
  patients,
  open,
}: {
  patients: (User & { records: number; pending: number })[];
  open: (id: string) => void;
}) {
  const tr = useText();
  const date = useDate();
  const locale = locales[useLocale()];

  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{tr("People first. Details connected.")}</h1>
          <p>
            {tr(
              "Your assigned patients and the stories waiting for your attention.",
            )}
          </p>
        </div>
        <Badge>
          {tr(patients.length)} {tr("patients")}
        </Badge>
      </div>
      <section className="panel patient-list">
        {patients.length ? (
          patients.map((p) => (
            <button
              className="patient-row"
              key={p.id}
              onClick={() => open(p.id)}
            >
              <span className="avatar large">{p.initials}</span>
              <div>
                <h3>{p.name}</h3>
                <p>
                  {p.age != null && <>{p.age} {tr("years ·")}</>}
                  {p.language.toUpperCase()}
                </p>
              </div>
              <span>
                {tr(p.records)} {tr("records")}
              </span>
              <Badge tone={p.pending ? "amber" : "green"}>
                {tr(
                  p.pending
                    ? `${p.pending} awaiting review`
                    : "No pending briefs",
                )}
              </Badge>
              <ArrowRight size={19} />
            </button>
          ))
        ) : (
          <Empty
            title={tr("No assigned patients")}
            description={tr(
              "Patient access is restricted to your assignments.",
            )}
          />
        )}
      </section>
    </>
  );
}
