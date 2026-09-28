import { useEffect, useState } from 'react'

export type Route = 'discover' | 'evaluation'

function parse(): Route {
  return window.location.hash.startsWith('#/evaluation') ? 'evaluation' : 'discover'
}

/** Two screens only; the hash keeps them linkable without a router dependency. */
export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(parse)
  useEffect(() => {
    const onHash = () => {
      setRoute(parse())
      window.scrollTo({ top: 0 })
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  return route
}
