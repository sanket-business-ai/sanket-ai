import type { ReactNode } from 'react'
import {
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  FileSearch,
  Loader2,
  RefreshCw,
} from 'lucide-react'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Card } from './ui/card'
import { cn, currency, number } from '@/lib/utils'
import type { Metric } from '@/lib/types'

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className="brand" aria-label="Sanket AI">
      <svg className="brand-mark" viewBox="0 0 256 256" aria-hidden="true">
        <path
          fill="currentColor"
          d="M224 24H100a76 76 0 0 0 0 152h28v-48h-28a28 28 0 0 1 0-56h124Z M32 232h124a76 76 0 0 0 0-152h-28v48h28a28 28 0 0 1 0 56H32Z"
        />
      </svg>
      {!compact && (
        <span className="brand-wordmark">
          sanket<span>AI</span>
        </span>
      )}
    </span>
  )
}
export function Loading({ label = 'Loading workspace…' }: { label?: string }) {
  return (
    <div
      role="status"
      className="flex min-h-48 items-center justify-center gap-3 text-sm text-muted-foreground"
    >
      <Loader2 className="size-5 animate-spin" />
      {label}
    </div>
  )
}
export function ErrorState({ error, retry }: { error: Error; retry?: () => void }) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-danger/20 bg-danger-bg p-5 text-sm text-danger"
    >
      <div className="flex items-center gap-2 font-semibold">
        <AlertCircle size={17} />
        Something needs attention
      </div>
      <p className="mt-2">{error.message}</p>
      {retry && (
        <Button variant="outline" size="sm" onClick={retry} className="mt-4">
          <RefreshCw />
          Try again
        </Button>
      )}
    </div>
  )
}
export function Empty({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <Card className="flex flex-col items-center px-6 py-14 text-center">
      <div className="mb-4 rounded-2xl bg-muted p-4 text-primary">
        <FileSearch size={28} />
      </div>
      <h2 className="font-semibold">{title}</h2>
      <p className="my-3 max-w-md text-sm leading-6 text-muted-foreground">{description}</p>
      {action}
    </Card>
  )
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
      {action}
    </div>
  )
}
export function Status({ value }: { value: string }) {
  const good = ['completed', 'succeeded', 'supported', 'monitoring'].includes(value)
  const bad = ['failed', 'rejected'].includes(value)
  return (
    <Badge
      variant={
        good
          ? 'default'
          : bad
            ? 'destructive'
            : ['pending', 'inconclusive'].includes(value)
              ? 'warning'
              : 'secondary'
      }
    >
      {['running', 'queued'].includes(value) ? (
        <Loader2 size={11} className={value === 'running' ? 'animate-spin' : ''} />
      ) : good ? (
        <CheckCircle2 size={11} />
      ) : (
        <span className="size-1.5 rounded-full bg-current" />
      )}
      {value.replaceAll('_', ' ')}
    </Badge>
  )
}
export function MetricCard({ metric }: { metric: Metric }) {
  const positive = (metric.change ?? 0) >= 0
  const good = metric.direction === 'up' ? positive : !positive
  const Arrow = positive ? ArrowUpRight : ArrowDownRight
  return (
    <Card className="metric-card">
      <p className="text-xs font-medium text-muted-foreground">{metric.label}</p>
      <div className="mt-4 flex items-end justify-between gap-2">
        <p className="metric-number">
          {metric.unit === 'NPR' ? (
            <>
              <span className="mr-1.5 text-[11px] font-medium text-muted-foreground">NPR</span>
              {number(metric.current)}
            </>
          ) : (
            `${number(metric.current, 1)}${metric.unit === '%' ? '%' : ''}`
          )}
        </p>
        <div
          className={cn(
            'rounded-md p-2',
            metric.anomaly ? 'bg-warning-bg text-warning' : 'bg-secondary text-primary',
          )}
        >
          <Arrow size={19} />
        </div>
      </div>
      <p className="metric-comparison">
        <span
          className={cn(
            'inline-flex items-center gap-0.5 font-semibold',
            good ? 'text-success' : 'text-danger',
          )}
        >
          {metric.change === null ? (
            'No baseline'
          ) : (
            <>
              <Arrow size={12} />
              {Math.abs(metric.change).toFixed(1)}
              {metric.unit === '%' ? ' pp' : '%'}
            </>
          )}
        </span>
        <span className="text-muted-foreground">vs previous 28 days</span>
      </p>
    </Card>
  )
}
export function MetricValue({ value, metric }: { value: number; metric: string }) {
  return <>{metric === 'late_rate' ? `${number(value, 1)}%` : currency(value)}</>
}
