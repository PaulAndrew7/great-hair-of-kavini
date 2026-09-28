import { useEffect, useState } from 'react'

export type ThemeChoice = 'light' | 'dark' | 'system'
const KEY = 'prior.theme'

function read(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

/** Per-viewer theme preference. Projectors read best in light, so the toggle is one press away. */
export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(read)

  useEffect(() => {
    const root = document.documentElement
    if (choice === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', choice)
    try {
      if (choice === 'system') localStorage.removeItem(KEY)
      else localStorage.setItem(KEY, choice)
    } catch {
      /* storage unavailable: preference lasts for this visit only */
    }
  }, [choice])

  const effective = (): 'light' | 'dark' =>
    choice !== 'system' ? choice : window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'

  const current = effective()
  const toggle = () => setChoice(current === 'dark' ? 'light' : 'dark')

  return { choice, effective: current, toggle }
}
