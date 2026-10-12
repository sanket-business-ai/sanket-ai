export interface User {
  email: string
  csrf_token: string
}
export interface System {
  agent_mode: string
  model: string
  worker_online: boolean
  demo_enabled: boolean
  upload_max_bytes: number
}
export interface Source {
  id: string
  name: string
  kind: string
  row_count: number
  created_at: string
  active: boolean
  checksum: string
}
export interface SourceDetail extends Source {
  rows?: Record<string, string | null>[]
  chunks?: { page: number; chunk: number; text: string }[]
  offset: number
}
export interface Metric {
  key: string
  label: string
  current: number
  previous: number
  change: number | null
  unit: string
  direction: string
  anomaly: boolean
  evidence_id: string
}
export interface Period {
  current_start: string
  current_end: string
  previous_start: string
  previous_end: string
}
export interface Investigation {
  id: string
  question: string
  mode: string
  status: string
  created_at: string
  completed_at: string | null
  parent_id: string | null
  confidence: string | null
  engine: string | null
}
export interface Trail {
  sequence: number
  stage: string
  message: string
  data: { tool?: string; result?: unknown; hypotheses?: { id: string; claim: string }[] }
  timestamp: string
}
export interface Evidence {
  id: string
  type: string
  claim: string
  value: number | null
  unit: string | null
  calculation: string | null
  sources: { id: string; name: string; locator: string }[]
}
export interface Hypothesis {
  id: string
  claim: string
  status: string
  supporting_evidence: string[]
  contradicting_evidence: string[]
  explanation: string
}
export interface Report {
  root_cause: string
  causal_chain: string[]
  evidence_ids: string[]
  confidence: string
  hypotheses: Hypothesis[]
  unknowns: string[]
  recommended_action: string
  evidence: Evidence[]
  metrics: Metric[]
  period: Period
  impact: {
    observed_revenue_difference: number | null
    currency: string
    label: string
    attributable_loss: number | null
  }
  engine: string
  model: string | null
  model_notice: string | null
  challenged: boolean
  coverage_issues: string[]
  actionable: boolean
}
export interface Action {
  id: string
  investigation_id: string
  title: string
  kind: string
  status: string
  owner: string
  metric: string
  baseline: number
  target: number
  direction: string
  approved_by: string | null
  approved_at: string | null
  due_at: string | null
  created_at: string
  outcome: {
    value: number
    target: number
    baseline: number
    checked_at: string
    note: string
    followup_investigation_id?: string
  } | null
}
export interface InvestigationDetail extends Investigation {
  source_ids: string[]
  trail: Trail[]
  report: Report | null
  error: string | null
  actions: Action[]
}
export interface Dashboard {
  metrics: Metric[]
  period: Period | null
  coverage_issues: string[]
  source_count: number
  investigation_count: number
  pending_actions: number
  recent: Investigation[]
}
export interface AuditEvent {
  id: string
  event: string
  actor: string
  entity_id: string
  details: Record<string, unknown>
  created_at: string
}
