import { cn } from '@/lib/utils'

/** Native select styled to match SAM chrome (no Radix dep). */
export function ModelSelect({
  id,
  value,
  onChange,
  options,
  disabled,
  className,
}: {
  id?: string
  value: string
  onChange: (value: string) => void
  options: { id: string; label: string }[]
  disabled?: boolean
  className?: string
}) {
  return (
    <select
      id={id}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        'h-10 max-w-full rounded-xl border border-border bg-background px-3 py-1.5 text-sm shadow-sm',
        'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className
      )}
    >
      {options.map((m) => (
        <option key={m.id} value={m.id}>
          {m.label}
        </option>
      ))}
    </select>
  )
}
