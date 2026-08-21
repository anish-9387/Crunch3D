import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * Premium fullscreen preloader that blocks interaction until the page shell
 * (fonts, stylesheets, images above the fold) has fully loaded.
 *
 * Lifecycle:
 *  1. Immediately visible (matches the inline preloader in index.html).
 *  2. Monitors document readyState + font loading + a minimum display time.
 *  3. Once ready, plays a smooth exit animation and then unmounts.
 */
export default function Preloader({ onComplete }) {
  const [progress, setProgress] = useState(0)
  const [exiting, setExiting] = useState(false)
  const [done, setDone] = useState(false)
  const rafRef = useRef(null)
  const startRef = useRef(Date.now())

  // Minimum time the preloader stays visible (ms) to prevent jarring flash
  const MIN_DISPLAY_MS = 1800
  // Exit animation duration (must match CSS transition below)
  const EXIT_MS = 700

  const finishLoading = useCallback(() => {
    const elapsed = Date.now() - startRef.current
    const remaining = Math.max(0, MIN_DISPLAY_MS - elapsed)

    setTimeout(() => {
      setProgress(100)
      // Small delay so the bar visually fills to 100% before exit
      setTimeout(() => {
        setExiting(true)
        setTimeout(() => {
          setDone(true)
          onComplete?.()
        }, EXIT_MS)
      }, 300)
    }, remaining)
  }, [onComplete])

  useEffect(() => {
    let cancelled = false

    // Synthetic progress that eases toward ~90% while we wait for real load
    const tick = () => {
      if (cancelled) return
      setProgress((prev) => {
        if (prev >= 90) return prev
        // Slow down as we approach 90
        const delta = (90 - prev) * 0.02
        return Math.min(prev + Math.max(delta, 0.1), 90)
      })
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)

    // Wait for both document + fonts
    const waitForLoad = async () => {
      // Wait for fonts
      if (document.fonts?.ready) {
        await document.fonts.ready
      }

      // Wait for document ready state
      if (document.readyState !== 'complete') {
        await new Promise((resolve) => {
          window.addEventListener('load', resolve, { once: true })
        })
      }

      if (!cancelled) finishLoading()
    }

    waitForLoad()

    return () => {
      cancelled = true
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [finishLoading])

  if (done) return null

  return (
    <div
      id="preloader"
      className={`preloader${exiting ? ' preloader--exit' : ''}`}
      aria-live="polite"
      aria-label="Loading Crunch3D"
    >
      {/* Animated background grid */}
      <div className="preloader__grid" />

      {/* Central content */}
      <div className="preloader__content">
        {/* Wireframe cube animation */}
        <div className="preloader__cube-wrap">
          <div className="preloader__cube">
            <div className="preloader__face preloader__face--front" />
            <div className="preloader__face preloader__face--back" />
            <div className="preloader__face preloader__face--left" />
            <div className="preloader__face preloader__face--right" />
            <div className="preloader__face preloader__face--top" />
            <div className="preloader__face preloader__face--bottom" />
          </div>
        </div>

        {/* Brand */}
        <div className="preloader__brand">
          <svg
            className="preloader__logo"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 4v16" />
            <path d="M20 12H4" />
            <path d="M17.657 6.343l-11.314 11.314" />
            <path d="M6.343 6.343l11.314 11.314" />
          </svg>
          <span className="preloader__name">Crunch3d</span>
        </div>

        {/* Progress bar */}
        <div className="preloader__bar-track">
          <div
            className="preloader__bar-fill"
            style={{ width: `${progress}%` }}
          />
        </div>

        <span className="preloader__status">
          {progress < 100 ? 'Loading assets…' : 'Ready'}
        </span>
      </div>

      {/* Scan lines for CRT / tech feel */}
      <div className="preloader__scanlines" />
    </div>
  )
}
