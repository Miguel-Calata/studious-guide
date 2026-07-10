import { Progress } from '@/components/ui/progress'

export function ProgressBar({
  value,
  total,
  label,
}: {
  value: number
  total: number
  label?: string
}) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs tabular-nums text-muted-foreground">
        <span>{label ?? 'Progreso'}</span>
        <span>
          {value}/{total} ({pct}%)
        </span>
      </div>
      <Progress value={value} max={total || 1} />
    </div>
  )
}
