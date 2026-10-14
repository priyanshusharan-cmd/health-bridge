import { useHistoryNavigation } from "./useHistoryNavigation";
import { PasswordField } from "./PasswordField";
import { AccountSecurity } from "./AccountSecurity";
import { RegistrationForm, InvitePatient, JoinHospital } from "./Onboarding";
import { AppointmentForm } from "./AppointmentForm";
import { LanguageSelect } from "./LanguageSelect";
import { LocaleContext, locales, useText } from "./locale";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  CalendarDays,
  ChevronDown,
  ClipboardCheck,
  FileHeart,
  Files,
  Heart,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
  X,
  CircleHelp,
  CheckCircle2,
  AlertCircle,
  Clock3,
} from "lucide-react";
import { Account, Privacy } from "./Account";
import { ThemeToggle } from "./ThemeToggle";
import { api, post } from "./api";
import type { Health, Intake, Language, User, Workspace, Instruction } from "./types";
import { translations } from "./i18n";
import { Badge, Logo, Modal, Safety, Spinner } from "./ui";
import {
  Overview,
  Records,
  Timeline,
  VisitPrep,
  Instructions,
  ActivityLog,
  PatientList,
} from "./pages";
import { IntakeForm, UploadForm, RecordViewer, InstructionForm } from "./forms";

type Page =
  | "overview"
  | "records"
  | "timeline"
  | "prep"
  | "instructions"
  | "activity"
  | "patients";

export type DialogContext =
  | { kind: "appointment"; patientId: string; accountId: string; initial?: Workspace["appointments"][number] }
  | { kind: "upload"; patientId: string; accountId: string }
  | { kind: "intake"; patientId: string; accountId: string; initial?: Intake | null }
  | { kind: "instructions"; patientId: string; accountId: string; previousInstruction?: Instruction }
  | { kind: "record"; recordId: string; patientId?: string; accountId?: string }
  | { kind: "profile" }
  | { kind: "invite" }
  | { kind: "privacy" }
  | { kind: "about" }
  | null;

type ErrorState = {
  message: string;
  retry?: () => void | Promise<void>;
} | null;

