import { ArrowSquareOut, CaretDown } from '@phosphor-icons/react'
import { useId, useState } from 'react'
import type { FeedbackLabel, Recommendation, SkillTile } from '../types'
import CourseMeta from './CourseMeta'
import Feedback from './Feedback'
import './CourseList.css'

interface Props {
  courses: Recommendation[]
  baselineIds: string[] | null
  tiles: SkillTile[]
  effective: string[]
  searchText: string
  eligibleCount: number
  onFeedback: (course: Recommendation, label: FeedbackLabel, comment?: string) => Promise<void>
}

function prereqLine(c: Recommendation): { state: string; text: string } {
  const p = c.prerequisites
  if (p.status === 'unknown') return { state: 'unknown', text: 'Prerequisites not verified.' }
  if (p.status === 'unmet') return { state: 'missing', text: `Missing first: ${p.missing.join(', ')}.` }
  if (p.required.length === 0 && p.source === 'course description') return { state: 'met', text: 'No prior skills needed.' }
  if (p.required.length === 0) return { state: 'met', text: 'No modelled prerequisites.' }
  return { state: 'met', text: `Ready: you have ${p.required.join(', ')}.` }
}

function Entry({ course, isNew, tiles, effective, onFeedback }: {
  course: Recommendation
  isNew: boolean
  tiles: SkillTile[]
  effective: string[]
  onFeedback: Props['onFeedback']
}) {
  const [open, setOpen] = useState(false)
  const panelId = useId()
  const pre = prereqLine(course)
  const primary = course.track_skills.filter((e) => e.strength === 'primary')

  return (
    <li className="course">
      <span className="course-rank num" aria-hidden="true">{course.rank}</span>
      <div className="course-body">
        {isNew && <p className="step-flag">New in this what-if</p>}
        <h3 className="course-title">
          <span className="visually-hidden">Rank {course.rank}: </span>
          {course.title}
        </h3>
        <CourseMeta course={course} />
        {(primary.length > 0 || course.path_step) && (
          <div className="course-teaches">
            {primary.map((e) => {
              const tile = tiles.find((t) => t.skill === e.skill)
              const kind = effective.includes(e.skill) ? 'known' : tile?.group
              return <span key={e.skill} className="mini" data-kind={kind} title={`Teaches ${e.skill} (${e.source})`}>{tile?.abbr ?? e.skill}</span>
            })}
            {course.path_step && <span className="course-inpath">Step {course.path_step} of your path</span>}
          </div>
        )}
        <p className="course-prereq"><span className="mark" data-state={pre.state} aria-hidden="true" />{pre.text}</p>
        <button type="button" className="disclose" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(!open)}>
          Why this course
          <CaretDown size={16} weight="bold" aria-hidden="true" />
        </button>
        <div id={panelId} className="advisor" hidden={!open}>
          <section>
            <h4>Why this helps</h4>
            <ul>{course.advisor.why.map((t) => <li key={t}>{t}</li>)}</ul>
          </section>
          <section>
            <h4>Before you start</h4>
            <ul>{course.advisor.before.map((t) => <li key={t}>{t}</li>)}</ul>
          </section>
          <section>
            <h4>Things to consider</h4>
            {course.advisor.consider.length
              ? <ul>{course.advisor.consider.map((t) => <li key={t}>{t}</li>)}</ul>
              : <p>Nothing flagged in the catalog data for this course.</p>}
          </section>
          {course.summary && (
            <section>
              <h4>From the catalog</h4>
              <p className="advisor-summary">{course.summary}</p>
            </section>
          )}
          {course.course_url && (
            <a className="advisor-link" href={course.course_url} target="_blank" rel="noreferrer">
              Open the course page <ArrowSquareOut size={16} weight="bold" aria-hidden="true" />
            </a>
          )}
          <Feedback onSend={(label, comment) => onFeedback(course, label, comment)} />
        </div>
      </div>
    </li>
  )
}

export default function CourseList({ courses, baselineIds, tiles, effective, searchText, eligibleCount, onFeedback }: Props) {
  return (
    <section className="courses" aria-labelledby="courses-title">
      <header className="courses-head">
        <h2 id="courses-title">Courses for this goal</h2>
        <p className="courses-sub">
          Searched <span className="num">{eligibleCount.toLocaleString()}</span> courses for &ldquo;{searchText}&rdquo;.
          Ranked by relevance, then by whether you have what each one builds on.
        </p>
      </header>
      {courses.length > 0 && (
        <ol className="course-list">
          {courses.map((c) => (
            <Entry key={c.course_id} course={c} isNew={baselineIds !== null && !baselineIds.includes(c.course_id)}
              tiles={tiles} effective={effective} onFeedback={onFeedback} />
          ))}
        </ol>
      )}
    </section>
  )
}
