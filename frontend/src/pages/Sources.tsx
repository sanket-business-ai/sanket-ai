import { useRef, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Database,
  Download,
  FileSpreadsheet,
  FileText,
  Loader2,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  UploadCloud,
} from 'lucide-react'
import { api, post } from '@/lib/api'
import type { DocumentSearchResponse, Source, System } from '@/lib/types'
import { dateTime, number } from '@/lib/utils'
import { Empty, ErrorState, Loading, PageHeading } from '@/components/shared'
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
  'document',
]
export default function Sources() {
  const client = useQueryClient()
  const [open, setOpen] = useState(false)
  const [kind, setKind] = useState('orders')
  const [file, setFile] = useState<File | null>(null)
  const [source, setSource] = useState<string | null>(null)
  const [allVersions, setAllVersions] = useState(false)
  const [success, setSuccess] = useState('')
  const [searchText, setSearchText] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const query = useQuery({ queryKey: ['sources'], queryFn: () => api<Source[]>('/sources') })
  const contracts = useQuery({
    queryKey: ['contracts'],
    queryFn: () => api<Record<string, Record<string, string>>>('/sources/contracts'),
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
    mutationFn: () => post('/demo'),
    onSuccess: () => {
      refresh()
      setSuccess('HimalayanMart synthetic evidence pack loaded: 8 datasets and 4 documents.')
    },
  })
  const documentSearch = useMutation({
    mutationFn: () => post<DocumentSearchResponse>('/sources/search', { query: searchText.trim() }),
  })
  function refresh() {
    client.invalidateQueries({ queryKey: ['sources'] })
    client.invalidateQueries({ queryKey: ['dashboard'] })
  }
  function submit(event: FormEvent) {
    event.preventDefault()
    upload.mutate()
  }
  function template() {
    const columns = Object.keys(contracts.data?.[kind] || {})
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
          <Button
            onClick={() => {
              upload.reset()
              setOpen(true)
            }}
          >
            <Plus />
            Upload evidence
          </Button>
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
      {demo.error && (
        <div className="mb-5">
          <ErrorState error={demo.error} />
        </div>
      )}
      <Card className="mb-7">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search size={18} />
            Search uploaded documents
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Find relevant passages in PDFs and other uploaded documents with local Ollama bge-m3.
            Keyword search is used if embeddings are unavailable.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            className="flex flex-col gap-3 sm:flex-row"
            onSubmit={(event) => {
              event.preventDefault()
              documentSearch.mutate()
            }}
          >
            <label className="sr-only" htmlFor="document-search">
              Search documents
            </label>
            <input
              id="document-search"
              className="min-w-0 flex-1"
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="e.g. why are customers upset about deliveries?"
              maxLength={500}
              required
            />
            <Button
              type="submit"
              disabled={!documentCount || !searchText.trim() || documentSearch.isPending}
            >
              {documentSearch.isPending ? <Loader2 className="animate-spin" /> : <Search />}
              Search documents
            </Button>
          </form>
          {!documentCount && (
            <p className="text-xs text-muted-foreground">
              Upload a PDF or other document to search its contents.
            </p>
          )}
          {documentSearch.error && <ErrorState error={documentSearch.error} />}
          {documentSearch.data && (
            <div aria-live="polite" className="space-y-3">
              <p className="text-xs text-muted-foreground">
                {documentSearch.data.method === 'semantic'
                  ? 'Semantic results · Ollama bge-m3'
                  : 'Keyword fallback · Ollama embeddings unavailable'}
                {' · '}
                {documentSearch.data.results.length} matching passages
              </p>
              {documentSearch.data.results.length ? (
                documentSearch.data.results.map((result) => (
                  <article
                    key={`${result.source_id}-${result.page}-${result.chunk}`}
                    className="rounded-xl border p-4"
                  >
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                      <button
                        type="button"
                        className="text-left text-sm font-semibold text-primary hover:underline"
                        onClick={() => setSource(result.source_id)}
                      >
                        {result.source_name} · Page {result.page}, chunk {result.chunk}
                      </button>
                      <span className="text-xs text-muted-foreground">
                        {documentSearch.data.method === 'semantic'
                          ? `Similarity ${result.score.toFixed(3)}`
                          : `${result.score} keyword matches`}
                      </span>
                    </div>
                    <p className="whitespace-pre-wrap text-sm leading-6">{result.text}</p>
                  </article>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">
                  No matching document passages found.
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
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
                <Button variant="outline" disabled={demo.isPending} onClick={() => demo.mutate()}>
                  {demo.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />}Load
                  HimalayanMart demo
                </Button>
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
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setSource(item.id)}
                          aria-label={`Inspect ${item.name}`}
                        >
                          Inspect
                        </Button>
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
            {kind === 'document'
              ? 'Documents are split into searchable chunks and embedded with local Ollama bge-m3 when available. If Ollama is offline, keyword retrieval remains available.'
              : 'Choose the dataset type and upload a complete file. Validation runs before any data is saved.'}
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
                    ? 'PDF, TXT or Markdown · up to 10 MB · 500 chunks maximum'
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
                    {Object.keys(contracts.data?.[kind] || {}).map((key) => (
                      <span
                        key={key}
                        className="rounded-md border bg-background px-2 py-1 font-mono text-[11px]"
                      >
                        {key}
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
      <SourcePreview sourceId={source} onClose={() => setSource(null)} />
    </>
  )
}
