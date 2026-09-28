import { Moon, Sun } from '@phosphor-icons/react'
import type { ServiceState } from '../App'
import type { Route } from '../hooks/useRoute'
import './TopBar.css'

interface Props {
  route: Route
  service: ServiceState
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}

function ServiceStatus({ service }: { service: ServiceState }) {
  if (service.kind === 'loading') {
    return <span className="status" data-state="unknown"><span className="mark" data-state="unknown" aria-hidden="true" />Connecting</span>
  }
  if (service.kind === 'down') {
    return <span className="status" data-state="missing"><span className="mark" data-state="missing" aria-hidden="true" />Service offline</span>
  }
  const { health } = service
  const degraded = health.mode === 'keyword_only'
  return (
    <span className="status" title={health.message}>
      <span className="mark" data-state={degraded ? 'simulated' : 'known'} aria-hidden="true" />
      <span className="num">{health.course_count.toLocaleString()}</span>&nbsp;courses
      <span className="status-sep" aria-hidden="true" />
      {degraded ? 'Keyword search only' : 'Hybrid search ready'}
    </span>
  )
}

export default function TopBar({ route, service, theme, onToggleTheme }: Props) {
  return (
    <header className="topbar">
      <a className="brand" href="#/discover" aria-label="Prior, University Course Finder, go to Discover">
        <span className="brand-tile" aria-hidden="true">Pr</span>
        <span className="brand-name">Prior</span>
        <span className="brand-desc">University Course Finder</span>
      </a>
      <nav className="tabs" aria-label="Screens">
        <a href="#/discover" aria-current={route === 'discover' ? 'page' : undefined}>Discover</a>
        <a href="#/evaluation" aria-current={route === 'evaluation' ? 'page' : undefined}>Evaluation</a>
      </nav>
      <div className="topbar-end">
        <ServiceStatus service={service} />
        <button
          type="button"
          className="theme-toggle"
          onClick={onToggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          title={theme === 'dark' ? 'Light theme (best on projectors)' : 'Dark theme'}
        >
          {theme === 'dark' ? <Sun size={20} weight="bold" /> : <Moon size={20} weight="bold" />}
        </button>
      </div>
    </header>
  )
}
