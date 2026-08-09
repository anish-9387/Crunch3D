const NAV_LINKS = [
  { label: 'Features', hash: '#features' },
  { label: 'How It Works', hash: '#about' },
]

/**
 * Shared top navigation for both the landing page and the demo.
 *
 * `active` controls which context we are in: on the landing page the section
 * links are in-page anchors, on the demo they point back at the landing page
 * (`/#features`) so they still resolve. The CTA is relabelled per context via
 * `ctaLabel` — "Try Demo" on landing, "Back to Home" on the demo.
 */
export default function Navbar({ onTryDemo, ctaLabel = 'Try Demo', active = 'landing' }) {
  const isDemo = active === 'demo'
  const href = (hash) => (isDemo ? `/${hash}` : hash)

  return (
    <nav className="flex justify-center items-center w-full z-50">
      <div className="flex items-center gap-1.5 flex-wrap justify-center">
        <div className="flex items-center gap-2.5 px-6 py-[10px] bg-[#0A0A0A] border border-white/5 rounded-[14px] cursor-pointer hover:bg-[#111111] transition-colors">
          <svg
            className="w-[18px] h-[18px] text-white"
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
          <span className="text-[#F2F2F2] text-[15px] tracking-wide font-semibold">Crunch3d</span>
        </div>

        <div className="flex items-center px-1 py-1 bg-[#0A0A0A] border border-white/5 rounded-[14px]">
          {NAV_LINKS.map((link, idx) => {
            // On landing the first section is the one in view by default; on the
            // demo no section link is current, so none is highlighted.
            const isCurrent = !isDemo && idx === 0
            return (
              <a
                key={link.label}
                href={href(link.hash)}
                className={`px-5 py-[6px] text-[14px] rounded-[10px] transition-colors ${
                  isCurrent
                    ? 'text-[#F2F2F2] font-semibold'
                    : 'text-[#666666] hover:text-[#F2F2F2] font-medium'
                }`}
              >
                {link.label}
              </a>
            )
          })}
          <a
            href="#"
            className="px-5 py-[6px] text-[14px] text-[#666666] hover:text-[#F2F2F2] font-medium rounded-[10px] transition-colors"
          >
            GitHub
          </a>
        </div>

        <button
          type="button"
          className="flex items-center gap-2 px-5 py-[10px] bg-[#0A0A0A] border border-white/5 rounded-[14px] cursor-pointer hover:bg-[#111111] transition-colors"
          onClick={onTryDemo}
        >
          <span className="text-[#F2F2F2] text-[14px] font-semibold">{ctaLabel}</span>
          <svg className="w-2 h-2 text-[#F2F2F2] fill-current" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z" />
          </svg>
        </button>
      </div>
    </nav>
  )
}
