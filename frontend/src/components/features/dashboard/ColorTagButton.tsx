import { Popover as PopoverPrimitive } from 'radix-ui'

import type { LabelColor } from '@/types/signal'

interface ColorTagButtonProps {
  ticker: string
  color: LabelColor
  onChange: (color: LabelColor) => void
}

const COLOR_TOKENS: Record<'red' | 'yellow' | 'blue', string> = {
  red: 'var(--color-label-red)',
  yellow: 'var(--color-label-yellow)',
  blue: 'var(--color-label-blue)',
}

const COLOR_CHOICES: { value: LabelColor; label: string }[] = [
  { value: 'red', label: '标记红色' },
  { value: 'yellow', label: '标记黄色' },
  { value: 'blue', label: '标记蓝色' },
  { value: null, label: '清除标记' },
]

function swatchStyle(color: LabelColor, selected: boolean): React.CSSProperties {
  return {
    width: 14,
    height: 14,
    borderRadius: 'var(--radius-full)',
    backgroundColor: color ? COLOR_TOKENS[color] : 'transparent',
    border: color ? 'none' : '1.5px solid var(--color-border)',
    outline: selected ? '2px solid var(--color-ring)' : 'none',
    outlineOffset: 2,
    padding: 0,
    cursor: 'pointer',
    flexShrink: 0,
  }
}

export function ColorTagButton({ ticker, color, onChange }: ColorTagButtonProps) {
  return (
    <PopoverPrimitive.Root>
      <span onClick={(e) => e.stopPropagation()} className="inline-flex">
        <PopoverPrimitive.Trigger asChild>
          <button
            type="button"
            aria-label={`颜色标记 ${ticker}`}
            style={swatchStyle(color, false)}
          />
        </PopoverPrimitive.Trigger>
      </span>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="start"
          sideOffset={4}
          onClick={(e) => e.stopPropagation()}
          className="z-50 flex rounded-lg bg-popover shadow-md ring-1 ring-foreground/10"
          style={{ gap: 'var(--spacing-2)', padding: 'var(--spacing-2)' }}
        >
          {COLOR_CHOICES.map((choice) => (
            <PopoverPrimitive.Close key={choice.value ?? 'none'} asChild>
              <button
                type="button"
                aria-label={choice.label}
                onClick={() => onChange(choice.value)}
                style={swatchStyle(choice.value, choice.value === color)}
              />
            </PopoverPrimitive.Close>
          ))}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
}
