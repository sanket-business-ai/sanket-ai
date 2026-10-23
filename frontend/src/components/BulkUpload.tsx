import { useRef, useState, type DragEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Check, Loader2, UploadCloud, X } from 'lucide-react'
import { api, post } from '@/lib/api'
import type { Contracts, Investigation, Source } from '@/lib/types'
import { Button } from './ui/button'
import { Card } from './ui/card'

type Row = {
  key: string
  file: File
  kind: string
  include: boolean
  note?: string
  status: 'ready' | 'uploading' | 'done' | 'error'
  message?: string
}

const DOCUMENT = /\.(pdf|txt|md)$/i
const DATASET = /\.(csv|xlsx)$/i
const SKIPPED = /^(readme|answer_key)\b/i

// Folder drops expose entries, not files; walk them and keep the readable ones.
async function dropped(event: DragEvent): Promise<File[]> {
  const entries = Array.from(event.dataTransfer.items)
    .map((item) => item.webkitGetAsEntry?.())
    .filter((entry): entry is FileSystemEntry => !!entry)
  if (!entries.length) return Array.from(event.dataTransfer.files)
  const files: File[] = []
  async function walk(entry: FileSystemEntry) {
    if (entry.isFile) {
      files.push(
        await new Promise<File>((resolve, reject) =>
          (entry as FileSystemFileEntry).file(resolve, reject),
        ),
      )
    } else if (entry.isDirectory) {
      const reader = (entry as FileSystemDirectoryEntry).createReader()
      let batch: FileSystemEntry[] = []
      do {
        batch = await new Promise((resolve, reject) => reader.readEntries(resolve, reject))
        for (const child of batch) await walk(child)
      } while (batch.length)
    }
  }
  for (const entry of entries) await walk(entry)
  return files
}

async function detect(file: File, contracts: Contracts | undefined) {
  if (DOCUMENT.test(file.name)) return 'document'
  if (!/\.csv$/i.test(file.name) || !contracts) return ''
  const header = (await file.slice(0, 8192).text())
    .replace(/^﻿/, '')
    .split(/\r?\n/)[0]
    .split(',')
    .map((column) => column.trim().replace(/^"|"$/g, ''))
  const matches = Object.entries(contracts).filter(([, contract]) =>
    contract.required.every((column) => header.includes(column)),
  )
  matches.sort((a, b) => b[1].required.length - a[1].required.length)
  return matches[0]?.[0] ?? ''
}

function suggestions(kinds: Set<string>) {
  const list: string[] = []
  if (kinds.has('purchases') || kinds.has('expenses'))
    list.push('Revenue increased, so why is our margin falling?')
  if (kinds.has('inventory') || kinds.has('suppliers'))
    list.push('Why did our sales drop in the latest 28 days?')
  if (kinds.has('deliveries')) list.push('Why are our deliveries late?')
  if (kinds.has('marketing')) list.push('Did our ad spend increase sales?')
  return list.slice(0, 3)
}

