import { ArrowRight } from '@phosphor-icons/react'
import { useEffect, useRef, type FormEvent, type KeyboardEvent } from 'react'
import './Composer.css'

export const EXAMPLES = [
  'I know Python and SQL. Help me move into machine learning.',
  'I want to learn cloud computing from the basics.',
  'Suggest a path from beginner to advanced data analytics.',
]
const MAX = 500

interface Props {
  goal: string
  onGoalChange: (goal: string) => void
  onSubmit: (goal: string) => void
  busy: boolean
  disabled: boolean
  error: string | null
}

export default function Composer({ goal, onGoalChange, onSubmit, busy, disabled, error }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [goal])

  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    if (goal.trim()) onSubmit(goal.trim())
    else ref.current?.focus()
  }

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const empty = goal.trim().length === 0
  const describedBy = ['goal-help', error ? 'goal-error' : ''].filter(Boolean).join(' ')

  return (
    <form className="composer" onSubmit={submit} noValidate>
      <label htmlFor="goal" className="composer-label">What do you want to learn next?</label>
      <div className="composer-row">
        <textarea
          id="goal"
          ref={ref}
          className="composer-input"
          rows={1}
          maxLength={MAX}
          value={goal}
          onChange={(e) => onGoalChange(e.target.value)}
          onKeyDown={onKey}
          aria-describedby={describedBy}
          aria-invalid={error ? true : undefined}
          disabled={disabled}
          spellCheck
        />
        <button type="submit" className="btn btn-primary composer-go" disabled={disabled || busy}>
          {busy ? 'Finding' : 'Find courses'}
          <ArrowRight size={20} weight="bold" aria-hidden="true" />
        </button>
      </div>
      <p id="goal-help" className="composer-help">
        Say what you know and where you want to go. Press Enter to search.
        {goal.length > MAX - 80 && <span className="num"> {MAX - goal.length} characters left.</span>}
      </p>
      {error && <p id="goal-error" className="composer-error" role="alert">{error}</p>}
      {empty && (
        <div className="examples" aria-label="Example goals">
          {EXAMPLES.map((ex) => (
            <button key={ex} type="button" className="example" disabled={disabled} onClick={() => { onGoalChange(ex); onSubmit(ex) }}>
              {ex}
            </button>
          ))}
        </div>
      )}
    </form>
  )
}
