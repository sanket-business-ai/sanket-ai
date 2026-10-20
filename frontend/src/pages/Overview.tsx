import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  Database,
  FileSearch,
  Lightbulb,
  Loader2,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingDown,
} from 'lucide-react'
import { api, post } from '@/lib/api'
import type { Dashboard, DemoPack, Investigation, System } from '@/lib/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Brand,
  Empty,
  ErrorState,
  Loading,
  MetricCard,
  PageHeading,
  Status,
} from '@/components/shared'
import { currency, dateTime } from '@/lib/utils'

const discover = 'Find what is going wrong'
const suggestions = [
  'Why did sales drop?',
  'Why is our margin falling?',
  'Why are deliveries late?',
  discover,
]
export default function Overview() {
  const navigate = useNavigate()
  const client = useQueryClient()
  const [question, setQuestion] = useState('')
  const dashboard = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api<Dashboard>('/dashboard'),
  })
  const system = useQuery({ queryKey: ['system'], queryFn: () => api<System>('/system') })
  const create = useMutation({
    mutationFn: (input: { question: string; mode: string }) =>
      post<Investigation>('/investigations', input),
    onSuccess: (job) => {
      client.invalidateQueries({ queryKey: ['investigations'] })
      navigate(`/investigations/${job.id}`)
    },
  })
  const demo = useMutation({
    mutationFn: (pack: DemoPack) => post('/demo', { pack }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['dashboard'] })
      client.invalidateQueries({ queryKey: ['sources'] })
    },
  })
  function start(event: FormEvent) {
    event.preventDefault()
    if (question.trim().length >= 8) create.mutate({ question, mode: 'question' })
  }
  if (dashboard.isPending) return <Loading />
  if (dashboard.error)
    return <ErrorState error={dashboard.error} retry={() => dashboard.refetch()} />
  const data = dashboard.data
  const anomalies = data.metrics.filter((m) => m.anomaly)
  return (
    <>
      <PageHeading
        eyebrow="THE BIG PICTURE"
        title="Your business, understood."
        description="See the signals. Ask the questions. Get to the root cause."
        action={
          <Badge variant="outline" className="bg-card py-2.5 px-3">
            <span className="size-1.5 rounded-full bg-primary" />
            {data.period
              ? `${data.period.current_start} — ${data.period.current_end}`
              : 'No data connected'}
          </Badge>
        }
      />
      <section className="investigate-hero">
        <div className="hero-copy">
          <Badge className="mb-5 border-mint/20 bg-mint/10 text-mint">
            <Sparkles size={12} />
            FROM SIGNAL TO ANSWER
          </Badge>
          <h2>
            Something changed.
            <br />
            <span>Let’s find out why.</span>
          </h2>
          <p>
            Connect the dots across your orders, inventory, suppliers,
            <br className="hidden xl:block" /> and reports. Get an explanation you can act on.
          </p>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="signal-node signal-top">
            <Database size={18} />
            <span>Business data</span>
          </div>
          <div className="signal-core">
            <Brand compact />
          </div>
          <div className="signal-node signal-bottom">
            <ShieldCheck size={18} />
            <span>Evidence-backed insight</span>
            <Check size={12} />
          </div>
          <i className="signal-dot dot-one" />
          <i className="signal-dot dot-two" />
        </div>
        <form className="question-form" onSubmit={start}>
          <Search size={19} className="shrink-0 text-primary/60" />
          <label htmlFor="business-question" className="sr-only">
            Ask a business question
          </label>
          <input
            id="business-question"
            placeholder="Ask anything about your business…"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            minLength={8}
            maxLength={2000}
            required
          />
          <Button
            variant="accent"
            type="submit"
            disabled={create.isPending || !data.source_count || question.trim().length < 8}
          >
            {create.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />}
            <span className="hidden sm:inline">Investigate</span>
            <ArrowRight />
          </Button>
        </form>
        <div className="suggestion-row">
          <span>Try asking</span>
          {suggestions.map((text) => (
            <button
              key={text}
              disabled={!data.source_count || create.isPending}
              onClick={() =>
                text === discover
                  ? create.mutate({
                      question: 'Find what is going wrong with our business.',
                      mode: 'discover',
                    })
                  : setQuestion(text)
              }
            >
              {text}
              <ArrowUpRight size={11} />
            </button>
          ))}
        </div>
      </section>
      {create.error && (
        <div className="mt-4">
          <ErrorState error={create.error} />
        </div>
      )}
      {!data.source_count ? (
        <div className="mt-7">
          <Empty
            title="Give your investigator some evidence"
            description="Connect business files to get started, or explore a complete investigation with HimalayanMart, a fictional Nepalese business."
            action={
              <div className="flex flex-wrap justify-center gap-3">
                <Button asChild>
                  <Link to="/sources">
                    <Database />
                    Connect data
                  </Link>
                </Button>
                {system.data?.demo_enabled && (
                  <>
                    <Button
                      variant="outline"
                      disabled={demo.isPending}
                      onClick={() => demo.mutate('supply')}
                    >
                      {demo.isPending && demo.variables === 'supply' ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <Sparkles />
                      )}
                      Load demo evidence
                    </Button>
                    <Button
                      variant="outline"
                      disabled={demo.isPending}
                      onClick={() => demo.mutate('margin')}
                    >
                      {demo.isPending && demo.variables === 'margin' ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <Sparkles />
                      )}
                      Load margin demo
                    </Button>
                  </>
                )}
              </div>
            }
          />
          {demo.error && (
            <div className="mt-4">
              <ErrorState error={demo.error} />
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="section-heading">
            <h2>
              Business pulse{' '}
              <span className="ml-2 text-[11px] font-normal text-muted-foreground">
                Latest 28 days
              </span>
            </h2>
            <Link to="/sources">
              {data.source_count} connected sources
              <ChevronRight size={13} />
            </Link>
          </div>
          <section className="metric-grid">
            {data.metrics.map((metric) => (
              <MetricCard key={metric.key} metric={metric} />
            ))}
          </section>
          {data.coverage_issues.length > 0 && (
            <div className="mt-4 rounded-lg border border-warning/20 bg-warning-bg px-4 py-3 text-xs leading-5 text-warning">
              Data coverage: {data.coverage_issues.join(' ')}{' '}
              <Link to="/sources" className="font-semibold underline">
                Review sources
              </Link>
            </div>
          )}
          <section className="overview-grid">
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <span className="rounded-md bg-warning-bg p-1.5 text-warning">
                    <Lightbulb size={16} />
                  </span>
                  Signals worth investigating
                </CardTitle>
                <Badge variant="warning">{anomalies.length} signals</Badge>
              </CardHeader>
              <CardContent>
                {anomalies.length ? (
                  <div className="space-y-3">
                    {anomalies.map((metric) => (
                      <div className="signal-row" key={metric.key}>
                        <span className="signal-icon">
                          <TrendingDown size={17} />
                        </span>
                        <div className="min-w-0 flex-1">
                          <h3 className="text-xs font-semibold">
                            {metric.label} {metric.direction === 'up' ? 'declined' : 'increased'}
                          </h3>
                          <p className="mt-1.5 text-[11px] leading-5 text-muted-foreground">
                            {metric.unit === 'NPR'
                              ? currency(metric.current)
                              : `${metric.current}${metric.unit === '%' ? '%' : ''}`}{' '}
                            · {Math.abs(metric.change ?? 0).toFixed(1)}
                            {metric.unit === '%' ? ' percentage points' : '%'} from baseline
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label={`Investigate ${metric.label}`}
                          disabled={create.isPending}
                          onClick={() =>
                            create.mutate({
                              question: `Why did ${metric.label.toLowerCase()} change in the latest 28 days?`,
                              mode: 'question',
                            })
                          }
                        >
                          <ArrowUpRight />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="py-8 text-center text-sm text-muted-foreground">
                    No changes crossed the current signal thresholds.
                  </p>
                )}
                <div className="mt-5 border-t pt-4">
                  <button
                    className="flex w-full items-center justify-center gap-2 text-xs font-semibold text-primary"
                    disabled={create.isPending}
                    onClick={() =>
                      create.mutate({
                        question: 'Find what is going wrong with our business.',
                        mode: 'discover',
                      })
                    }
                  >
                    <Sparkles size={14} />
                    Let SanketAI prioritize an investigation
                    <ArrowRight size={13} />
                  </button>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>Recent investigations</CardTitle>
                <Link className="text-xs text-primary" to="/investigations">
                  View all
                  <ArrowUpRight size={12} className="ml-1 inline" />
                </Link>
              </CardHeader>
              <CardContent>
                {data.recent.length ? (
                  <div className="divide-y">
                    {data.recent.slice(0, 4).map((job) => (
                      <Link
                        className="recent-investigation"
                        to={`/investigations/${job.id}`}
                        key={job.id}
                      >
                        <span className="rounded-lg bg-muted p-2.5 text-primary">
                          <FileSearch size={17} />
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-xs font-medium">{job.question}</p>
                          <p className="mt-2 text-[11px] text-muted-foreground">
                            {dateTime(job.created_at)}
                          </p>
                        </div>
                        <Status value={job.status} />
                      </Link>
                    ))}
                  </div>
                ) : (
                  <div className="py-9 text-center">
                    <FileSearch size={25} className="mx-auto mb-3 text-primary/40" />
                    <p className="text-sm font-medium">Your first discovery awaits</p>
                    <p className="mt-2 text-xs text-muted-foreground">
                      Ask a question above to start an investigation.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </section>
          <section className="trust-strip">
            <div className="flex items-center gap-3">
              <ShieldCheck className="text-primary" size={22} />
              <div>
                <h3>Evidence first. Decisions stay yours.</h3>
                <p>Every conclusion is traceable. Every action needs your approval.</p>
              </div>
            </div>
            <Link to="/actions">
              {data.pending_actions
                ? `${data.pending_actions} awaiting approval`
                : 'Review actions'}
              <ArrowRight size={14} />
            </Link>
          </section>
        </>
      )}
    </>
  )
}
