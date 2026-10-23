import { useRef, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Database,
  Download,
  FileSpreadsheet,
  FileText,
  Link2,
  Loader2,
  Plus,
  ShieldCheck,
  Sparkles,
  Trash2,
  UploadCloud,
} from 'lucide-react'
import { api, download, post } from '@/lib/api'
import type { Contracts, DemoPack, DemoResult, Source, System } from '@/lib/types'
import { dateTime, number } from '@/lib/utils'
import { Empty, ErrorState, Loading, PageHeading } from '@/components/shared'
import { BulkUpload } from '@/components/BulkUpload'
import { ClearWorkspace } from '@/components/ClearWorkspace'
import { ConnectSheet } from '@/components/ConnectSheet'
import { Connections } from '@/components/Connections'
import { DeleteSource } from '@/components/DeleteSource'
import { SourcePreview } from '@/components/SourcePreview'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'

const kinds = [
  'orders',
  'products',
  'inventory',
  'suppliers',
  'deliveries',
  'marketing',
  'customers',
  'expenses',
  'purchases',
  'document',
]
export default function Sources() {
  const client = useQueryClient()
  const [open, setOpen] = useState(false)
  const [kind, setKind] = useState('orders')
  const [file, setFile] = useState<File | null>(null)
  const [source, setSource] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<Source | null>(null)
  const [connecting, setConnecting] = useState(false)
  const [allVersions, setAllVersions] = useState(false)
  const [success, setSuccess] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const query = useQuery({ queryKey: ['sources'], queryFn: () => api<Source[]>('/sources') })
  const contracts = useQuery({
    queryKey: ['contracts'],
    queryFn: () => api<Contracts>('/sources/contracts'),
    staleTime: Infinity,
  })
  const system = useQuery({ queryKey: ['system'], queryFn: () => api<System>('/system') })
  const upload = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('Choose a file to upload')
      if (file.size > (system.data?.upload_max_bytes ?? 10485760))
        throw new Error('File exceeds the 10 MB upload limit')
      const form = new FormData()
      form.append('file', file)
      form.append('kind', kind)
      return api<Source>('/sources', { method: 'POST', body: form })
    },
    onSuccess: (data) => {
      refresh()
      setSuccess(`${data.name} is ready for investigation.`)
      setOpen(false)
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
    },
  })
  const demo = useMutation({
    mutationFn: (pack: DemoPack) => post<DemoResult>('/demo', { pack }),
    onSuccess: (data) => {
      refresh()
      setSuccess(
        `HimalayanMart synthetic ${data.pack === 'margin' ? 'margin ' : ''}evidence pack loaded: ${data.datasets} datasets and ${data.documents} documents.`,
      )
    },
  })
  const save = useMutation({ mutationFn: (id: string) => download(`/sources/${id}/download`) })
  const failure = demo.error ?? save.error
  function refresh() {
    client.invalidateQueries({ queryKey: ['sources'] })
    client.invalidateQueries({ queryKey: ['dashboard'] })
  }
  function submit(event: FormEvent) {
    event.preventDefault()
    upload.mutate()
  }
  function template() {
    const contract = contracts.data?.[kind]
    const columns = contract ? [...contract.required, ...contract.optional] : []
    const blob = new Blob([columns.join(',') + '\n'], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${kind}_template.csv`
    a.click()
    URL.revokeObjectURL(url)
  }
  const sources = query.data?.filter((item) => allVersions || item.active) || []
  const tableCount =
    query.data?.filter((item) => item.active && item.kind !== 'document').length || 0
  const documentCount = query.data?.filter((item) => item.kind === 'document').length || 0
  return (
    <>
      <PageHeading
        eyebrow="CONNECT THE DOTS"
        title="Data sources"
        description="Your business evidence, in one place. Each upload becomes a preserved source version."
        action={
          <div className="flex flex-wrap gap-2">
            {system.data?.demo_enabled && !!query.data?.length && (
              <ClearWorkspace onCleared={setSuccess} />
            )}
            <Button variant="outline" onClick={() => setConnecting(true)}>
              <Link2 />
              Connect Google Sheet
            </Button>
            <Button
              onClick={() => {
                upload.reset()
                setOpen(true)
              }}
            >
              <Plus />
              Upload evidence
            </Button>
          </div>
        }
      />
      <section className="mb-7 grid gap-4 sm:grid-cols-3">
        {[
          [Database, 'Connected datasets', tableCount],
          [FileText, 'Business documents', documentCount],
          [ShieldCheck, 'Source versions', query.data?.length || 0],
        ].map(([Icon, label, value]) => {
          const Symbol = Icon as typeof Database
          return (
            <Card key={String(label)} className="flex items-center gap-4 p-5">
              <span className="rounded-xl bg-primary/5 p-3 text-primary">
                <Symbol size={21} />
              </span>
              <div>
                <p className="text-xs text-muted-foreground">{String(label)}</p>
                <p className="mt-2 text-2xl font-semibold">{String(value)}</p>
              </div>
            </Card>
          )
        })}
      </section>
      {success && (
        <p
          role="status"
          className="mb-5 rounded-lg border border-primary/20 bg-primary/5 p-4 text-sm text-primary"
        >
          {success}
        </p>
      )}
      {failure && (
        <div className="mb-5">
          <ErrorState error={failure} />
        </div>
      )}
      <BulkUpload onDone={setSuccess} />
      <Connections onMessage={setSuccess} />
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => query.refetch()} />
      ) : !query.data?.length ? (
        <Empty
          title="Start with the evidence you already have"
          description="Upload orders, inventory, supplier records, and business reports. Use the synthetic demo pack to explore the full investigation flow."
          action={
            <div className="flex flex-wrap justify-center gap-3">
              <Button onClick={() => setOpen(true)}>
                <UploadCloud />
                Upload your first file
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
                    Load HimalayanMart demo
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
      ) : (
        <Card>
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-4">
            <CardTitle>Evidence library</CardTitle>
            <label className="m-0 flex items-center gap-2 text-xs font-normal text-muted-foreground">
              <input
                className="size-3.5 accent-primary"
                type="checkbox"
                checked={allVersions}
                onChange={(e) => setAllVersions(e.target.checked)}
              />
              Show previous versions
            </label>
          </CardHeader>
          <CardContent>
            <div className="table-scroll">
              <table className="source-table">
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Type</th>
                    <th>Records</th>
                    <th>Added</th>
                    <th>Version</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {sources.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <div className="flex items-center gap-3">
                          <span
                            className={`rounded-lg p-2 ${item.kind === 'document' ? 'bg-warning-bg text-warning' : 'bg-primary/5 text-primary'}`}
                          >
                            {item.kind === 'document' ? (
                              <FileText size={17} />
                            ) : (
                              <FileSpreadsheet size={17} />
                            )}
                          </span>
                          <div>
                            <p className="font-medium">{item.name}</p>
                            <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                              {item.id.slice(0, 8)}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="capitalize">{item.kind}</td>
                      <td>
                        {number(item.row_count)} {item.kind === 'document' ? 'chunks' : 'rows'}
                      </td>
                      <td>{dateTime(item.created_at)}</td>
                      <td>
                        <Badge variant={item.active ? 'default' : 'secondary'}>
                          {item.active ? 'Current' : 'Preserved'}
                        </Badge>
                      </td>
                      <td>
                        <div className="flex justify-end gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={save.isPending && save.variables === item.id}
                            onClick={() => save.mutate(item.id)}
                            aria-label={`Download ${item.name}`}
                            title={
                              item.kind === 'document'
                                ? 'Download extracted text'
                                : 'Download as CSV'
                            }
                          >
                            {save.isPending && save.variables === item.id ? (
                              <Loader2 className="animate-spin" />
                            ) : (
                              <Download />
                            )}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setSource(item.id)}
                            aria-label={`Inspect ${item.name}`}
                          >
                            Inspect
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="danger-on-card text-danger hover:text-danger"
                            onClick={() => {
                              setSuccess('')
                              setDeleting(item)
                            }}
                            aria-label={`Delete ${item.name}`}
                            title="Delete source"
                          >
                            <Trash2 />
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
      )}
      <section className="mt-7 grid gap-6 md:grid-cols-2">
        <Card className="bg-transparent shadow-none">
          <CardHeader>
            <CardTitle>What makes useful evidence?</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3 text-xs leading-6 text-muted-foreground">
              <li>Include at least 56 days of orders for equal 28-day comparisons.</li>
              <li>Match product, customer, supplier, and order IDs across your files.</li>
              <li>Use ISO dates (YYYY-MM-DD), non-negative amounts, and NPR throughout.</li>
              <li>
                Add supplier incidents, customer feedback, and internal reports as PDF or text.
              </li>
            </ul>
          </CardContent>
        </Card>
        <Card className="bg-transparent shadow-none">
          <CardHeader>
            <CardTitle>Versioned by design</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs leading-7 text-muted-foreground">
              The newest file for each dataset type is used in new investigations. Upload a complete
              replacement dataset each time. Documents accumulate as separate evidence. Previous
              investigations keep their original source versions, so their calculations and
              conclusions remain reviewable.
            </p>
            <p className="mt-3 text-xs font-medium text-primary">
              CSV & Excel datasets · PDF, TXT & Markdown documents · 10 MB per file
            </p>
          </CardContent>
        </Card>
      </section>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogTitle className="text-xl font-semibold">Connect a piece of evidence</DialogTitle>
          <DialogDescription className="text-sm leading-6 text-muted-foreground">
            Choose the dataset type and upload a complete file. Validation runs before any data is
            saved.
          </DialogDescription>
          <form className="space-y-5" onSubmit={submit}>
            <div>
              <label htmlFor="dataset-kind">Evidence type</label>
              <select
                id="dataset-kind"
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value)
                  setFile(null)
                  upload.reset()
                  if (fileRef.current) fileRef.current.value = ''
                }}
              >
                {kinds.map((value) => (
                  <option value={value} key={value}>
                    {value === 'document'
                      ? 'Business document'
                      : value.charAt(0).toUpperCase() + value.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <label
              className="upload-zone"
              htmlFor="evidence-file"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault()
                setFile(e.dataTransfer.files[0] || null)
              }}
            >
              <UploadCloud size={27} className="mb-3 text-primary" />
              <span className="text-sm font-semibold">
                {file ? file.name : 'Choose a file or drop it here'}
              </span>
              <span className="mt-2 text-xs font-normal text-muted-foreground">
                {file
                  ? `${(file.size / 1024).toFixed(1)} KB`
                  : kind === 'document'
                    ? 'PDF, TXT or Markdown · up to 10 MB'
                    : 'CSV or XLSX · up to 50,000 rows · 10 MB'}
              </span>
              <input
                ref={fileRef}
                id="evidence-file"
                type="file"
                className="sr-only"
                accept={kind === 'document' ? '.pdf,.txt,.md' : '.csv,.xlsx'}
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </label>
            {kind !== 'document' && (
              <div className="rounded-xl bg-muted/70 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-xs font-semibold">Required columns</p>
                  <Button
                    variant="ghost"
                    size="sm"
                    type="button"
                    onClick={template}
                    disabled={!contracts.data}
                  >
                    <Download />
                    CSV header
                  </Button>
                </div>
                {contracts.isPending ? (
                  <p className="text-xs text-muted-foreground">Loading format…</p>
                ) : contracts.error ? (
                  <ErrorState error={contracts.error} />
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {contracts.data?.[kind]?.required.map((key) => (
                      <span
                        key={key}
                        className="rounded-md border bg-background px-2 py-1 font-mono text-[11px]"
                      >
                        {key}
                      </span>
                    ))}
                    {contracts.data?.[kind]?.optional.map((key) => (
                      <span
                        key={key}
                        className="rounded-md border border-dashed bg-background px-2 py-1 font-mono text-[11px] text-muted-foreground"
                      >
                        {key} (optional)
                      </span>
                    ))}
                  </div>
                )}
                <p className="mt-3 text-[11px] leading-5 text-muted-foreground">
                  Use values in Excel cells, without formulas. Dates must be ISO text. Extra columns
                  are ignored. Orders use delivered, completed, cancelled, returned, pending, or
                  shipped status.
                </p>
              </div>
            )}
            {upload.error && <ErrorState error={upload.error} />}
            <Button className="w-full" type="submit" disabled={!file || upload.isPending}>
              {upload.isPending ? <Loader2 className="animate-spin" /> : <UploadCloud />}
              {upload.isPending ? 'Validating evidence…' : 'Validate & connect'}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
      <ConnectSheet open={connecting} onOpenChange={setConnecting} onConnected={setSuccess} />
      <SourcePreview sourceId={source} onClose={() => setSource(null)} />
      <DeleteSource source={deleting} onClose={() => setDeleting(null)} onDeleted={setSuccess} />
    </>
  )
}
