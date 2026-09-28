import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from './api'
import TopBar from './components/TopBar'
import { useRoute } from './hooks/useRoute'
import { useTheme } from './hooks/useTheme'
import Discover from './pages/Discover'
import Evaluation from './pages/Evaluation'
import type { CatalogInfo, Health } from './types'
import './App.css'

export type ServiceState =
  | { kind: 'loading' }
  | { kind: 'down'; message: string }
  | { kind: 'ready'; health: Health; catalog: CatalogInfo | null }

export default function App() {
  const route = useRoute()
  const theme = useTheme()
  const [service, setService] = useState<ServiceState>({ kind: 'loading' })

  const connect = useCallback(async () => {
    setService({ kind: 'loading' })
    try {
      const health = await api.health()
      if (health.status === 'unavailable') {
        setService({ kind: 'down', message: health.message })
        return
      }
      const catalog = await api.catalog().catch(() => null)
      setService({ kind: 'ready', health, catalog })
    } catch (err) {
      setService({ kind: 'down', message: err instanceof ApiError ? err.message : 'The course service did not answer.' })
    }
  }, [])

  useEffect(() => {
    void connect()
  }, [connect])

  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <TopBar route={route} service={service} theme={theme.effective} onToggleTheme={theme.toggle} />
      <main id="main" className="shell">
        {route === 'discover' ? <Discover service={service} onRetry={connect} /> : <Evaluation service={service} />}
      </main>
    </>
  )
}
