export type Language = "en" | "hi" | "kn";
export type User = {
  id: string;
  name: string;
  email: string;
  role: "patient" | "clinician";
  language: Language;
  age: number | null;
  initials: string;
  is_demo?: boolean;
  organization?: {id:string; name:string; created_at:string} | null;
};
export type RecordItem = {
  id: string;
  title: string;
  kind: string;
  date: string | null;
  provider: string;
  created_at: string;
  text?: string;
  extraction?: {
    version: number;
    method: string;
    ocr_lang: string | null;
    pages: { page_number: number; method: string; length: number; has_warning: boolean; warning?: string | null }[];
    warnings: string[];
    notice?: string;
  };
  corrections?: {
    id: string;
    version: number;
    kind?: string;
    date?: string | null;
    provider?: string;
    text?: string;
    reason: string;
    reviewer_id: string;
    reviewer_name: string;
    created_at: string;
    previous_version?: number;
  }[];
};
export type Intake = {
  id?: string;
  reason: string;
  duration: string;
  medications: string;
  allergies: string;
  questions: string;
  language: string;
};
export type Citation = {
  source_id: string;
  source_version?: number;
  page?: number | null;
  start_offset?: number | null;
  end_offset?: number | null;
  quote: string;
};
export type BriefItem = {
  text: string;
  attribution: "patient_reported" | "document_recorded" | "clinician_reviewed";
  citations: Citation[];
};
export type BriefSection = {
  key: string;
  label: string;
  items: BriefItem[];
};
export type BriefUncertainty = {
  id: string;
  kind: "missing_information" | "conflicting_sources" | "extraction_warning";
  description: string;
  citations: Citation[];
  status: "unresolved" | "resolved";
};
export type BriefCoverage = {
  available_records: number;
  included_records: number;
  excluded_sources: { id: string; title: string; reason: string }[];
  shortened_sources: { id: string; title: string; character_count: number; truncated_to: number }[];
};
export type Brief = {
  id: string;
  status: string;
  engine: string;
  created_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  content: {
    evidence: { source_id: string; quote: string }[];
    sources: { id: string; title: string }[];
    intake: Intake | null;
    note: string;
    latency_ms: number;
    notice: string;
    processing?: {
      mode: string;
      model: string;
      policy_version: string;
      latency_ms: number;
    };
    schema_version?: string;
    source_revision?: string | number;
    sections?: BriefSection[];
    uncertainties?: BriefUncertainty[];
    coverage?: BriefCoverage;
  };
};
export type Instruction = {
  id: string;
  original: string;
  plain: string;
  translated: string;
  language: string;
  author: string;
  created_at: string;
  brief_id?: string | null;
  source_revision?: string | null;
  reviewer_id?: string | null;
  reviewer_name?: string | null;
  status?: "published" | "draft" | "superseded" | "withdrawn";
  withdrawal_reason?: string | null;
  version?: number;
  previous_version_id?: string | null;
  content_language?: string | null;
  reviewed_at?: string | null;
  acknowledged_at?: string | null;
  acknowledgement_status?: "acknowledged" | "needs_clarification" | null;
  override_reason?: string | null;
};
export type ClarificationMessage = {
  id: string;
  clarification_id: string;
  author_id: string;
  author_name: string;
  role: "patient" | "clinician";
  text: string;
  created_at: string;
};
export type Clarification = {
  id: string;
  patient_id: string;
  brief_id?: string | null;
  question: string;
  originating_uncertainty_id?: string | null;
  creator_id: string;
  creator_name: string;
  assigned_owner: "patient" | "clinician";
  status: "open" | "resolved";
  resolution_reason?: string | null;
  created_at: string;
  resolved_at?: string | null;
  resolved_by?: string | null;
  messages: ClarificationMessage[];
};
export type Workspace = {
  patient: User;
  records: RecordItem[];
  intake: Intake | null;
  brief: Brief | null;
  appointments: {
    id: string;
    clinician: string;
    specialty: string;
    location: string;
    starts_at: string;
  }[];
  instructions: Instruction[];
  clarifications?: Clarification[];
  activity: {
    id: number;
    actor: string;
    action: string;
    detail: string;
    created_at: string;
  }[];
};
export type Health = {
  status: string;
  ai_backend: string;
  model: string | null;
  amd_verified: boolean;
  demo: boolean;
};
