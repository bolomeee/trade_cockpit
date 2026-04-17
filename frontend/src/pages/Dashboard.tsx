import { Button } from '@/components/ui/button'

export default function Dashboard() {
  return (
    <section>
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <p className="mt-2 text-red-500">Tailwind v4 check (red)</p>
      <p
        className="mt-1"
        style={{ color: 'var(--color-signal-breakout)' }}
      >
        tokens.css check (should be #2962ff)
      </p>
      <Button className="mt-4">Hello shadcn</Button>
    </section>
  )
}
