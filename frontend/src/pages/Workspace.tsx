import { useQuery } from '@tanstack/react-query'
import { Cpu, Database, FileCheck2, LockKeyhole, ShieldCheck } from 'lucide-react'
import { api } from '@/lib/api'
import type { AuditEvent, System } from '@/lib/types'
import { dateTime } from '@/lib/utils'
import { ErrorState, Loading, PageHeading } from '@/components/shared'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export default function Workspace() {
  const system = useQuery({ queryKey: ['system'], queryFn: () => api<System>('/system') })
  const audit = useQuery({ queryKey: ['audit'], queryFn: () => api<AuditEvent[]>('/audit') })
  return (
    <>
      <PageHeading
        eyebrow="A FOUNDATION YOU CAN TRUST"
        title="Workspace & audit"
        description="Inspect runtime configuration and review the decisions made in your workspace."
      />
      <div className="mb-7 grid gap-5 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu size={17} />
              Investigation runtime
            </CardTitle>
          </CardHeader>
          <CardContent>
            {system.isPending ? (
              <Loading />
            ) : system.error ? (
              <ErrorState error={system.error} />
            ) : (
              <dl className="settings-list">
                <div>
                  <dt>Agent mode</dt>
                  <dd className="capitalize">{system.data.agent_mode}</dd>
                </div>
                <div>
                  <dt>
                    {system.data.llm_provider === 'openai'
                      ? 'Configured hosted model'
                      : 'Configured local model'}
                  </dt>
                  <dd>{system.data.model}</dd>
                </div>
                <div>
                  <dt>Background worker</dt>
                  <dd>
                    <Badge variant={system.data.worker_online ? 'default' : 'warning'}>
                      {system.data.worker_online ? 'Connected' : 'Not connected'}
                    </Badge>
                  </dd>
                </div>
                <div>
                  <dt>Demo evidence</dt>
                  <dd>{system.data.demo_enabled ? 'Available in empty workspaces' : 'Disabled'}</dd>
                </div>
                <div>
                  <dt>Upload limit</dt>
                  <dd>{system.data.upload_max_bytes / 1024 / 1024} MB per file</dd>
                </div>
              </dl>
            )}
            <p className="mt-5 text-xs leading-6 text-muted-foreground">
              Runtime settings come from server environment variables. In auto mode, unavailable
              model reasoning falls back to explicitly labeled deterministic analysis.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck size={17} />
              Workspace safeguards
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-5">
              {[
                [
                  LockKeyhole,
                  'Authenticated access',
                  'HTTP-only sessions, CSRF checks, and recorded approvals.',
                ],
                [
                  Database,
                  'Preserved evidence',
                  'Investigations keep immutable source IDs and deterministic calculations.',
                ],
                [
                  FileCheck2,
                  'Reviewable reasoning',
                  'Competing hypotheses, counter-evidence, confidence limits, and explicit unknowns.',
                ],
              ].map(([Icon, title, text]) => {
                const Symbol = Icon as typeof ShieldCheck
                return (
                  <div key={String(title)} className="flex gap-3">
                    <Symbol className="mt-0.5 shrink-0 text-primary" size={17} />
                    <div>
                      <h3 className="text-xs font-semibold">{String(title)}</h3>
                      <p className="mt-1 text-xs leading-6 text-muted-foreground">{String(text)}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Audit trail</CardTitle>
          <p className="mt-2 text-xs text-muted-foreground">
            The latest 100 workspace events. Source uploads, investigation creation, and action
            decisions are recorded.
          </p>
        </CardHeader>
        <CardContent>
          {audit.isPending ? (
            <Loading />
          ) : audit.error ? (
            <ErrorState error={audit.error} retry={() => audit.refetch()} />
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Event</th>
                    <th>Actor ID</th>
                    <th>Time</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.data?.map((event) => (
                    <tr key={event.id}>
                      <td>
                        <span className="font-medium">{event.event.replaceAll('.', ' · ')}</span>
                      </td>
                      <td className="font-mono text-[11px]">{event.actor.slice(0, 8)}</td>
                      <td>{dateTime(event.created_at)}</td>
                      <td>
                        <details>
                          <summary className="cursor-pointer text-primary">Inspect</summary>
                          <pre className="mt-2 max-w-sm overflow-auto rounded-lg bg-muted p-3 text-[11px]">
                            {JSON.stringify(event.details, null, 2)}
                          </pre>
                        </details>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </>
  )
}
