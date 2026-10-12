import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowRight, FileSearch, Loader2, Plus, Search, Sparkles } from 'lucide-react'
import { api, post } from '@/lib/api'
import type { Investigation } from '@/lib/types'
import { Empty, ErrorState, Loading, PageHeading, Status } from '@/components/shared'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { dateTime } from '@/lib/utils'

export default function Investigations() {
  const [params, setParams] = useSearchParams()
  const [question, setQuestion] = useState('')
  const [mode, setMode] = useState('question')
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const [offset, setOffset] = useState(0)
  const navigate = useNavigate()
  const client = useQueryClient()
  const query = useQuery({
    queryKey: ['investigations', offset],
    queryFn: () =>
      api<{ items: Investigation[]; total: number }>(`/investigations?offset=${offset}`),
    refetchInterval: (q) =>
      q.state.data?.items.some((job) => ['queued', 'running'].includes(job.status)) ? 2000 : false,
  })
  const create = useMutation({
    mutationFn: () =>
      post<Investigation>('/investigations', {
        question: mode === 'discover' ? 'Find what is going wrong with our business.' : question,
        mode,
      }),
    onSuccess: (job) => {
      client.invalidateQueries({ queryKey: ['investigations'] })
      client.invalidateQueries({ queryKey: ['dashboard'] })
      navigate(`/investigations/${job.id}`)
    },
  })
  const jobs =
    query.data?.items.filter(
      (job) =>
        (status === 'all' || job.status === status) &&
        job.question.toLowerCase().includes(search.toLowerCase()),
    ) ?? []
  function submit(event: FormEvent) {
    event.preventDefault()
    create.mutate()
  }
  return (
    <>
      <PageHeading
        eyebrow="FOLLOW THE EVIDENCE"
        title="Investigations"
        description="Every question, hypothesis, and discovery — with a complete trail."
        action={
          <Button onClick={() => setParams({ new: '1' })}>
            <Plus />
            New investigation
          </Button>
        }
      />
      <Card className="mb-6 flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="relative min-w-48 flex-1 max-w-sm">
          <Search size={16} className="absolute left-3 top-3 text-muted-foreground" />
          <label htmlFor="search-investigations" className="sr-only">
            Search this page of investigations
          </label>
          <input
            id="search-investigations"
            className="pl-9"
            placeholder="Search investigations on this page…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-1" aria-label="Filter investigation status">
          {['all', 'completed', 'running', 'failed'].map((value) => (
            <Button
              key={value}
              variant={status === value ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => setStatus(value)}
              className="capitalize"
            >
              {value}
            </Button>
          ))}
        </div>
      </Card>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => query.refetch()} />
      ) : jobs.length ? (
        <Card className="overflow-hidden">
          <div className="hidden grid-cols-[1fr_120px_130px_160px_24px] gap-4 border-b bg-muted/40 px-6 py-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground md:grid">
            <span>Investigation</span>
            <span>Status</span>
            <span>Confidence</span>
            <span>Created</span>
            <span />
          </div>
          {jobs.map((job) => (
            <Link key={job.id} to={`/investigations/${job.id}`} className="investigation-row">
              <div className="flex min-w-0 items-center gap-3">
                <span className="rounded-lg bg-primary/5 p-2 text-primary">
                  <FileSearch size={18} />
                </span>
                <div className="min-w-0">
                  <h2 className="truncate text-sm font-medium">{job.question}</h2>
                  <p className="mt-1 text-[10px] capitalize text-muted-foreground">
                    {job.mode} · {job.id.slice(0, 8)}
                    {job.engine === 'deterministic' ? ' · Deterministic analysis' : ''}
                  </p>
                </div>
              </div>
              <Status value={job.status} />
              <span className="text-xs capitalize text-muted-foreground">
                {job.confidence || 'Pending'}
                {job.confidence ? ' evidence strength' : ''}
              </span>
              <span className="text-[11px] text-muted-foreground">{dateTime(job.created_at)}</span>
              <ArrowRight size={15} className="text-muted-foreground" />
            </Link>
          ))}
        </Card>
      ) : (
        <Empty
          title={
            search || status !== 'all' ? 'No matching investigations' : 'Start with a question'
          }
          description="Ask why a metric changed, or let SanketAI discover which business signal needs attention."
          action={
            <Button onClick={() => setParams({ new: '1' })}>
              <Sparkles />
              Start investigating
            </Button>
          }
        />
      )}
      {query.data && query.data.total > 50 && (
        <div className="mt-5 flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {offset + 1}–{Math.min(offset + 50, query.data.total)} of {query.data.total}
          </span>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={!offset}
              onClick={() => setOffset(Math.max(0, offset - 50))}
            >
              Previous
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={offset + 50 >= query.data.total}
              onClick={() => setOffset(offset + 50)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
      <Dialog open={params.has('new')} onOpenChange={(open) => setParams(open ? { new: '1' } : {})}>
        <DialogContent>
          <DialogTitle className="text-xl font-semibold">What should we investigate?</DialogTitle>
          <DialogDescription className="text-sm leading-6 text-muted-foreground">
            The investigator uses a snapshot of your connected evidence. Every tool call and source
            will be recorded.
          </DialogDescription>
          <form onSubmit={submit} className="space-y-5">
            <fieldset className="grid grid-cols-2 gap-3">
              <legend className="sr-only">Investigation mode</legend>
              {[
                ['question', 'Ask a question', 'Start with a known problem.'],
                ['discover', 'Find what is wrong', 'Let the agent inspect business signals.'],
              ].map(([value, title, description]) => (
                <label key={value} className={`mode-option ${mode === value ? 'selected' : ''}`}>
                  <input
                    className="sr-only"
                    type="radio"
                    name="mode"
                    value={value}
                    checked={mode === value}
                    onChange={() => setMode(value)}
                  />
                  <span className="text-sm font-semibold">{title}</span>
                  <span className="mt-2 block text-xs font-normal leading-5 text-muted-foreground">
                    {description}
                  </span>
                </label>
              ))}
            </fieldset>
            {mode === 'question' && (
              <div>
                <label htmlFor="investigation-question">Business question</label>
                <textarea
                  id="investigation-question"
                  rows={4}
                  placeholder="Why did our sales drop in the latest month?"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  minLength={8}
                  maxLength={2000}
                  required
                  autoFocus
                />
              </div>
            )}
            {create.error && <ErrorState error={create.error} />}
            <Button
              className="w-full"
              type="submit"
              disabled={create.isPending || (mode === 'question' && question.trim().length < 8)}
            >
              {create.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />}Start
              investigation
              <ArrowRight />
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
