import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link2, Loader2 } from 'lucide-react'
import { api, post } from '@/lib/api'
import type { Connection, Contracts } from '@/lib/types'
import { ErrorState } from './shared'
import { Button } from './ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from './ui/dialog'

export const schedules: [number, string][] = [
  [24, 'Daily'],
  [6, 'Every 6 hours'],
  [1, 'Every hour'],
  [0, 'Manual only'],
]

export function ConnectSheet({
  open,
  onOpenChange,
  onConnected,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConnected: (message: string) => void
}) {
  const client = useQueryClient()
  const [kind, setKind] = useState('orders')
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')
  const [refresh, setRefresh] = useState(24)
  const contracts = useQuery({
    queryKey: ['contracts'],
    queryFn: () => api<Contracts>('/sources/contracts'),
    staleTime: Infinity,
  })
  const connect = useMutation({
    mutationFn: () => post<Connection>('/connections', { kind, url, name, refresh_hours: refresh }),
    onSuccess: (data) => {
      client.invalidateQueries({ queryKey: ['connections'] })
      client.invalidateQueries({ queryKey: ['sources'] })
      client.invalidateQueries({ queryKey: ['dashboard'] })
      onConnected(`${data.name} is connected and its data was imported.`)
      setUrl('')
      setName('')
      onOpenChange(false)
    },
  })
  function submit(event: FormEvent) {
    event.preventDefault()
    connect.mutate()
  }
  const contract = contracts.data?.[kind]
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        connect.reset()
        onOpenChange(value)
      }}
    >
      <DialogContent>
        <DialogTitle className="text-xl font-semibold">Connect a Google Sheet</DialogTitle>
        <DialogDescription className="text-sm leading-6 text-muted-foreground">
          SanketAI imports the sheet now and checks it again on your schedule. A changed sheet
          becomes a new source version; earlier reports keep the version they used.
        </DialogDescription>
        <form className="space-y-4" onSubmit={submit}>
          <div>
            <label htmlFor="sheet-kind">Dataset type</label>
            <select id="sheet-kind" value={kind} onChange={(e) => setKind(e.target.value)}>
              {Object.keys(contracts.data || { orders: null }).map((value) => (
                <option value={value} key={value}>
                  {value.charAt(0).toUpperCase() + value.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="sheet-url">Google Sheets link</label>
            <input
              id="sheet-url"
              type="url"
              required
              placeholder="https://docs.google.com/spreadsheets/d/…/edit#gid=0"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="sheet-name">Name (optional)</label>
              <input
                id="sheet-name"
                maxLength={120}
                placeholder={`Google Sheet ${kind}`}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="sheet-refresh">Check for changes</label>
              <select
                id="sheet-refresh"
                value={refresh}
                onChange={(e) => setRefresh(Number(e.target.value))}
              >
                {schedules.map(([hours, label]) => (
                  <option value={hours} key={hours}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="rounded-xl bg-muted/70 p-4 text-[11px] leading-5 text-muted-foreground">
            <ol className="list-decimal space-y-1 pl-4">
              <li>
                In Google Sheets, choose <b>Share → General access → Anyone with the link</b>{' '}
                (Viewer).
              </li>
              <li>Keep one dataset per tab, with column names in the first row.</li>
              <li>Open that tab and copy the link from the address bar (it ends in #gid=…).</li>
            </ol>
            {contract && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {contract.required.map((column) => (
                  <span
                    key={column}
                    className="rounded-md border bg-background px-2 py-1 font-mono text-[11px] text-foreground"
                  >
                    {column}
                  </span>
                ))}
                {contract.optional.map((column) => (
                  <span
                    key={column}
                    className="rounded-md border border-dashed bg-background px-2 py-1 font-mono text-[11px]"
                  >
                    {column} (optional)
                  </span>
                ))}
              </div>
            )}
            <p className="mt-3">
              Anyone who has the link can view the sheet. Private sheets need Google sign-in, which
              is not supported yet.
            </p>
          </div>
          {connect.error && <ErrorState error={connect.error} />}
          <Button className="w-full" type="submit" disabled={!url || connect.isPending}>
            {connect.isPending ? <Loader2 className="animate-spin" /> : <Link2 />}
            {connect.isPending ? 'Importing sheet…' : 'Connect & import'}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
