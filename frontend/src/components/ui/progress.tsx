import * as React from 'react'

import { cn } from '@/lib/utils'

const Progress = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & {
    value?: number
    max?: number
  }
>(({ className, value = 0, max = 100, ...props }, ref) => {
  const pct =
    max > 0 ? Math.min(100, Math.max(0, Math.round((value / max) * 100))) : 0

  return (
    <div
      ref={ref}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      className={cn(
        'relative h-2 w-full overflow-hidden rounded-full bg-foreground/10',
        className
      )}
      {...props}
    >
      <div
        className="h-full bg-foreground transition-[width] duration-300 ease-out"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
})
Progress.displayName = 'Progress'

export { Progress }
