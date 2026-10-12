import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Clock3, ShieldCheck } from 'lucide-react'
import { api } from '@/lib/api'
import type { Action } from '@/lib/types'
import { Empty, ErrorState, Loading, PageHeading } from '@/components/shared'
import { ActionCard } from '@/components/ActionCard'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

export default function Actions() {
  const [filter, setFilter] = useState('all')
  const query = useQuery({ queryKey: ['actions'], queryFn: () => api<Action[]>('/actions') })
  const counts = {
    pending: query.data?.filter((a) => a.status === 'pending').length || 0,
    monitoring: query.data?.filter((a) => a.status === 'monitoring').length || 0,
    succeeded: query.data?.filter((a) => a.status === 'succeeded').length || 0,
  }
  const actions = query.data?.filter((a) => filter === 'all' || a.status === filter) || []
  return (
    <>
      <PageHeading
        eyebrow="TURN INSIGHT INTO PROGRESS"
        title="Actions & monitoring"
        description="Review the recommendation, approve an internal task, and follow the result."
      />
      <div className="mb-7 grid gap-4 sm:grid-cols-3">
        {[
          [ShieldCheck, 'Awaiting approval', counts.pending],
          [Clock3, 'Monitoring a KPI', counts.monitoring],
          [CheckCircle2, 'Target achieved', counts.succeeded],
        ].map(([Icon, label, count]) => {
          const Symbol = Icon as typeof ShieldCheck
          return (
            <Card key={String(label)} className="flex items-center gap-4 p-5">
              <span className="rounded-xl bg-primary/5 p-3 text-primary">
                <Symbol size={21} />
              </span>
              <div>
                <p className="text-xs text-muted-foreground">{String(label)}</p>
                <p className="mt-2 text-2xl font-semibold">{String(count)}</p>
              </div>
            </Card>
          )
        })}
      </div>
      <div className="mb-6 flex flex-wrap gap-2" aria-label="Filter actions">
        {['all', 'pending', 'monitoring', 'succeeded', 'failed', 'rejected'].map((value) => (
          <Button
            size="sm"
            key={value}
            variant={filter === value ? 'secondary' : 'ghost'}
            className="capitalize"
            onClick={() => setFilter(value)}
          >
            {value === 'pending' ? 'Awaiting approval' : value}
          </Button>
        ))}
      </div>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => query.refetch()} />
      ) : actions.length ? (
        <div className="grid items-start gap-5 xl:grid-cols-2">
          {actions.map((action) => (
            <ActionCard key={action.id} action={action} />
          ))}
        </div>
      ) : (
        <Empty
          title="No actions in this view"
          description="Completed investigations with sufficient evidence can propose an internal task. You review its scope and approve it before monitoring begins."
          action={
            <Button asChild variant="outline">
              <Link to="/investigations">
                View investigations
                <ArrowRight />
              </Link>
            </Button>
          }
        />
      )}
      <p className="mt-6 text-xs leading-6 text-muted-foreground">
        The worker checks approved tasks when their follow-up is due. You can also select “Check
        outcome” at any time. Missing outcome data defers the scheduled check by one day. External
        notifications, CRM updates, and third-party workflows require a connector and are not
        configured in this phase.
      </p>
    </>
  )
}
