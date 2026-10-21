import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link2, Loader2, RefreshCw, Unlink } from 'lucide-react'
import { api, post } from '@/lib/api'
import type { Connection } from '@/lib/types'
import { dateTime } from '@/lib/utils'
import { schedules } from './ConnectSheet'
import { ErrorState, Status } from './shared'
import { Button } from './ui/button'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'

export function Connections({ onMessage }: { onMessage: (message: string) => void }) {
  const client = useQueryClient()
  const query = useQuery({
    queryKey: ['connections'],
    queryFn: () => api<Connection[]>('/connections'),
  })
  function refresh() {
    client.invalidateQueries({ queryKey: ['connections'] })
    client.invalidateQueries({ queryKey: ['sources'] })
    client.invalidateQueries({ queryKey: ['dashboard'] })
  }
  const sync = useMutation({
    mutationFn: (id: string) => post<Connection>(`/connections/${id}/sync`),
    onSuccess: (data) => {
      refresh()
      onMessage(
        data.last_status === 'error'
          ? `${data.name} could not sync: ${data.last_error}`
          : data.last_status === 'updated'
            ? `${data.name} changed, so a new version was imported.`
            : `${data.name} is already up to date.`,
      )
    },
  })
  const disconnect = useMutation({
    mutationFn: (id: string) => post(`/connections/${id}/delete`),
    onSuccess: () => {
      refresh()
      onMessage('Connection removed. Data it already imported stays in the evidence library.')
    },
  })
  if (query.error) return <ErrorState error={query.error} retry={() => query.refetch()} />
  if (!query.data?.length) return null
  const failure = sync.error ?? disconnect.error
  return (
    <Card className="mb-7">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Link2 size={17} />
          Live connections
        </CardTitle>
      </CardHeader>
      <CardContent>
        {failure && (
          <div className="mb-4">
            <ErrorState error={failure} />
          </div>
        )}
        <div className="table-scroll">
          <table className="source-table">
            <thead>
              <tr>
                <th>Connection</th>
                <th>Type</th>
                <th>Checks</th>
                <th>Last sync</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {query.data.map((item) => (
                <tr key={item.id}>
                  <td>
                    <p className="font-medium">{item.name}</p>
                    <p className="text-[11px] text-muted-foreground">Google Sheets</p>
                  </td>
                  <td className="capitalize">{item.kind}</td>
                  <td>
                    {schedules.find(([hours]) => hours === item.refresh_hours)?.[1] ??
                      `Every ${item.refresh_hours} h`}
                  </td>
                  <td>
                    <div className="flex flex-wrap items-center gap-2">
                      {item.last_status && <Status value={item.last_status} />}
                      <span className="text-[11px] text-muted-foreground">
                        {item.last_synced_at ? dateTime(item.last_synced_at) : 'Never'}
                      </span>
                    </div>
                    {item.last_status === 'error' && item.last_error && (
                      <p className="danger-on-card mt-1 max-w-xs text-[11px] leading-5 text-danger">
                        {item.last_error}
                      </p>
                    )}
                  </td>
                  <td>
                    <div className="flex justify-end gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={sync.isPending && sync.variables === item.id}
                        onClick={() => sync.mutate(item.id)}
                      >
                        {sync.isPending && sync.variables === item.id ? (
                          <Loader2 className="animate-spin" />
                        ) : (
                          <RefreshCw />
                        )}
                        Sync now
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="danger-on-card text-danger hover:text-danger"
                        disabled={disconnect.isPending}
                        onClick={() => disconnect.mutate(item.id)}
                        aria-label={`Disconnect ${item.name}`}
                        title="Disconnect (imported data stays)"
                      >
                        <Unlink />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}
