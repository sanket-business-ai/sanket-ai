import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Eraser, Loader2 } from 'lucide-react'
import { post } from '@/lib/api'
import type { ResetResult } from '@/lib/types'
import { ErrorState } from './shared'
import { Button } from './ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from './ui/dialog'

export function ClearWorkspace({ onCleared }: { onCleared: (message: string) => void }) {
  const client = useQueryClient()
  const [open, setOpen] = useState(false)
  const clear = useMutation({
    mutationFn: () => post<ResetResult>('/workspace/reset', { confirm: 'RESET' }),
    onSuccess: (data) => {
      client.invalidateQueries()
      setOpen(false)
      onCleared(
        `Workspace cleared: ${data.sources} sources, ${data.investigations} investigations and ${data.actions} actions removed.`,
      )
    },
  })
  return (
    <>
      <Button
        variant="ghost"
        onClick={() => {
          clear.reset()
          setOpen(true)
        }}
      >
        <Eraser />
        Clear workspace
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogTitle className="text-lg font-semibold">Clear the workspace?</DialogTitle>
          <DialogDescription className="text-sm leading-6 text-muted-foreground">
            Every source, investigation, action and live connection is deleted so you can start with
            new files. Your sign-in and the audit trail stay. This cannot be undone.
          </DialogDescription>
          {clear.error && <ErrorState error={clear.error} />}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" disabled={clear.isPending} onClick={() => clear.mutate()}>
              {clear.isPending && <Loader2 className="animate-spin" />}
              Clear everything
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