export default function App() {
  useHistoryNavigation();
  const [user, setUser] = useState<User | null>(null),
    [health, setHealth] = useState<Health | null>(null),
    [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [preLoginLocale, setPreLoginLocale] = useState<Language>(() => {
    try {
      const saved = localStorage.getItem("healthbridge-locale");
      if (saved === "hi" || saved === "kn" || saved === "en") return saved;
    } catch {}
    return "en";
  });
  const [patients, setPatients] = useState<
      (User & { records: number; pending: number })[]
    >([]),
    [patientId, setPatientId] = useState("");
  const [page, setPage] = useState<Page>("overview"),
    [dialog, setDialog] = useState<DialogContext>(null);
  const [initializing, setInitializing] = useState(true),
    [loading, setLoading] = useState(false),
    [errorState, setErrorState] = useState<ErrorState>(null),
    [isStale, setIsStale] = useState(false),
    [toast, setToast] = useState(""),
    [mobile, setMobile] = useState(false);
  const [generation, setGeneration] = useState(false);
  const [refreshingPatients, setRefreshingPatients] = useState(false);
  const activeUser = useRef(user?.id);
  activeUser.current = user?.id;
  const activePatient = useRef(patientId);
  activePatient.current = patientId;
  const tr = useText(user?.language ?? "en");
  const t = translations[user?.language || "en"];

  const isPatientMutationDialogOpen =
    dialog !== null &&
    (dialog.kind === "appointment" ||
      dialog.kind === "upload" ||
      dialog.kind === "intake" ||
      dialog.kind === "instructions");

  useEffect(() => {
    const expired = () => {
      setUser(null);
      setDialog(null);
      setPatients([]);
      setErrorState({ message: "Your session expired. Please sign in again." });
    };
    window.addEventListener("healthbridge-session-expired", expired);
    return () => window.removeEventListener("healthbridge-session-expired", expired);
  }, []);

  useEffect(() => {
    if (dialog && "accountId" in dialog && dialog.accountId !== user?.id) {
      setDialog(null);
    }
  }, [user?.id, dialog]);

  useEffect(() => {
    if (!user) return;
    const sync = () => {
      const target = window.location.hash.slice(1) as Page;
      const allowed = [
        "overview",
        "records",
        "timeline",
        "prep",
        "instructions",
        "activity",
        ...(user.role === "clinician" ? ["patients"] : []),
      ];
      setPage(allowed.includes(target) ? target : "overview");
      setMobile(false);
    };
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, [user?.id]);

  useEffect(() => {
    Promise.all([
      api<User>("/me")
        .then(setUser)
        .catch(() => {}),
      api<Health>("/health")
        .then(setHealth)
        .catch(() =>
          setErrorState({
            message: "Cannot connect to the HealthBridge server. Start the backend and reload.",
            retry: async () => {
              try {
                const h = await api<Health>("/health");
                setHealth(h);
                setErrorState(null);
              } catch {
                setErrorState({
                  message: "Cannot connect to the HealthBridge server. Start the backend and reload.",
                });
              }
            },
          }),
        ),
    ]).finally(() => setInitializing(false));
  }, []);

  const loadPatients = useCallback(async (uid: string) => {
    try {
      const rows = await api<(User & { records: number; pending: number })[]>("/patients");
      if (activeUser.current === uid) {
        setPatients(rows);
        setPatientId((cur) => (rows.some((r) => r.id === cur) ? cur : rows[0]?.id || ""));
        setErrorState(null);
      }
    } catch (e) {
      if (activeUser.current === uid) {
        setErrorState({
          message: (e as Error).message,
          retry: () => loadPatients(uid),
        });
      }
    }
  }, []);

  useEffect(() => {
    if (!user) {
      setWorkspace(null);
      setPatients([]);
      setPatientId("");
      return;
    }
    if (user.role === "patient") {
      setPatientId(user.id);
    } else {
      loadPatients(user.id);
    }
  }, [user?.id, user?.role, loadPatients]);

  const refresh = useCallback(
    async (targetId = patientId) => {
      if (!targetId || !activeUser.current) return;
      const uid = activeUser.current;
      try {
        const result = await api<Workspace>(`/patients/${targetId}/workspace`);
        if (activePatient.current !== targetId || activeUser.current !== uid) return;
        setWorkspace(result);
        setIsStale(false);
        setErrorState(null);
        if (user?.role === "clinician") {
          const rows = await api<(User & { records: number; pending: number })[]>("/patients");
          if (activeUser.current === uid) setPatients(rows);
        }
      } catch (e) {
        if (activePatient.current === targetId && activeUser.current === uid) {
          setIsStale(true);
          setErrorState({
            message: (e as Error).message,
            retry: () => refresh(targetId),
          });
        }
      }
    },
    [patientId, user?.role]
  );

  useEffect(() => {
    if (!patientId || !user) return;
    let cancelled = false;
    setLoading(true);
    setIsStale(false);
    api<Workspace>(`/patients/${patientId}/workspace`)
      .then((data) => {
        if (!cancelled) {
          setWorkspace(data);
          setErrorState(null);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setWorkspace(null);
          setErrorState({
            message: e.message,
            retry: () => refresh(patientId),
          });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [patientId, user?.id, refresh]);

  useEffect(() => {
    if (user?.role === "patient" && !user.organization && new URLSearchParams(window.location.search).has("invite"))
      setDialog({ kind: "profile" });
  }, [user?.id]);

  useEffect(() => {
    document.documentElement.lang = user?.language || "en";
  }, [user?.language]);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(""), 5000);
    return () => clearTimeout(id);
  }, [toast]);

  const close = useCallback(() => setDialog(null), []);

  const navigate = (next: Page) => {
    window.location.hash = next;
    setPage(next);
    setMobile(false);
  };

  const [signingOut, setSigningOut] = useState(false);
  const signOut = async (all = false) => {
    if (signingOut) return;
    setSigningOut(true);
    try {
      await post(all ? "/auth/logout-all" : "/auth/logout");
      activeUser.current = undefined;
      activePatient.current = "";
      setUser(null);
      setWorkspace(null);
      setPatients([]);
      setPatientId("");
      setDialog(null);
      setMobile(false);
      setToast("");
      setErrorState(null);
      setIsStale(false);
      window.history.replaceState(null, "", window.location.pathname + "#overview");
      setPage("overview");
    } catch (e) {
      setErrorState({ message: (e as Error).message });
    } finally {
      setSigningOut(false);
    }
  };

  const handleSaved = async (
    targetPatientId: string,
    initiatingAccountId: string,
    successMessage: string
  ) => {
    close();
    if (!activeUser.current || activeUser.current !== initiatingAccountId) return;
    try {
      const updated = await api<Workspace>(`/patients/${targetPatientId}/workspace`);
      if (activeUser.current !== initiatingAccountId) return;
      if (activePatient.current === targetPatientId) {
        setWorkspace(updated);
        setIsStale(false);
        setErrorState(null);
      }
      if (user?.role === "clinician") {
        const rows = await api<(User & { records: number; pending: number })[]>("/patients");
        if (activeUser.current === initiatingAccountId) setPatients(rows);
      }
      if (activePatient.current === targetPatientId) {
        setToast(successMessage);
      }
    } catch {
      if (activeUser.current !== initiatingAccountId) return;
      setIsStale(true);
      setToast(`${successMessage} (${tr("Refresh failed")})`);
      setErrorState({
        message: "Saved; refresh failed. Check your connection.",
        retry: () => refresh(targetPatientId),
      });
    }
  };

  const openRecord = (id: string) => {
    if (!user) return;
    setDialog({
      kind: "record",
      recordId: id,
      patientId,
      accountId: user.id,
    });
  };

  const generate = async () => {
    if (!patientId || !user) return;
    const targetPatient = patientId;
    const targetUser = user.id;
    setGeneration(true);
    try {
      await post(`/patients/${targetPatient}/brief`);
      await refresh(targetPatient);
      if (activePatient.current !== targetPatient || activeUser.current !== targetUser) return;
      navigate("prep");
      setToast("Your source-linked visit brief is ready for review.");
    } catch (e) {
      if (activeUser.current === targetUser) {
        setErrorState({
          message: (e as Error).message,
          retry: () => refresh(targetPatient),
        });
      }
    } finally {
      setGeneration(false);
    }
  };
  const nav = [
    { key: "overview", icon: LayoutDashboard },
    { key: "records", icon: Files },
    { key: "timeline", icon: Heart },
    { key: "prep", icon: ClipboardCheck },
    { key: "instructions", icon: ListChecks },
    { key: "activity", icon: Clock3 },
  ] as const;
  if (initializing)
    return (
      <div className="boot">
        <Logo />
        <Spinner />
        <p>{tr("Connecting your care…")}</p>
      </div>
    );
  if (!user)
    return (
      <LocaleContext.Provider value={preLoginLocale}>
        <Login
          preLoginLocale={preLoginLocale}
          onLocaleChange={(lang) => {
            setPreLoginLocale(lang);
            try {
              localStorage.setItem("healthbridge-locale", lang);
            } catch {}
          }}
          onLogin={(u) => {
            setUser(u);
            setErrorState(null);
          }}
          error={errorState?.message || ""}
          connected={!!health}
          onRetry={async () => {
            try {
              setHealth(await api<Health>("/health"));
              setErrorState(null);
            } catch (e) {
              setErrorState({ message: (e as Error).message });
            }
          }}
        />
      </LocaleContext.Provider>
    );
  return (
    <LocaleContext.Provider value={user.language}>
      <div className="app-shell">
        {mobile && (
          <div className="sidebar-scrim" onClick={() => setMobile(false)} />
        )}
        <aside className={`sidebar ${mobile ? "open" : ""}`}>
          <button
            className="brand-home"
            aria-label={tr("HealthBridge home")}
            onClick={() => navigate("overview")}
          >
            <Logo />
          </button>
          <div className="workspace-label">
            {tr(
              user.role === "clinician"
                ? "CLINICIAN WORKSPACE"
                : "YOUR CARE SPACE",
            )}
          </div>
          <nav aria-label={tr("Main navigation")}>
            {user.role === "clinician" && (
              <button
                onClick={() => navigate("patients")}
                className={page === "patients" ? "active" : ""}
              >
                <Users size={19} />
                {tr(t.patients)}
                <span className="nav-count">{tr(patients.length)}</span>
              </button>
            )}
            {nav.map(({ key, icon: Icon }) => (
              <button
                key={key}
                onClick={() => navigate(key)}
                className={page === key ? "active" : ""}
              >
                <Icon size={19} />
                {tr(t[key])}
                {key === "records" && workspace && (
                  <span className="nav-count">
                    {tr(workspace.records.length)}
                  </span>
                )}
                {key === "prep" && workspace?.brief?.status === "pending" && (
                  <span className="nav-dot" />
                )}
              </button>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="care-promise">
              <span className="small-heart">
                <Heart size={19} />
              </span>
              <h4>{tr("Care is a team effort.")}</h4>
              <p>
                {tr("Your story stays connected.")}
                <br />
                {tr("Your clinician stays in control.")}
              </p>
              <button onClick={() => setDialog({ kind: "about" })}>
                {tr("Our approach")}
                <ArrowRight size={14} />
              </button>
            </div>
            <button className="help-button" onClick={() => setDialog({ kind: "about" })}>
              <CircleHelp size={18} /> {tr("About this demo")}
            </button>
            <div className="sidebar-profile">
              <button
                className="avatar"
                aria-label={tr("Open profile")}
                onClick={() => setDialog({ kind: "profile" })}
              >
                {user.initials}
              </button>
              <div>
                <strong>{user.name}</strong>
                <small>
                  {tr(
                    user.role === "patient"
                      ? "Patient account"
                      : "Clinician account",
                  )}
                </small>
              </div>
              <button
                className="icon-button"
                title={tr(t.logout)}
                aria-label={tr(t.logout)}
                disabled={signingOut}
                onClick={() => signOut()}
              >
                <LogOut size={17} />
              </button>
            </div>
          </div>
        </aside>
        <div className="main-shell">
          <header className="topbar">
            <div className="breadcrumb">

              <button
                className="icon-button mobile-menu"
                onClick={() => setMobile(true)}
                aria-label={tr("Open navigation")}
              >
                <Menu size={21} />
              </button>
              <button
                className="workspace-home"
                onClick={() => navigate("overview")}
              >
                {tr("My workspace")}
              </button>
              <span className="slash">/</span>
              <strong>{tr(t[page])}</strong>
            </div>
            <div className="topbar-actions">
              <ThemeToggle />
              <button
                className="private-label"
                onClick={() => setDialog({ kind: "privacy" })}
              >
                <ShieldCheck size={14} /> {tr("Privacy notice")}
              </button>
              <label className="language-select">
                <span className="sr-only">{tr(t.language)}</span>
                <LanguageSelect interfaceOnly
                  label={tr(t.language)}
                  value={user.language}
                  onChange={async (value) => {
                    try {
                      setUser(
                        await api<User>("/me", {
                          method: "PATCH",
                          body: JSON.stringify({
                            language: value as Language,
                          }),
                        }),
                      );
                    } catch (e) {
                      setErrorState({ message: (e as Error).message });
                    }
                  }}
                />
                <ChevronDown size={13} />
              </label>
              <button
                className="avatar small"
                aria-label={tr("Open account profile")}
                onClick={() => setDialog({ kind: "profile" })}
              >
                {user.initials}
              </button>
            </div>
          </header>
          {health?.demo && (
            <div className="demo-banner">
              <span className="demo-dot" />
              <strong>{tr("Demo workspace")}</strong>
              <span>
                {tr(
                  "Synthetic patients only. Please don’t upload real medical data.",
                )}
              </span>
              <Badge>{tr("PREVIEW")}</Badge>
            </div>
          )}
          <main id="main-content">
            <div className="page-topline">
              <span className="eyebrow">
                {tr(
                  user.role === "clinician"
                    ? "A CONNECTED VIEW OF YOUR PATIENT"
                    : "A CLEARER PATH TO CARE",
                )}
              </span>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                {isStale && (
                  <Badge tone="amber">{tr("Showing cached data · Refresh failed")}</Badge>
                )}
                <span className="today">
                  {new Date().toLocaleDateString(locales[user.language], {
                    weekday: "long",
                    month: "long",
                    day: "numeric",
                  })}
                </span>
              </div>
            </div>
            {user.role === "clinician" && page !== "patients" && (
              <div className="patient-switch">
                <Users size={17} />
                <label htmlFor="patient-select">{tr("Patient")}</label>
                <select
                  id="patient-select"
                  disabled={generation || isPatientMutationDialogOpen}
                  value={patientId}
                  onChange={(e) => setPatientId(e.target.value)}
                >
                  {patients.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <Badge>{tr("Assigned to you")}</Badge>
              </div>
            )}
            {errorState && (
              <div className="error-banner" role="alert">
                <AlertCircle size={18} />
                <span>{tr(errorState.message)}</span>
                {errorState.retry && (
                  <button
                    onClick={() => {
                      const retryFn = errorState.retry;
                      setErrorState(null);
                      retryFn?.();
                    }}
                  >
                    {tr("Retry")}
                  </button>
                )}
                <button
                  className="icon-button"
                  aria-label={tr("Dismiss error")}
                  onClick={() => setErrorState(null)}
                >
                  <X size={16} />
                </button>
              </div>
            )}
            {loading ? (
              <div
                className="skeleton-area"
                aria-label={tr("Loading workspace")}
              >
                <div />
                <div />
                <div />
              </div>
            ) : page === "patients" ? (
              <><div className="hospital-toolbar">
                <button className="button secondary" disabled={refreshingPatients} onClick={async()=>{
                  setRefreshingPatients(true);const uid=user.id;
                  try{const rows=await api<(User & {records:number;pending:number})[]>("/patients");
                    if(activeUser.current===uid){setPatients(rows);setPatientId(current=>rows.some(row=>row.id===current)?current:rows[0]?.id||"");}
                  }catch(e){if(activeUser.current===uid)setErrorState({message:(e as Error).message, retry:()=>loadPatients(uid)});}finally{setRefreshingPatients(false);}
                }}>{refreshingPatients&&<Spinner/>}{tr("Refresh patients")}</button>
                {user.organization && <><h2>{user.organization.name}</h2><button className="button primary" onClick={()=>setDialog({ kind: "invite" })}>{tr("Invite a patient")}</button></>}
              </div><PatientList
                patients={patients}
                open={(id) => {
                  setPatientId(id);
                  navigate("overview");
                }}
              /></>
            ) : workspace ? (
              <>
                {page === "overview" && (
                  <Overview
                    w={workspace}
                    t={t}
                    clinician={user.role === "clinician"}
                    navigate={navigate}
                    onAppointment={() =>
                      setDialog({
                        kind: "appointment",
                        patientId,
                        accountId: user.id,
                        initial: workspace.appointments.find((a) => new Date(a.starts_at) > new Date()),
                      })
                    }
                    onIntake={() =>
                      setDialog({
                        kind: "intake",
                        patientId,
                        accountId: user.id,
                        initial: workspace.intake,
                      })
                    }
                    onUpload={() =>
                      setDialog({
                        kind: "upload",
                        patientId,
                        accountId: user.id,
                      })
                    }
                    openRecord={openRecord}
                  />
                )}
                {page === "records" && (
                  <Records
                    w={workspace}
                    t={t}
                    onUpload={() =>
                      setDialog({
                        kind: "upload",
                        patientId,
                        accountId: user.id,
                      })
                    }
                    openRecord={openRecord}
                  />
                )}
                {page === "timeline" && (
                  <Timeline w={workspace} t={t} openRecord={openRecord} />
                )}
                {page === "prep" && (
                  <VisitPrep
                    key={patientId}
                    w={workspace}
                    t={t}
                    clinician={user.role === "clinician"}
                    generate={generate}
                    generating={generation}
                    onIntake={() =>
                      setDialog({
                        kind: "intake",
                        patientId,
                        accountId: user.id,
                        initial: workspace.intake,
                      })
                    }
                    openRecord={openRecord}
                    refresh={refresh}
                    notify={setToast}
                  />
                )}
                {page === "instructions" && (
                  <Instructions
                    w={workspace}
                    t={t}
                    clinician={user.role === "clinician"}
                    create={(prev?: Instruction) =>
                      setDialog({
                        kind: "instructions",
                        patientId,
                        accountId: user.id,
                        previousInstruction: prev,
                      })
                    }
                    refresh={() => refresh(patientId)}
                    notify={setToast}
                  />
                )}
                {page === "activity" && <ActivityLog w={workspace} />}
              </>
            ) : (
              !errorState && (
                <div className="empty">
                  <Users />
                  <h2>{tr("No assigned patients")}</h2>
                  <p>{tr("Your assigned patients will appear here.")}</p>
                </div>
              )
            )}
            <footer className="workspace-footer">
              <Safety />
              <button
                className="text-button"
                onClick={() => setDialog({ kind: "privacy" })}
              >
                {tr("Privacy notice")}
              </button>
              <span className="runtime">
                <span />
                {tr(
                  health?.ai_backend === "extractive"
                    ? "Source-only mode · no AI inference"
                    : `${health?.ai_backend} ${tr("model configured")}`,
                )}
              </span>
            </footer>
          </main>
        </div>
        {toast && (
          <div className="toast" role="status">
            <CheckCircle2 size={20} />
            {tr(toast)}
            <button
              className="icon-button"
              aria-label={tr("Dismiss notification")}
              onClick={() => setToast("")}
            >
              <X size={16} />
            </button>
          </div>
        )}
        {dialog?.kind === "appointment" && (
          <Modal title={tr("Appointment details")} onClose={close}>
            <AppointmentForm
              key={dialog.patientId}
              patientId={dialog.patientId}
              initial={dialog.initial}
              onSaved={() => handleSaved(dialog.patientId, dialog.accountId, "Appointment saved")}
            />
          </Modal>
        )}
        {dialog?.kind === "profile" && (
          <Modal title={tr("Your profile")} onClose={close}>
            {errorState && <p role="alert" className="field-error">{tr(errorState.message)}</p>}
            <div className="account-actions">
              <button className="button secondary" disabled={signingOut} onClick={() => signOut()}>
                <LogOut size={16} />{tr("Sign out")}
              </button>
              <button className="text-button" disabled={signingOut} onClick={() => signOut(true)}>
                {tr("Sign out all devices")}
              </button>
              <button className="text-button" onClick={() => setDialog({ kind: "privacy" })}>
                {tr("Privacy notice")}
              </button>
            </div>
            {user.organization && <p className="organization-label">{user.organization.name}</p>}
            <Account
              user={user}
              onSaved={async (updated) => {
                setUser(updated);
                try {
                  await refresh();
                  close();
                  setToast("Profile saved.");
                } catch {
                  close();
                  setToast("Profile saved. (Refresh failed)");
                  setErrorState({
                    message: "Saved; refresh failed. Check your connection.",
                    retry: () => refresh(),
                  });
                }
              }}
            />
            <AccountSecurity demo={!!user.is_demo} />
            {user.role === "patient" && !user.organization && !user.is_demo && (
              <JoinHospital
                onJoined={(updated) => {
                  setUser(updated);
                  close();
                  setToast("Hospital joined");
                }}
              />
            )}
          </Modal>
        )}
        {dialog?.kind === "invite" && user.organization && (
          <Modal title={tr("Invite a patient")} onClose={close}>
            <InvitePatient />
          </Modal>
        )}
        {dialog?.kind === "privacy" && (
          <Modal
            title={tr("How this demo handles information")}
            onClose={close}
          >
            <Privacy />
          </Modal>
        )}
        {dialog?.kind === "upload" && (
          <Modal title={tr("Add to your health story")} onClose={close}>
            <UploadForm
              key={dialog.patientId}
              patientId={dialog.patientId}
              onSaved={() =>
                handleSaved(dialog.patientId, dialog.accountId, "Record added to your care timeline.")
              }
            />
          </Modal>
        )}
        {dialog?.kind === "intake" && (
          <Modal title={tr(t.intake)} onClose={close} wide>
            <IntakeForm
              key={dialog.patientId}
              patientId={dialog.patientId}
              initial={dialog.initial || null}
              language={user.language}
              t={t}
              onSaved={() =>
                handleSaved(dialog.patientId, dialog.accountId, "Your visit information has been saved.")
              }
            />
          </Modal>
        )}
        {dialog?.kind === "record" && (
          <Modal
            title={tr("A closer look at your record")}
            onClose={close}
            wide
          >
            <RecordViewer
              id={dialog.recordId}
              clinician={user.role === "clinician"}
              onUpdated={() => refresh(patientId)}
              onDeleted={() => {
                close();
                refresh(patientId);
                setToast("Record withdrawn. Any dependent visit brief has been marked outdated.");
              }}
            />
          </Modal>
        )}
        {dialog?.kind === "instructions" && (
          <Modal title={tr("Publish clear next steps")} onClose={close} wide>
            <InstructionForm
              key={dialog.patientId}
              patientId={dialog.patientId}
              previousInstruction={dialog.previousInstruction}
              onSaved={() =>
                handleSaved(dialog.patientId, dialog.accountId, "Reviewed instructions are now available to the patient.")
              }
            />
          </Modal>
        )}
        {dialog?.kind === "about" && (
          <Modal
            title={tr("Built around people, not predictions")}
            onClose={close}
          >
            <div className="about-content">
              <span className="large-icon">
                <ShieldCheck />
              </span>
              <p>
                {tr(
                  "HealthBridge brings records and patient concerns into one source-linked brief. Clinicians review the information and write the next steps.",
                )}
              </p>
              <h3>{tr("What’s running?")}</h3>
              <p>
                {tr("Backend:")}
                <strong>{health?.status || "Unavailable"}</strong>
                <br />
                {tr("Processing:")}
                <strong>{tr(health?.ai_backend)}</strong>
                {health?.model && (
                  <>
                    <br />
                    {tr("Model:")}
                    {tr(health.model)}
                  </>
                )}
              </p>
              <p>
                {tr(
                  "Source-only mode selects excerpts without an AI model. The model adapter supports Ollama and AMD-hosted vLLM. AMD hardware execution has not been verified in this environment.",
                )}
              </p>
              <h3>{tr("Safe demo, honest boundaries")}</h3>
              <p>
                {tr(
                  "Use synthetic data only. This prototype does not diagnose, prescribe, or claim regulatory certification. Core navigation is multilingual; clinical translations must be checked by a qualified reviewer.",
                )}
              </p>
              <Badge tone="green">{tr("Human review stays in the loop")}</Badge>
            </div>
          </Modal>
        )}
      </div>
    </LocaleContext.Provider>
  );
}
export function Login({
  onLogin,
  error,
  connected,
  onRetry,
  preLoginLocale = "en",
  onLocaleChange,
}: {
  onLogin: (u: User) => void;
  error: string;
  connected: boolean;
  onRetry: () => Promise<void>;
  preLoginLocale?: Language;
  onLocaleChange?: (lang: Language) => void;
}) {
  const tr = useText();
  const [retrying, setRetrying] = useState(false);

  const [accounts, setAccounts] = useState<
      { email: string; name: string; role: string; password: string }[]
    >([]),
    [busy, setBusy] = useState(""),
    [message, setMessage] = useState(""),
    [showForm, setShowForm] = useState(true),
    [registering,setRegistering] = useState(window.location.hash === "#register" || new URLSearchParams(window.location.search).has("invite"));
  useEffect(() => {
    api<typeof accounts>("/demo-accounts")
      .then(setAccounts)
      .catch(() => {});
  }, [connected]);
  const login = async (email: string, password: string) => {
    setBusy(email);
    setMessage("");
    try {
      onLogin(await post<User>("/auth/login", { email, password }));
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy("");
    }
  };
  return (
    <div className="login-page">
      <header>
        <Logo />
        <LanguageSelect
          interfaceOnly
          value={preLoginLocale}
          onChange={(l) => onLocaleChange?.(l as Language)}
        />
        <ThemeToggle />
        <span className="login-header-note">
          <ShieldCheck size={16} /> {tr("Human-centered. Open by design.")}
        </span>
      </header>
      <div className="login-layout">
        <section className="login-story">
          <div className="pill">
            <span /> {tr("YOUR CARE, CONNECTED")}
          </div>
          <h1>
            {tr("A clearer path")}
            <br />
            {tr("to")}{" "}
            <em>{tr("better care.")}</em>
          </h1>
          <p>
            {tr(
              "Your health story shouldn’t get lost between documents, languages, and appointments. Bring it all together — with your care team by your side.",
            )}
          </p>
          <div className="login-journey">
            <span>
              <Files />
              {tr("Share your records")}
            </span>
            <ArrowRight />
            <span>
              <Sparkles />
              {tr("Prepare together")}
            </span>
            <ArrowRight />
            <span>
              <Heart />
              {tr("Move forward")}
            </span>
          </div>
          <div className="story-visual">
            <div className="visual-orbit orbit-one" />
            <div className="visual-orbit orbit-two" />
            <div className="floating-record">
              <span className="record-icon sage">
                <FileHeart size={25} />
              </span>
              <div>
                <strong>{tr("Your story, connected")}</strong>
                <small>{tr("Every detail has a source.")}</small>
              </div>
              <CheckCircle2 size={21} />
            </div>
            <div className="floating-review">
              <ShieldCheck size={19} />
              <span>
                {tr("Reviewed by a human.")}
                <br />
                <strong>{tr("Made clearer for you.")}</strong>
              </span>
            </div>
          </div>
        </section>
        <section className="login-card">
          <span className="eyebrow">{tr("WELCOME TO HEALTHBRIDGE")}</span>
          <h2>
            {tr("Good care starts")}{" "}
            <br />
            {tr("with understanding.")}
          </h2>
          <p>{tr("Step into a connected care journey.")}</p>
          {(message || error) && (
            <div className="error-banner" role="alert">
              {message || error}
            </div>
          )}
          {!connected && <button className="button secondary full" disabled={retrying} onClick={async () => {
            setRetrying(true);
            try { await onRetry(); } finally { setRetrying(false); }
          }}>{retrying && <Spinner />}{tr("Retry connection")}</button>}
          {!registering && accounts.length > 0 && (
            <>
              <span className="login-caption">{tr("EXPLORE THE DEMO AS")}</span>
              {accounts.map((a) => (
                <button
                  className="account-choice"
                  disabled={!!busy || !connected}
                  key={a.email}
                  onClick={() => login(a.email, a.password)}
                >
                  <span
                    className={`account-icon ${a.role === "clinician" ? "lavender" : "sage"}`}
                  >
                    {a.role === "clinician" ? <ClipboardCheck /> : <Heart />}
                  </span>
                  <span>
                    <strong>
                      {tr(a.role === "clinician" ? "A clinician" : "A patient")}
                    </strong>
                    <small>
                      {tr(
                        a.role === "clinician"
                          ? "Review the story. Guide the next step."
                          : "Your records. Your language. Your care.",
                      )}
                    </small>
                  </span>
                  {busy === a.email ? <Spinner /> : <ArrowRight size={19} />}
                </button>
              ))}
            </>
          )}
          <div className="onboarding-actions"><button className="text-button" onClick={()=>{setRegistering(value=>!value);setShowForm(true);}}>{tr(registering ? "Back to sign in" : "Create account")}</button></div>
          {registering && <RegistrationForm onCreated={onLogin} connected={connected} />}
          {!registering && <button
            className="text-button signin-link"
            onClick={() => setShowForm(!showForm)}
          >
            {tr(showForm ? "Hide sign-in form" : "Sign in with your account")}
            <ArrowRight size={15} />
          </button>}
          {showForm && !registering && (
            <form
              className="signin-form"
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                login(String(f.get("email")), String(f.get("password")));
              }}
            >
              <label>
                {tr("Email")}
                <input
                  name="email"
                  type="email"
                  required
                  autoComplete="username"
                />
              </label>
              <PasswordField name="password" label={tr("Password")} />
              <button className="button primary" disabled={!!busy || !connected}>
                {tr("Sign in")}
                {busy && <Spinner />}
              </button>
            </form>
          )}
          <div className="login-foot">
            <ShieldCheck size={17} />
            <span>
              {tr(
                accounts.length
                  ? "Fictional patients. Real, connected workflows."
                  : "Secure account access.",
              )}
              <br />
              {tr(
                connected
                  ? "Please don’t enter sensitive medical information."
                  : "Backend connection required.",
              )}
            </span>
          </div>
        </section>
      </div>
      <footer>
        <span>{tr("Connecting patients, providers, and care.")}</span>
        <span>{tr("HealthBridge")}</span>
      </footer>
    </div>
  );
}
