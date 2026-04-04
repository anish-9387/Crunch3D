import { useCallback, useEffect, useState } from 'react'
import DemoApp from './DemoApp'
import LandingPage from './landing/LandingPage'

const DEMO_PATH = '/demo'

function normalizePath(pathname) {
  if (!pathname) return '/'
  if (pathname.length > 1 && pathname.endsWith('/')) {
    return pathname.slice(0, -1)
  }
  return pathname
}

export default function App() {
  const [path, setPath] = useState(() => normalizePath(window.location.pathname))

  useEffect(() => {
    const handlePopState = () => setPath(normalizePath(window.location.pathname))
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  useEffect(() => {
    if (path !== '/' && path !== DEMO_PATH) {
      window.history.replaceState({}, '', '/')
      setPath('/')
    }
  }, [path])

  useEffect(() => {
    document.body.setAttribute('data-view', path === DEMO_PATH ? 'demo' : 'landing')
  }, [path])

  useEffect(
    () => () => {
      document.body.removeAttribute('data-view')
    },
    [],
  )

  const openDemo = useCallback(() => {
    if (path === DEMO_PATH) return
    window.history.pushState({}, '', DEMO_PATH)
    setPath(DEMO_PATH)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [path])

  if (path === DEMO_PATH) {
    return <DemoApp />
  }

  return <LandingPage onTryDemo={openDemo} onGenerateLods={openDemo} />
}