export function BulkUpload({ onDone }: { onDone: (message: string) => void }) {
  const client = useQueryClient()
  const navigate = useNavigate()
  const input = useRef<HTMLInputElement>(null)
  const [rows, setRows] = useState<Row[]>([])
  const [over, setOver] = useState(false)
  const [uploaded, setUploaded] = useState<Set<string>>(new Set())
  const contracts = useQuery({
    queryKey: ['contracts'],
    queryFn: () => api<Contracts>('/sources/contracts'),
    staleTime: Infinity,
  })
  const investigate = useMutation({
    mutationFn: (question: string) => post<Investigation>('/investigations', { question }),
    onSuccess: (job) => navigate(`/investigations/${job.id}`),
  })

  async function add(files: File[]) {
    setUploaded(new Set())
    const next = await Promise.all(
      files
        .filter((file) => !file.name.startsWith('.'))
        .map(async (file, index): Promise<Row> => {
          const supported = DOCUMENT.test(file.name) || DATASET.test(file.name)
          const kind = supported ? await detect(file, contracts.data) : ''
          const skipped = SKIPPED.test(file.name)
          return {
            key: `${file.name}-${file.size}-${index}-${Date.now()}`,
            file,
            kind: kind || (/\.xlsx$/i.test(file.name) ? 'auto' : ''),
            include: supported && !skipped,
            note: !supported
              ? 'Not a supported file'
              : skipped
                ? 'Looks like a readme; not added as evidence'
                : undefined,
            status: 'ready',
          }
        }),
    )
    setRows((current) => [...current, ...next])
  }

  function update(key: string, change: Partial<Row>) {
    setRows((current) => current.map((row) => (row.key === key ? { ...row, ...change } : row)))
  }

  const queue = rows.filter((row) => row.include && row.status !== 'done')
  const missingType = queue.some((row) => !row.kind)
  const counts = queue.reduce<Record<string, number>>((all, row) => {
    if (row.kind && row.kind !== 'document' && row.kind !== 'auto')
      all[row.kind] = (all[row.kind] ?? 0) + 1
    return all
  }, {})
  const duplicates = Object.entries(counts).filter(([, count]) => count > 1)

  const upload = useMutation({
    mutationFn: async () => {
      const done = new Set<string>()
      for (const row of queue) {
        update(row.key, { status: 'uploading', message: undefined })
        const form = new FormData()
        form.append('file', row.file)
        form.append('kind', row.kind)
        try {
          const source = await api<Source>('/sources', { method: 'POST', body: form })
          update(row.key, { status: 'done', kind: source.kind })
          done.add(source.kind)
        } catch (error) {
          update(row.key, { status: 'error', message: (error as Error).message })
        }
      }
      return done
    },
    onSuccess: (done) => {
      client.invalidateQueries({ queryKey: ['sources'] })
      client.invalidateQueries({ queryKey: ['dashboard'] })
      setUploaded(done)
      if (done.size) onDone('Files added. Ask a question below, or start from the Overview page.')
    },
  })

  const kinds = Object.keys(contracts.data ?? {})
  return (
    <Card className="mb-7 p-5">
      <div
        role="button"
        tabIndex={0}
        aria-label="Add files: drop files or a folder, or press Enter to choose"
        onClick={() => input.current?.click()}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={async (e) => {
          e.preventDefault()
          setOver(false)
          add(await dropped(e))
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-6 py-8 text-center transition-colors ${over ? 'border-foreground/40 bg-muted' : 'border-border hover:bg-muted/50'}`}
      >
        <UploadCloud size={22} className="text-muted-foreground" />
        <p className="mt-3 text-sm font-medium">Drop files or a folder here</p>
        <p className="mt-1 text-xs text-muted-foreground">
          CSV or XLSX datasets and PDF, TXT or Markdown documents. Types are detected for you.
        </p>
        <input
          ref={input}
          type="file"
          multiple
          className="sr-only"
          accept=".csv,.xlsx,.pdf,.txt,.md"
          onChange={(e) => {
            add(Array.from(e.target.files ?? []))
            e.target.value = ''
          }}
        />
      </div>

      {rows.length > 0 && (
        <div className="mt-5">
          <ul className="divide-y rounded-lg border">
            {rows.map((row) => (
              <li key={row.key} className="flex flex-wrap items-center gap-3 px-3 py-2.5 text-sm">
                <input
                  type="checkbox"
                  className="size-3.5 accent-primary"
                  aria-label={`Include ${row.file.name}`}
                  checked={row.include}
                  disabled={(!!row.note && row.note.startsWith('Not')) || row.status === 'done'}
                  onChange={(e) => update(row.key, { include: e.target.checked })}
                />
                <span className="min-w-0 flex-1 truncate font-mono text-xs">{row.file.name}</span>
                {row.note && <span className="text-xs text-muted-foreground">{row.note}</span>}
                {!row.note?.startsWith('Not') && (
                  <select
                    aria-label={`Type of ${row.file.name}`}
                    className="h-8 w-40 py-0 text-xs"
                    value={row.kind}
                    disabled={row.status === 'done' || row.status === 'uploading'}
                    onChange={(e) => update(row.key, { kind: e.target.value })}
                  >
                    <option value="">Choose type…</option>
                    {/\.xlsx$/i.test(row.file.name) && (
                      <option value="auto">Detect on upload</option>
                    )}
                    {kinds.map((kind) => (
                      <option key={kind} value={kind}>
                        {kind.charAt(0).toUpperCase() + kind.slice(1)}
                      </option>
                    ))}
                    <option value="document">Document</option>
                  </select>
                )}
                <span className="w-20 text-right text-xs">
                  {row.status === 'uploading' && (
                    <Loader2 size={14} className="ml-auto animate-spin text-muted-foreground" />
                  )}
                  {row.status === 'done' && (
                    <span className="inline-flex items-center gap-1 text-success">
                      <Check size={13} />
                      Added
                    </span>
                  )}
                  {row.status === 'error' && <span className="text-danger">Failed</span>}
                </span>
                {row.message && (
                  <p className="w-full pl-7 text-xs leading-5 text-danger">{row.message}</p>
                )}
              </li>
            ))}
          </ul>
          {duplicates.length > 0 && (
            <p className="mt-3 text-xs leading-5 text-muted-foreground">
              {duplicates.map(([kind, count]) => `${count} ${kind} files`).join(', ')}: each upload
              becomes a new version, and only the last one is used for new investigations.
            </p>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button
              disabled={!queue.length || missingType || upload.isPending}
              onClick={() => upload.mutate()}
            >
              {upload.isPending ? <Loader2 className="animate-spin" /> : <UploadCloud />}
              {upload.isPending
                ? 'Uploading…'
                : `Upload ${queue.length} file${queue.length === 1 ? '' : 's'}`}
            </Button>
            <Button
              variant="ghost"
              disabled={upload.isPending}
              onClick={() => {
                setRows([])
                setUploaded(new Set())
              }}
            >
              <X />
              Clear list
            </Button>
            {missingType && (
              <span className="text-xs text-muted-foreground">
                Choose a type for every file first.
              </span>
            )}
          </div>
        </div>
      )}

      {uploaded.size > 0 && suggestions(uploaded).length > 0 && (
        <div className="mt-5 border-t pt-4">
          <p className="text-xs text-muted-foreground">Investigate now</p>
          <div className="mt-2 flex flex-col items-start gap-1">
            {suggestions(uploaded).map((question) => (
              <button
                key={question}
                className="inline-flex items-center gap-2 text-sm font-medium hover:underline disabled:opacity-50"
                disabled={investigate.isPending}
                onClick={() => investigate.mutate(question)}
              >
                {question}
                <ArrowRight size={13} />
              </button>
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}
