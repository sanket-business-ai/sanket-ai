import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { SourceDetail } from '@/lib/types'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from './ui/dialog'
import { Button } from './ui/button'
import { ErrorState, Loading } from './shared'

export function SourcePreview({
  sourceId,
  onClose,
}: {
  sourceId: string | null
  onClose: () => void
}) {
  const [offset, setOffset] = useState(0)
  const query = useQuery({
    queryKey: ['source', sourceId, offset],
    queryFn: () => api<SourceDetail>(`/sources/${sourceId}?offset=${offset}`),
    enabled: !!sourceId,
  })
  return (
    <Dialog
      open={!!sourceId}
      onOpenChange={(open) => {
        if (!open) {
          onClose()
          setOffset(0)
        }
      }}
    >
      <DialogContent className="max-w-5xl">
        <DialogTitle className="pr-6 text-lg font-semibold">
          {query.data?.name || 'Source evidence'}
        </DialogTitle>
        <DialogDescription className="text-xs text-muted-foreground">
          Immutable source version · {sourceId?.slice(0, 8)} ·{' '}
          {query.data?.row_count.toLocaleString()}{' '}
          {query.data?.kind === 'document' ? 'chunks' : 'rows'}
        </DialogDescription>
        {query.isPending ? (
          <Loading />
        ) : query.error ? (
          <ErrorState error={query.error} />
        ) : query.data?.rows ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Row</th>
                  {Object.keys(query.data.rows[0] || {}).map((key) => (
                    <th key={key}>{key}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {query.data.rows.map((row, index) => (
                  <tr key={index}>
                    <td>{offset + index + 2}</td>
                    {Object.entries(row).map(([key, value]) => (
                      <td key={key}>{value ?? '—'}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="max-h-[55vh] space-y-4 overflow-auto">
            {query.data?.chunks?.map((chunk) => (
              <div key={chunk.chunk} className="rounded-xl border p-4">
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-primary">
                  Page {chunk.page} · Chunk {chunk.chunk}
                </p>
                <p className="whitespace-pre-wrap text-sm leading-7">{chunk.text}</p>
              </div>
            ))}
          </div>
        )}
        {query.data && query.data.row_count > 100 && (
          <div className="flex items-center justify-between text-xs">
            <span>
              {offset + 1}–{Math.min(offset + 100, query.data.row_count)} of {query.data.row_count}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={!offset}
                onClick={() => setOffset(Math.max(0, offset - 100))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={offset + 100 >= query.data.row_count}
                onClick={() => setOffset(offset + 100)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
