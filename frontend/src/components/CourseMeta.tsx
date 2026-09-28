import { Star } from '@phosphor-icons/react'
import type { CourseCard } from '../types'
import './CourseMeta.css'

/** One metadata line. Unknown values are named as unknown, never defaulted. */
export default function CourseMeta({ course }: { course: CourseCard }) {
  return (
    <ul className="meta" aria-label="Course details">
      <li>{course.organization ?? 'Organization not listed'}</li>
      <li>{course.difficulty === 'Unknown' ? 'Level not stated' : course.difficulty}</li>
      <li className="num">
        {course.rating !== null ? (
          <>
            <Star size={14} weight="fill" aria-hidden="true" />
            <span className="visually-hidden">Rated </span>
            {course.rating.toFixed(1)}
            {course.num_reviews !== null && <span className="meta-dim"> ({course.num_reviews.toLocaleString()} reviews)</span>}
          </>
        ) : 'No rating'}
      </li>
      {course.course_type && course.course_type !== 'Course' && <li>{course.course_type}</li>}
    </ul>
  )
}
