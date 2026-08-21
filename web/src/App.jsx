import { useCallback, useEffect, useState } from 'react'
import DemoApp from './DemoApp'
import LandingPage from './landing/LandingPage'
import Preloader from './components/Preloader'

const DEMO_PATH = '/demo'
const MOBILE_LAST_PATH_KEY = 'crunch3d-mobile-last-path'

function normalizePath(pathname) {
  if (!pathname) return '/'
  if (pathname.length > 1 && pathname.endsWith('/')) {
    return pathname.slice(0, -1)
  }
  return pathname
}

function isMobileViewport() {
  return typeof window !== 'undefined' && window.matchMedia?.('(max-width: 640px)').matches
}

function getInitialPath() {
  const currentPath = normalizePath(window.location.pathname)
  if (currentPath !== '/' || !isMobileViewport()) return currentPath

  const savedPath = window.localStorage.getItem(MOBILE_LAST_PATH_KEY)
  return savedPath === DEMO_PATH ? DEMO_PATH : '/'
}

export default function App() {
  const [path, setPath] = useState(getInitialPath)
  const [loaded, setLoaded] = useState(false)

  const handlePreloaderComplete = useCallback(() => {
    // Remove the inline HTML preloader from the DOM
    const inlinePreloader = document.getElementById('preloader-inline')
    if (inlinePreloader) {
      inlinePreloader.classList.add('hidden')
      setTimeout(() => inlinePreloader.remove(), 600)
    }
    setLoaded(true)
  }, [])

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

  useEffect(() => {
    if (isMobileViewport()) {
      if (path === DEMO_PATH && normalizePath(window.location.pathname) !== DEMO_PATH) {
        window.history.replaceState({}, '', DEMO_PATH)
      }
      window.localStorage.setItem(MOBILE_LAST_PATH_KEY, path)
    }
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

  const openHome = useCallback(() => {
    if (path === '/') return
    window.history.pushState({}, '', '/')
    setPath('/')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [path])

  return (
    <>
      <Preloader onComplete={handlePreloaderComplete} />

      {loaded && (
        path === DEMO_PATH
          ? <DemoApp onBackToHome={openHome} />
          : <LandingPage onTryDemo={openDemo} onGenerateLods={openDemo} />
      )}
    </>
  )
}

