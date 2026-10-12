import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ArrowRight, Check, Clock3, Loader2, RefreshCw, ShieldCheck, X } from 'lucide-react'
import { post } from '@/lib/api'
import type { Action } from '@/lib/types'
import { dateTime } from '@/lib/utils'
import { ErrorState, MetricValue, Status } from './shared'
import { Button } from './ui/button'
import { Card } from './ui/card'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from './ui/dialog'

export function ActionCard({ action }: { action: Action }) {
  const [confirm, setConfirm] = useState(false)
  const client = useQueryClient()
  const mutation = useMutation({
    mutationFn: (decision: string) => post<Action>(`/actions/${action.id}/decision`, { decision }),
    onSuccess: () => {
      setConfirm(false)
      refresh()
    },
  })
  const monitor = useMutation({
    mutationFn: () => post<Action>(`/actions/${action.id}/monitor`),
    onSuccess: refresh,
  })
  function refresh() {
    client.invalidateQueries({ queryKey: ['actions'] })
    client.invalidateQueries({ queryKey: ['investigation', action.investigation_id] })
    client.invalidateQueries({ queryKey: ['dashboard'] })
  }
  return (
    <Card className="p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <ShieldCheck size={15} />
          Internal operations task
        </div>
        <Status value={action.status} />
      </div>
      <h3 className="mt-4 text-base font-semibold leading-7">{action.title}</h3>
      <div className="mt-5 grid grid-cols-3 gap-3 rounded-lg bg-muted/70 p-4 text-xs">
        <div>
          <p className="text-[10px] text-muted-foreground">MONITORED KPI</p>
          <p className="mt-2 font-medium">
            {action.metric === 'late_rate' ? 'Late delivery rate' : 'Recognized revenue'}
          </p>
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground">BASELINE</p>
          <p className="mt-2 font-medium">
            <MetricValue value={action.baseline} metric={action.metric} />
          </p>
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground">TARGET</p>
          <p className="mt-2 font-medium">
            {action.direction === 'up' ? '≥ ' : '≤ '}
            <MetricValue value={action.target} metric={action.metric} />
          </p>
        </div>
      </div>
      <p className="mt-4 text-xs leading-5 text-muted-foreground">
        Owner: {action.owner}
        {action.due_at
          ? ` · Follow-up due ${dateTime(action.due_at)}`
          : ' · Follow-up scheduled 7 days after approval'}
      </p>
      {action.outcome && (
        <div className="mt-4 rounded-lg border p-4 text-xs leading-6">
          <p className="font-semibold">
            Outcome: <MetricValue value={action.outcome.value} metric={action.metric} />
          </p>
          <p className="text-muted-foreground">{action.outcome.note}</p>
          {action.outcome.followup_investigation_id && (
            <Link
              className="mt-2 inline-flex items-center gap-2 font-semibold text-primary"
              to={`/investigations/${action.outcome.followup_investigation_id}`}
            >
              Open follow-up investigation
              <ArrowRight size={13} />
            </Link>
          )}
        </div>
      )}
      <div className="mt-5 flex flex-wrap items-center gap-2">
        {action.status === 'pending' && (
          <>
            <Button size="sm" onClick={() => setConfirm(true)} disabled={mutation.isPending}>
              <Check />
              Review & approve
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => mutation.mutate('reject')}
              disabled={mutation.isPending}
            >
              <X />
              Reject
            </Button>
          </>
        )}
        {action.status === 'monitoring' && (
          <Button
            variant="outline"
            size="sm"
            disabled={monitor.isPending}
            onClick={() => monitor.mutate()}
          >
            {monitor.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />}Check outcome
          </Button>
        )}
        <Link
          to={`/investigations/${action.investigation_id}`}
          className="ml-auto text-xs font-medium text-primary"
        >
          View investigation
          <ArrowRight size={12} className="ml-1 inline" />
        </Link>
      </div>
      {action.status === 'monitoring' && (
        <p className="mt-3 flex items-start gap-2 text-[11px] leading-5 text-muted-foreground">
          <Clock3 size={13} className="mt-0.5 shrink-0" />
          Upload a complete newer 28-day outcome period before checking. A missed KPI target starts
          a follow-up investigation.
        </p>
      )}
      {!confirm && mutation.error && (
        <div className="mt-4">
          <ErrorState error={mutation.error} />
        </div>
      )}
      {monitor.error && (
        <div className="mt-4">
          <ErrorState error={monitor.error} />
        </div>
      )}
      <Dialog open={confirm} onOpenChange={setConfirm}>
        <DialogContent>
          <DialogTitle className="text-xl font-semibold">Approve this operations task?</DialogTitle>
          <DialogDescription className="text-sm leading-6 text-muted-foreground">
            Your approval creates an internal task for Operations and schedules a KPI follow-up. The
            team carries out the business change.
          </DialogDescription>
          <div className="rounded-xl border bg-muted/40 p-5">
            <p className="text-sm font-semibold leading-6">{action.title}</p>
            <p className="mt-4 text-xs text-muted-foreground">
              KPI target: {action.direction === 'up' ? 'at least ' : 'at most '}
              <MetricValue metric={action.metric} value={action.target} /> · Follow-up: 7 days
            </p>
          </div>
          <p className="text-xs leading-6 text-muted-foreground">
            This approval is recorded in the audit trail. If a newer outcome period misses the
            target, SanketAI creates a follow-up investigation.
          </p>
          {mutation.error && <ErrorState error={mutation.error} />}
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setConfirm(false)}>
              Cancel
            </Button>
            <Button disabled={mutation.isPending} onClick={() => mutation.mutate('approve')}>
              {mutation.isPending ? <Loader2 className="animate-spin" /> : <Check />}Approve &
              create task
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
