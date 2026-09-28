import { Check } from '@phosphor-icons/react'
import { useId, useState } from 'react'
import type { FeedbackLabel } from '../types'
import './Feedback.css'

const LABELS: { id: FeedbackLabel; text: string }[] = [
  { id: 'relevant', text: 'Relevant' },
  { id: 'not_relevant', text: 'Not relevant' },
  { id: 'too_advanced', text: 'Too advanced' },
  { id: 'too_basic', text: 'Too basic' },
  { id: 'already_learned', text: 'Already learned' },
]

type Status = { kind: 'idle' } | { kind: 'saving' } | { kind: 'saved' } | { kind: 'error'; message: string }

export default function Feedback({ onSend }: { onSend: (label: FeedbackLabel, comment?: string) => Promise<void> }) {
  const [label, setLabel] = useState<FeedbackLabel | null>(null)
  const [comment, setComment] = useState('')
  const [status, setStatus] = useState<Status>({ kind: 'idle' })
  const ids = { group: useId(), comment: useId() }

  const send = async (next: FeedbackLabel, note?: string) => {
    setLabel(next)
    setStatus({ kind: 'saving' })
    try {
      await onSend(next, note)
      setStatus({ kind: 'saved' })
      if (note) setComment('')
    } catch (err) {
      setStatus({ kind: 'error', message: (err as Error).message || 'Could not save feedback.' })
    }
  }

  return (
    <div className="feedback">
      <p className="feedback-q" id={ids.group}>Was this a good suggestion for you?</p>
      <div className="feedback-labels" role="group" aria-labelledby={ids.group}>
        {LABELS.map((l) => (
          <button key={l.id} type="button" className="fb" aria-pressed={label === l.id}
            disabled={status.kind === 'saving'} onClick={() => send(l.id)}>
            {label === l.id && status.kind === 'saved' && <Check size={14} weight="bold" aria-hidden="true" />}
            {l.text}
          </button>
        ))}
      </div>
      {label && (
        <form className="feedback-comment" onSubmit={(e) => { e.preventDefault(); if (comment.trim()) void send(label, comment.trim()) }}>
          <label htmlFor={ids.comment} className="field-label">Add a note (optional)</label>
          <div className="feedback-comment-row">
            <input id={ids.comment} className="input" value={comment} maxLength={1000} onChange={(e) => setComment(e.target.value)} />
            <button type="submit" className="btn" disabled={!comment.trim() || status.kind === 'saving'}>Send note</button>
          </div>
        </form>
      )}
      <p className="feedback-status" role="status">
        {status.kind === 'saving' && 'Saving.'}
        {status.kind === 'saved' && 'Saved. Feedback is stored for review; it does not change rankings on its own.'}
        {status.kind === 'error' && <span className="feedback-error">{status.message} Press a label to try again.</span>}
      </p>
    </div>
  )
}
