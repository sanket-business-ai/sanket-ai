import type { MarginBridge } from '@/lib/types'
import { cn, currency, number } from '@/lib/utils'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface Row {
  key: string
  label: string
  from: number
  to: number
  kind: 'total' | 'up' | 'down' | 'flat'
  detail: string
  evidenceId?: string
}

const signed = (value: number) =>
  value === 0 ? 'No change' : `${value < 0 ? '−' : '+'}NPR ${number(Math.abs(value))}`

// Baseline contribution, then each step's effect on it, then current contribution.
function rows(bridge: MarginBridge): Row[] {
  const start = bridge.previous ?? 0
  const result: Row[] = [
    {
      key: 'previous',
      label: 'Baseline contribution',
      from: 0,
      to: start,
      kind: 'total',
      detail: currency(start),
    },
  ]
  let running = start
  for (const step of bridge.steps ?? []) {
    result.push({
      key: step.key,
      label: step.label,
      from: running,
      to: running + step.effect,
      kind: step.effect < 0 ? 'down' : step.effect > 0 ? 'up' : 'flat',
      detail: `${currency(step.previous)} → ${currency(step.current)}${
        step.change === null ? '' : ` (${step.change > 0 ? '+' : ''}${step.change.toFixed(1)}%)`
      }`,
      evidenceId: step.evidence_id,
    })
    running += step.effect
  }
  result.push({
    key: 'current',
    label: 'Current contribution',
    from: 0,
    to: bridge.current ?? running,
    kind: 'total',
    detail: currency(bridge.current ?? running),
  })
  return result
}

export function MarginWaterfall({
  bridge,
  onEvidence,
}: {
  bridge: MarginBridge
  onEvidence: (id: string) => void
}) {
  const data = rows(bridge)
  const low = Math.min(0, ...data.flatMap((r) => [r.from, r.to]))
  const high = Math.max(...data.flatMap((r) => [r.from, r.to]))
  const span = high - low || 1
  const at = (value: number) => ((value - low) / span) * 100
  const rate = bridge.margin_rate
  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle>Where the margin went</CardTitle>
        <p className="mt-2 text-xs leading-5 text-muted-foreground">
          How each recorded line moved contribution from the baseline to the current period
          {rate?.previous != null && rate.current != null && (
            <>
              {' '}
              · margin {rate.previous.toFixed(1)}% → {rate.current.toFixed(1)}%
            </>
          )}
        </p>
      </CardHeader>
      <CardContent>
        <ol className="space-y-3" aria-label="Contribution bridge">
          {data.map((row) => {
            const effect = row.to - row.from
            return (
              <li
                key={row.key}
                className="grid grid-cols-1 gap-x-4 gap-y-1.5 sm:grid-cols-[minmax(0,13rem)_minmax(0,1fr)]"
              >
                <div className="flex items-baseline justify-between gap-3 sm:block">
                  <p className={cn('text-sm', row.kind === 'total' && 'font-medium')}>
                    {row.label}
                  </p>
                  <p
                    className={cn(
                      'text-xs tabular-nums sm:mt-0.5',
                      row.kind === 'total' ? 'font-semibold' : 'text-muted-foreground',
                    )}
                  >
                    {row.kind === 'total' ? currency(row.to) : signed(effect)}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <div
                    className="relative h-6 flex-1 rounded-sm bg-muted/60"
                    title={`${row.label}: ${row.detail}`}
                  >
                    {low < 0 && (
                      <span
                        className="absolute inset-y-0 w-px bg-border"
                        style={{ left: `${at(0)}%` }}
                      />
                    )}
                    {row.kind !== 'flat' && (
                      <span
                        className="absolute inset-y-0 rounded-sm"
                        style={{
                          left: `${at(Math.min(row.from, row.to))}%`,
                          width: `max(2px, ${Math.abs(at(row.to) - at(row.from))}%)`,
                          background:
                            row.kind === 'total'
                              ? 'var(--text-secondary)'
                              : row.kind === 'up'
                                ? 'var(--chart-2)'
                                : 'var(--chart-6)',
                        }}
                      />
                    )}
                  </div>
                  {row.evidenceId ? (
                    <button
                      className="evidence-chip w-12 shrink-0"
                      onClick={() => onEvidence(row.evidenceId!)}
                      aria-label={`Evidence ${row.evidenceId}: ${row.label}, ${row.detail}`}
                    >
                      {row.evidenceId}
                    </button>
                  ) : (
                    <span className="w-12 shrink-0" />
                  )}
                </div>
              </li>
            )
          })}
        </ol>
        <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground">
          <span className="flex items-center gap-2">
            <span className="size-2.5 rounded-sm" style={{ background: 'var(--chart-2)' }} />
            Raised contribution
          </span>
          <span className="flex items-center gap-2">
            <span className="size-2.5 rounded-sm" style={{ background: 'var(--chart-6)' }} />
            Lowered contribution
          </span>
          <span className="flex items-center gap-2">
            <span className="size-2.5 rounded-sm" style={{ background: 'var(--text-secondary)' }} />
            Contribution total
          </span>
        </div>
        <details className="mt-4">
          <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
            Show as a table
          </summary>
          <table className="mt-3 w-full text-left text-xs tabular-nums">
            <thead className="text-muted-foreground">
              <tr>
                <th className="py-1.5 pr-3 font-medium">Line</th>
                <th className="py-1.5 pr-3 font-medium">Baseline</th>
                <th className="py-1.5 pr-3 font-medium">Current</th>
                <th className="py-1.5 font-medium">Effect on contribution</th>
              </tr>
            </thead>
            <tbody>
              {(bridge.steps ?? []).map((step) => (
                <tr key={step.key} className="border-t">
                  <td className="py-1.5 pr-3">{step.label}</td>
                  <td className="py-1.5 pr-3">{currency(step.previous)}</td>
                  <td className="py-1.5 pr-3">{currency(step.current)}</td>
                  <td className="py-1.5">{signed(step.effect)}</td>
                </tr>
              ))}
              <tr className="border-t font-semibold">
                <td className="py-1.5 pr-3">Contribution</td>
                <td className="py-1.5 pr-3">{currency(bridge.previous ?? 0)}</td>
                <td className="py-1.5 pr-3">{currency(bridge.current ?? 0)}</td>
                <td className="py-1.5">{signed(bridge.change ?? 0)}</td>
              </tr>
            </tbody>
          </table>
        </details>
        <p className="mt-4 text-xs leading-6 text-muted-foreground">{bridge.limitation}</p>
      </CardContent>
    </Card>
  )
}
