import { Button } from '@/components/ui/button'
import { useHealthCheck } from '@/shared/hooks/useHealthCheck'

export function DashboardHomePage() {
  const { data, isPending, isError, refetch } = useHealthCheck()

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="text-muted-foreground text-sm">
        Backend health:{' '}
        {isPending ? 'checking…' : isError ? 'unreachable' : (data?.status ?? 'unknown')}
      </p>
      <Button onClick={() => refetch()} size="sm">
        Recheck
      </Button>
    </div>
  )
}
