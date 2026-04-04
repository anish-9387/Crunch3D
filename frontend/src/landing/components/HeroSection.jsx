const MeshSphere = () => {
  return (
    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] md:w-[700px] md:h-[700px] opacity-25 pointer-events-none z-0">
      <svg viewBox="0 0 100 100" className="w-full h-full animate-[spin_60s_linear_infinite]">
        <g stroke="#FF3B3B" strokeWidth="0.2" fill="none">
          <circle cx="50" cy="50" r="45" opacity="0.3" />
          <ellipse cx="50" cy="50" rx="45" ry="15" opacity="0.3" />
          <ellipse cx="50" cy="50" rx="15" ry="45" opacity="0.3" />
          <path d="M 50 5 L 82 28 L 82 72 L 50 95 L 18 72 L 18 28 Z" opacity="0.5" />
          <path d="M 50 5 L 65 50 L 50 95 L 35 50 Z" opacity="0.4" />
          <path d="M 18 28 L 82 72 M 18 72 L 82 28" opacity="0.4" />
          <g fill="#FF3B3B" stroke="none">
            <circle cx="50" cy="5" r="1" />
            <circle cx="82" cy="28" r="1" />
            <circle cx="82" cy="72" r="1" />
            <circle cx="50" cy="95" r="1" />
            <circle cx="18" cy="72" r="1" />
            <circle cx="18" cy="28" r="1" />
            <circle cx="50" cy="50" r="1.5" />
            <circle cx="65" cy="50" r="1" />
            <circle cx="35" cy="50" r="1" />
            <circle cx="50" cy="27.5" r="1" />
            <circle cx="50" cy="72.5" r="1" />
          </g>
        </g>
      </svg>
    </div>
  )
}

