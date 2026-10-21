import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Download,
  FileText,
  FlaskConical,
  GitBranch,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Terminal,
  TriangleAlert,
} from 'lucide-react'
import { api, post } from '@/lib/api'
import type { Investigation, InvestigationDetail, Trail } from '@/lib/types'
import { cn, currency, dateTime } from '@/lib/utils'
import { ErrorState, Loading, MetricCard, Status } from '@/components/shared'
import { ActionCard } from '@/components/ActionCard'
import { SourcePreview } from '@/components/SourcePreview'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

function TrailView({ trail, running }: { trail: Trail[]; running: boolean }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <GitBranch size={17} />
          Investigation trail
        </CardTitle>
        <p className="mt-2 text-xs leading-5 text-muted-foreground">
          Recorded decisions and tool results — a reviewable trail of what was checked.
        </p>
      </CardHeader>
      <CardContent>
        <ol className="trail-list">
          {trail.map((item) => (
            <li key={item.sequence}>
              <span
                className={cn(
                  'trail-dot',
                  ['challenge', 'conclusion'].includes(item.stage)
                    ? 'bg-primary/10 text-primary'
                    : 'bg-muted text-muted-foreground',
                )}
              >
                {item.stage === 'tool' ? (
                  <Terminal size={14} />
                ) : item.stage === 'conclusion' ? (
                  <CheckCircle2 size={14} />
                ) : (
                  <Search size={14} />
                )}
              </span>
              <div className="flex items-start justify-between gap-3">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-primary">
                  {item.data.tool?.replaceAll('_', ' ') || item.stage}
                </p>
                <time className="shrink-0 text-[11px] text-muted-foreground">
                  {dateTime(item.timestamp)}
                </time>
              </div>
              <p className="mt-2 text-sm leading-6">{item.message}</p>
              {item.data.hypotheses && (
                <ul className="mt-3 space-y-2">
                  {item.data.hypotheses.map((h) => (
                    <li key={h.id} className="rounded-md bg-muted p-3 text-xs">
                      <strong className="mr-2 text-primary">{h.id}</strong>
                      {h.claim}
                    </li>
                  ))}
                </ul>
              )}
              {item.data.result !== undefined && (
                <details className="mt-3">
                  <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-primary">
                    Inspect tool result
                  </summary>
                  <pre className="mt-3 max-h-72 overflow-auto rounded-lg bg-muted p-4 text-[11px] leading-5">
                    {JSON.stringify(item.data.result, null, 2)}
                  </pre>
                </details>
              )}
            </li>
          ))}
        </ol>
        {running && (
          <p role="status" className="ml-2 flex items-center gap-3 py-4 text-xs text-primary">
            <Loader2 size={16} className="animate-spin" />
            Investigator is working. Progress saves automatically.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export default function InvestigationView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const client = useQueryClient()
  const [tab, setTab] = useState('report')
  const [focusEvidence, setFocusEvidence] = useState<string | null>(null)
  const [source, setSource] = useState<string | null>(null)
  const query = useQuery({
    queryKey: ['investigation', id],
    queryFn: () => api<InvestigationDetail>(`/investigations/${id}`),
    refetchInterval: (q) =>
      ['queued', 'running'].includes(q.state.data?.status || '') ? 1500 : false,
  })
  const rerun = useMutation({
    mutationFn: (kind: string) => post<Investigation>(`/investigations/${id}/${kind}`),
    onSuccess: (job) => {
      client.invalidateQueries({ queryKey: ['investigations'] })
      navigate(`/investigations/${job.id}`)
      setTab('trail')
    },
  })
  useEffect(() => {
    if (focusEvidence && tab === 'evidence')
      document.getElementById(`evidence-${focusEvidence}`)?.scrollIntoView({
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
          ? 'instant'
          : 'smooth',
        block: 'center',
      })
  }, [focusEvidence, tab])
  function showEvidence(eid: string) {
    setFocusEvidence(eid)
    setTab('evidence')
  }
  if (query.isPending) return <Loading label="Opening investigation…" />
  if (query.error) return <ErrorState error={query.error} retry={() => query.refetch()} />
  const job = query.data
  const report = job.report
  const running = ['queued', 'running'].includes(job.status)
  return (
    <>
      <Link
        to="/investigations"
        className="mb-6 inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-primary"
      >
        <ArrowLeft size={14} />
        All investigations
      </Link>
      <div className="mb-7 flex flex-wrap items-start justify-between gap-5">
        <div className="max-w-3xl">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <p className="eyebrow">INVESTIGATION · {job.id.slice(0, 8)}</p>
            <Status value={job.status} />
          </div>
          <h1 className="text-[28px] font-semibold leading-snug tracking-tight">{job.question}</h1>
          <p className="mt-3 text-xs text-muted-foreground">
            Started {dateTime(job.created_at)} · {job.source_ids.length} source versions
            {job.parent_id && (
              <>
                {' '}
                ·{' '}
                <Link to={`/investigations/${job.parent_id}`} className="font-medium text-primary">
                  View original investigation
                </Link>
              </>
            )}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {report && (
            <>
              <Button variant="outline" size="sm" asChild>
                <a href={`/api/investigations/${id}/export`} download>
                  <Download />
                  Export report
                </a>
              </Button>
              <Button
                size="sm"
                disabled={rerun.isPending}
                onClick={() => rerun.mutate('challenge')}
              >
                {rerun.isPending ? <Loader2 className="animate-spin" /> : <FlaskConical />}Challenge
                conclusion
              </Button>
            </>
          )}
          {job.status === 'failed' && (
            <Button size="sm" disabled={rerun.isPending} onClick={() => rerun.mutate('retry')}>
              <RefreshCw />
              Retry investigation
            </Button>
          )}
        </div>
      </div>
      {rerun.error && (
        <div className="mb-5">
          <ErrorState error={rerun.error} />
        </div>
      )}
      {job.error && (
        <div className="mb-5">
          <ErrorState error={new Error(job.error)} />
        </div>
      )}
      {running ? (
        <>
          <Card className="mb-6 border-primary/20 bg-primary/5 p-6">
            <div className="flex items-start gap-4">
              <span className="rounded-xl bg-primary/10 p-3 text-primary">
                <Loader2 className="animate-spin" size={23} />
              </span>
              <div>
                <h2 className="font-semibold">
                  {job.status === 'queued'
                    ? 'Your investigation is queued'
                    : 'Following the evidence…'}
                </h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {job.status === 'queued'
                    ? 'The worker will pick up this investigation. If it stays queued, start the backend worker.'
                    : 'SanketAI is testing explanations and checking competing evidence. You can leave this page and return later.'}
                </p>
              </div>
            </div>
          </Card>
          <TrailView trail={job.trail} running />
        </>
      ) : report ? (
        <>
          <div className="mb-6 flex flex-wrap items-center gap-2">
            <Badge variant={report.engine === 'deterministic' ? 'warning' : 'default'}>
              <Sparkles size={12} />
              {report.engine !== 'deterministic'
                ? `${report.engine === 'hosted' ? 'Hosted agent' : 'Local agent'} · ${report.model}`
                : 'Deterministic evidence analysis'}
            </Badge>
            <Badge variant="outline">{report.confidence} evidence strength</Badge>
            {report.challenged && (
              <Badge variant="default">
                <FlaskConical size={11} />
                Adversarial pass completed
              </Badge>
            )}
          </div>
          {report.model_notice && (
            <p className="mb-5 rounded-lg border border-warning/20 bg-warning-bg p-3 text-xs leading-6 text-warning">
              {report.model_notice}
            </p>
          )}
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="max-w-full overflow-x-auto">
              <TabsTrigger value="report">Report</TabsTrigger>
              <TabsTrigger value="hypotheses">Hypotheses ({report.hypotheses.length})</TabsTrigger>
              <TabsTrigger value="evidence">Evidence ({report.evidence.length})</TabsTrigger>
              <TabsTrigger value="trail">Trail ({job.trail.length})</TabsTrigger>
            </TabsList>
            <TabsContent value="report">
              <section className="report-grid">
                <div className="space-y-6">
                  <Card className="root-cause-card">
                    <CardHeader>
                      <p className="eyebrow flex items-center gap-2 text-primary">
                        <ShieldCheck size={16} />
                        STRONGEST SUPPORTED EXPLANATION
                      </p>
                    </CardHeader>
                    <CardContent>
                      <p className="text-lg font-medium leading-8 tracking-tight">
                        {report.root_cause}
                      </p>
                      <div className="mt-6 flex flex-wrap items-center gap-2">
                        {report.causal_chain.map((item, index) => (
                          <span className="contents" key={index}>
                            <span className="rounded-lg border border-primary/15 bg-card/80 px-3 py-2 text-xs font-medium text-primary">
                              {item}
                            </span>
                            {index < report.causal_chain.length - 1 && (
                              <ChevronRight size={14} className="text-primary/40" />
                            )}
                          </span>
                        ))}
                      </div>
                      <div className="mt-5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span>Supporting evidence</span>
                        {report.evidence_ids.map((eid) => (
                          <button
                            key={eid}
                            className="evidence-chip"
                            onClick={() => showEvidence(eid)}
                          >
                            {eid}
                          </button>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle>Business impact</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {report.scenario === 'margin' &&
                      report.impact.observed_contribution_difference != null ? (
                        <>
                          <p className="text-3xl font-semibold tracking-tight">
                            {currency(report.impact.observed_contribution_difference)}
                          </p>
                          <p className="mt-2 text-xs text-muted-foreground">
                            Observed contribution difference, from recorded costs
                          </p>
                          {report.impact.observed_revenue_difference !== null && (
                            <p className="mt-3 text-xs text-muted-foreground">
                              Revenue difference:{' '}
                              {currency(report.impact.observed_revenue_difference)}
                            </p>
                          )}
                        </>
                      ) : (
                        <>
                          <p className="text-3xl font-semibold tracking-tight">
                            {report.impact.observed_revenue_difference === null
                              ? 'Insufficient baseline'
                              : currency(report.impact.observed_revenue_difference)}
                          </p>
                          <p className="mt-2 text-xs text-muted-foreground">
                            {report.impact.label}
                          </p>
                        </>
                      )}
                      <p className="mt-4 text-xs leading-6 text-muted-foreground">
                        Current: {report.period.current_start} — {report.period.current_end}
                        <br />
                        Baseline: {report.period.previous_start} — {report.period.previous_end}
                      </p>
                    </CardContent>
                  </Card>
                  <div>
                    <h2 className="mb-4 text-sm font-semibold">Recommended action</h2>
                    {job.actions.length ? (
                      job.actions.map((action) => <ActionCard key={action.id} action={action} />)
                    ) : (
                      <Card className="p-5">
                        <p className="text-sm leading-7">{report.recommended_action}</p>
                        <p className="mt-3 text-xs leading-5 text-muted-foreground">
                          Collect stronger evidence before creating an operational action.
                        </p>
                      </Card>
                    )}
                  </div>
                </div>
                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <TriangleAlert size={16} className="text-warning" />
                        What we still don’t know
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-4">
                        {report.unknowns.map((unknown, index) => (
                          <li
                            key={index}
                            className="flex gap-3 text-xs leading-6 text-muted-foreground"
                          >
                            <span className="mt-2 size-1 shrink-0 rounded-full bg-warning-bg0" />
                            {unknown}
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                  <Card className="border-dashed bg-transparent shadow-none">
                    <CardContent className="pt-6">
                      <FlaskConical size={20} className="mb-3 text-primary" />
                      <h3 className="text-sm font-semibold">
                        A good explanation survives a challenge.
                      </h3>
                      <p className="mt-3 text-xs leading-6 text-muted-foreground">
                        Run a deliberate second pass using the same evidence snapshot. Your original
                        report stays available for comparison.
                      </p>
                      <Button
                        className="mt-4"
                        variant="outline"
                        size="sm"
                        disabled={rerun.isPending}
                        onClick={() => rerun.mutate('challenge')}
                      >
                        Challenge conclusion
                        <ArrowRight />
                      </Button>
                    </CardContent>
                  </Card>
                </div>
              </section>
              <div className="metric-grid mt-6">
                {report.metrics.map((metric) => (
                  <MetricCard key={metric.key} metric={metric} />
                ))}
              </div>
            </TabsContent>
            <TabsContent value="hypotheses">
              <div className="space-y-4">
                {report.hypotheses.map((h) => (
                  <Card key={h.id} className="p-6">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <h2 className="flex gap-3 text-sm font-semibold leading-6">
                        <span className="text-primary/60">{h.id}</span>
                        {h.claim}
                      </h2>
                      <Status value={h.status} />
                    </div>
                    <p className="mt-4 text-sm leading-7 text-muted-foreground">{h.explanation}</p>
                    <div className="mt-5 flex flex-wrap gap-x-8 gap-y-3 text-xs">
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">Supports</span>
                        {h.supporting_evidence.length ? (
                          h.supporting_evidence.map((eid) => (
                            <button
                              key={eid}
                              className="evidence-chip"
                              onClick={() => showEvidence(eid)}
                            >
                              {eid}
                            </button>
                          ))
                        ) : (
                          <span className="text-muted-foreground">None collected</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">Challenges</span>
                        {h.contradicting_evidence.length ? (
                          h.contradicting_evidence.map((eid) => (
                            <button
                              key={eid}
                              className="evidence-chip"
                              onClick={() => showEvidence(eid)}
                            >
                              {eid}
                            </button>
                          ))
                        ) : (
                          <span className="text-muted-foreground">None collected</span>
                        )}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </TabsContent>
            <TabsContent value="evidence">
              <p className="mb-5 text-xs leading-6 text-muted-foreground">
                Calculations are reproducible from the original source versions. Document excerpts
                are attributed statements and may contain unverified claims.
              </p>
              <div className="space-y-4">
                {report.evidence.map((item) => (
                  <Card
                    id={`evidence-${item.id}`}
                    key={item.id}
                    className={cn(
                      'scroll-mt-6 p-5',
                      focusEvidence === item.id && 'ring-2 ring-primary/40',
                    )}
                  >
                    <div className="mb-3 flex items-center gap-3">
                      <span className="evidence-chip">{item.id}</span>
                      <Badge variant="secondary">{item.type}</Badge>
                    </div>
                    <p className="whitespace-pre-wrap text-sm leading-7">{item.claim}</p>
                    {item.calculation && (
                      <p className="mt-4 rounded-lg bg-muted px-3 py-2 font-mono text-[11px] leading-6 text-muted-foreground">
                        {item.calculation}
                      </p>
                    )}
                    <div className="mt-4 space-y-2">
                      {item.sources.map((s) => (
                        <button
                          key={s.id}
                          className="flex w-full items-start gap-2 text-left text-xs text-primary hover:underline"
                          onClick={() => setSource(s.id)}
                        >
                          <FileText size={14} className="mt-0.5 shrink-0" />
                          <span>
                            {s.name}
                            <span className="mt-1 block text-[11px] leading-5 text-muted-foreground">
                              {s.locator}
                            </span>
                          </span>
                          <ArrowRight size={12} className="ml-auto shrink-0" />
                        </button>
                      ))}
                    </div>
                  </Card>
                ))}
              </div>
            </TabsContent>
            <TabsContent value="trail">
              <TrailView trail={job.trail} running={false} />
            </TabsContent>
          </Tabs>
        </>
      ) : (
        <TrailView trail={job.trail} running={false} />
      )}
      <SourcePreview sourceId={source} onClose={() => setSource(null)} />
    </>
  )
}
