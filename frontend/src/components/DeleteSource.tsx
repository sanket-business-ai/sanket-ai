import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Trash2 } from 'lucide-react'
import { api, post } from '@/lib/api'
import type { DeleteResult, Source, SourceUsage } from '@/lib/types'
import { ErrorState, Loading } from './shared'
import { Button } from './ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from './ui/dialog'

export function DeleteSource({
  source,
  onClose,
  onDeleted,
}: {
  source: Source | null
  onClose: () => void
  onDeleted: (message: string) => void
}) {
  const client = useQueryClient()
  const id = source?.id
  const usage = useQuery({
    queryKey: ['source-usage', id],
    queryFn: () => api<SourceUsage>(`/sources/${id}/usage`),
    enabled: !!id,
    staleTime: 0,
  })
  const reports = usage.data?.investigations ?? 0
  const remove = useMutation({
    mutationFn: () =>
      post<DeleteResult>(`/sources/${id}/delete`, { delete_investigations: reports > 0 }),
    onSuccess: (data) => {
      client.removeQueries({ queryKey: ['source-usage', id] })
      client.invalidateQueries()
      onDeleted(
        data.investigations
          ? `${source?.name} deleted, with ${data.investigations} investigation(s) and ${data.actions} action(s) that used it.`
          : `${source?.name} deleted.`,
      )
      onClose()
    },
  })
  const kind = source?.kind === 'document' ? 'document' : `${source?.kind} data`
  return (
    <Dialog
      open={!!source}
      onOpenChange={(open) => {
        if (!open) {
          remove.reset()
          onClose()
        }
      }}
    >
      <DialogContent>
        <DialogTitle className="text-xl font-semibold">Delete {source?.name}?</DialogTitle>
        <DialogDescription className="text-sm leading-6 text-muted-foreground">
          The stored file is removed permanently. This cannot be undone.
        </DialogDescription>
        {usage.isPending ? (
          <Loading />
        ) : usage.error ? (
          <ErrorState error={usage.error} retry={() => usage.refetch()} />
        ) : (
          <div className="space-y-3 text-sm leading-6">
            {usage.data.running && (
              <p className="rounded-lg border border-warning/20 bg-warning-bg p-3 text-warning">
                An investigation using this source is still running. Wait for it to finish.
              </p>
            )}
            {usage.data.active && source?.kind !== 'document' && (
              <p className="text-muted-foreground">
                {usage.data.replacement
                  ? `The previous version, ${usage.data.replacement}, becomes the current ${kind}.`
                  : `New investigations will have no ${kind} until you upload a new file.`}
              </p>
            )}
            {reports > 0 && (
              <p className="rounded-lg bg-danger-bg p-3 text-danger">
                {reports} investigation(s) and {usage.data.actions} action(s) used this file and
                will also be deleted, because a report cannot outlive its evidence. To keep them,
                upload a corrected version instead.
              </p>
            )}
          </div>
        )}
        {remove.error && <ErrorState error={remove.error} />}
        <Button
          className="w-full"
          variant="destructive"
          disabled={!usage.data || usage.data.running || remove.isPending}
          onClick={() => remove.mutate()}
        >
          {remove.isPending ? <Loader2 className="animate-spin" /> : <Trash2 />}
          {reports > 0 ? `Delete source and ${reports} investigation(s)` : 'Delete source'}
        </Button>
      </DialogContent>
    </Dialog>
  )
}