export default function HeroSection({ onTryDemo }) {
  return (
    <section className="relative w-full flex flex-col items-center justify-center pt-10 md:pt-16 pb-12 text-center z-10 flex-1 min-h-[460px] lg:min-h-[50vh]">
      <MeshSphere />

      <div className="hidden lg:grid grid-cols-[1fr_auto_1fr] items-center gap-6 w-full mx-auto relative z-10 mt-12 px-2 md:px-0">
        <div className="flex flex-col text-left gap-10 opacity-90 pl-4">
          <div>
            <div className="text-[28px] xl:text-[34px] font-medium tracking-tight text-[#F2F2F2] mb-1 leading-tight">
              500k+
            </div>
            <div className="text-[13px] text-[#888] font-medium tracking-wide">Vertices Processed</div>
          </div>
          <div className="w-[30px] h-[1px] bg-white/20" />
          <div>
            <div className="text-[28px] xl:text-[34px] font-medium tracking-tight text-[#F2F2F2] mb-1 leading-tight">
              Up to 65%
            </div>
            <div className="text-[13px] text-[#888] font-medium tracking-wide">Polygon Reduction</div>
          </div>
        </div>

        <div className="flex flex-col items-center justify-center w-full max-w-[850px] mx-auto">
          <h1 className="text-[44px] md:text-[68px] lg:text-[76px] tracking-tight leading-[1] mb-10 text-[#F2F2F2]">
            Next level of <br className="hidden md:block" />
            <span className="whitespace-nowrap inline-flex items-center justify-center">
              <svg
                className="w-10 h-10 lg:w-[68px] lg:h-[68px] text-[#FF3B3B] mx-2"
                aria-hidden="true"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
              >
                <path
                  stroke="currentColor"
                  strokeLinejoin="round"
                  strokeWidth="1.5"
                  d="m17 13 3.4641-2V7L17 5l-3.4641 2v4M17 13l-3.4641-2M17 13v4l-7.00001 4M17 13V9m0 4-7.00001 4m3.53591-6L10.5 12.7348M9.99999 21l-3.4641-2.1318M9.99999 21v-4m-3.4641 2v-.1318m0 0V15L10.5 12.7348m-3.96411 6.1334L3.5 17V5m0 0L7 3l3.5 2m-7 0 2.99999 2M10.5 5v7.7348M10.5 5 6.49999 7M17 9l3.5-2M17 9l-3.5-2M9.99999 17l-3.5-2m0 .5V7"
                />
              </svg>
              <span className="text-[#FF3B3B]">mesh optimization</span>
            </span>
          </h1>

          <button
            type="button"
            onClick={onTryDemo}
            className="group relative flex items-center justify-center w-[76px] h-[76px] rounded-full border border-white/10 bg-[#070707] hover:bg-white/5 hover:border-white/20 transition-all duration-300 shadow-[0_0_20px_-5px_rgba(255,255,255,0.05)]"
          >
            <svg
              className="w-6 h-6 text-[#F2F2F2] group-hover:translate-x-[2px] group-hover:-translate-y-[2px] transition-transform duration-300"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M7 17L17 7" />
              <path d="M7 7h10v10" />
            </svg>
          </button>
        </div>

        <div className="flex flex-col items-end text-right gap-10 opacity-90 pr-4">
          <div>
            <div className="text-[28px] xl:text-[34px] font-medium tracking-tight text-[#F2F2F2] mb-1 leading-tight">
              4
            </div>
            <div className="text-[13px] text-[#888] font-medium tracking-wide">LOD Levels Generated</div>
          </div>
          <div className="w-[30px] h-[1px] bg-white/20 ml-auto" />
          <div>
            <div className="text-[28px] xl:text-[34px] font-medium tracking-tight text-[#F2F2F2] mb-1 leading-tight">
              Real-Time
            </div>
            <div className="text-[13px] text-[#888] font-medium tracking-wide">Ready Assets</div>
          </div>
        </div>
      </div>

      <div className="lg:hidden w-full flex flex-col items-center relative z-10 px-4">
        <h1 className="text-[44px] md:text-[68px] tracking-tight leading-[1] mb-10 text-[#F2F2F2]">
          Next level of <br />
          <span className="whitespace-nowrap inline-flex items-center justify-center">
            <svg
              className="w-10 h-10 md:w-[60px] md:h-[60px] text-[#FF3B3B] mx-2"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
            >
              <path
                stroke="currentColor"
                strokeLinejoin="round"
                strokeWidth="1.5"
                d="m17 13 3.4641-2V7L17 5l-3.4641 2v4M17 13l-3.4641-2M17 13v4l-7.00001 4M17 13V9m0 4-7.00001 4m3.53591-6L10.5 12.7348M9.99999 21l-3.4641-2.1318M9.99999 21v-4m-3.4641 2v-.1318m0 0V15L10.5 12.7348m-3.96411 6.1334L3.5 17V5m0 0L7 3l3.5 2m-7 0 2.99999 2M10.5 5v7.7348M10.5 5 6.49999 7M17 9l3.5-2M17 9l-3.5-2M9.99999 17l-3.5-2m0 .5V7"
              />
            </svg>
            <span className="text-[#FF3B3B]">mesh optimization</span>
          </span>
        </h1>

        <button
          type="button"
          onClick={onTryDemo}
          className="group relative flex items-center justify-center w-[76px] h-[76px] rounded-full border border-white/10 bg-[#070707] hover:bg-white/5 hover:border-white/20 transition-all duration-300 shadow-[0_0_20px_-5px_rgba(255,255,255,0.05)]"
        >
          <svg
            className="w-6 h-6 text-[#F2F2F2] group-hover:translate-x-[2px] group-hover:-translate-y-[2px] transition-transform duration-300"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M7 17L17 7" />
            <path d="M7 7h10v10" />
          </svg>
        </button>

        <div className="w-full flex flex-row justify-between items-start mt-16 text-left">
          <div className="flex flex-col gap-6 w-1/2">
            <div>
              <div className="text-[26px] font-medium tracking-tight text-[#F2F2F2] mb-1 leading-tight">500k+</div>
              <div className="text-[12px] text-[#888]">Vertices Processed</div>
            </div>
            <div className="w-[30px] h-[1px] bg-white/20" />
            <div>
              <div className="text-[26px] font-medium tracking-tight text-[#F2F2F2] mb-1 leading-tight">Up to 65%</div>
              <div className="text-[12px] text-[#888]">Polygon Reduction</div>
            </div>
          </div>
          <div className="flex flex-col gap-6 w-1/2 text-right items-end">
            <div>
              <div className="text-[26px] font-medium tracking-tight text-[#F2F2F2] mb-1 leading-tight">4</div>
              <div className="text-[12px] text-[#888]">LOD Levels Generated</div>
            </div>
            <div className="w-[30px] h-[1px] bg-white/20 ml-auto" />
            <div>
              <div className="text-[26px] font-medium tracking-tight text-[#F2F2F2] mb-1 leading-tight">Real-Time</div>
              <div className="text-[12px] text-[#888]">Ready Assets</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
