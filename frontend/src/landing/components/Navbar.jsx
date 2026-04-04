export default function Navbar({ onTryDemo }) {
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
          <span className="text-[#F2F2F2] text-[15px] tracking-wide font-semibold">OptiMesh</span>
        </div>

        <div className="flex items-center px-1 py-1 bg-[#0A0A0A] border border-white/5 rounded-[14px]">
          <a
            href="#features"
            className="px-5 py-[6px] text-[14px] text-[#F2F2F2] font-semibold rounded-[10px] transition-colors"
          >
            Features
          </a>
          <a
            href="#about"
            className="px-5 py-[6px] text-[14px] text-[#666666] hover:text-[#F2F2F2] font-medium rounded-[10px] transition-colors"
          >
            How It Works
          </a>
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
          <span className="text-[#F2F2F2] text-[14px] font-semibold">Try Demo</span>
          <svg className="w-2 h-2 text-[#F2F2F2] fill-current" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z" />
          </svg>
        </button>
      </div>
    </nav>
  )
}
