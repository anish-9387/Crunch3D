import { useState } from 'react'

export default function FeatureCards() {
  const [activeIndex, setActiveIndex] = useState(1)

  const features = [
    'Automated Mesh Processing: Analyzes high-poly models and prepares them for intelligent workflows.',
    'Feature-Aware Simplification: Preserves sharp edges, boundaries, and critical geometry.',
    'Multi-Level LOD Generation: Generates optimized versions for real-time rendering in games.',
  ]

  return (
    <section
      id="features"
      className="w-full mx-auto mt-6 md:mt-10 mb-8 relative z-10 flex flex-col lg:flex-row justify-center gap-3 h-[110px] px-2 md:px-0"
    >
      {features.map((text, idx) => {
        const isActive = activeIndex === idx

        return (
          <div
            key={idx}
            onClick={() => setActiveIndex(idx)}
            className={`relative flex items-center p-6 rounded-[20px] cursor-pointer transition-all duration-[600ms] ease-[cubic-bezier(0.25,1,0.5,1)] overflow-hidden flex-shrink-0 ${
              isActive
                ? 'bg-[#FF0F0F] lg:w-[65%] w-full shadow-[0_0_40px_-5px_rgba(255,15,15,0.4)]'
                : 'bg-[#0D0D0D] border border-white/5 lg:w-[17.5%] w-full hover:bg-[#151515]'
            }`}
          >
            <div className={`flex items-center ${isActive ? 'mr-6' : 'justify-center w-full'}`}>
              {[0, 1, 2].map((circleIdx) => {
                const isThisCardCircleActive = circleIdx === idx

                if (isActive) {
                  return (
                    <div
                      key={circleIdx}
                      className={`w-10 h-10 rounded-full flex items-center justify-center text-[14px] tracking-wide -ml-2.5 first:ml-0 border transition-all duration-500 ${
                        isThisCardCircleActive
                          ? 'bg-[#0A0A0A] border-[#0A0A0A] text-white z-20 font-semibold'
                          : 'bg-transparent border-[#B30000] text-[#800000] z-10 font-bold'
                      }`}
                    >
                      {circleIdx + 1}
                    </div>
                  )
                }

                return (
                  <div
                    key={circleIdx}
                    className={`w-10 h-10 rounded-full flex items-center justify-center text-[14px] -ml-2.5 first:ml-0 border transition-all duration-500 ${
                      isThisCardCircleActive
                        ? 'bg-[#FF0F0F] border-[#FF0F0F] text-[#660000] z-20 font-bold'
                        : 'bg-transparent border-white/10 text-transparent z-10'
                    }`}
                  >
                    {isThisCardCircleActive ? circleIdx + 1 : ''}
                  </div>
                )
              })}
            </div>

            <div
              className={`flex-1 flex items-center justify-between transition-all duration-500 min-w-0 ${
                isActive
                  ? 'opacity-100 translate-x-0 delay-150'
                  : 'opacity-0 translate-x-4 pointer-events-none hidden lg:flex absolute'
              }`}
            >
              <p className="text-[#1A0505] font-semibold text-[14px] md:text-[15px] leading-snug truncate lg:whitespace-normal pr-4">
                {text}
              </p>
              <svg
                className="w-5 h-5 text-[#1A0505] flex-shrink-0"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M7 17L17 7" />
                <path d="M7 7h10v10" />
              </svg>
            </div>
          </div>
        )
      })}
    </section>
  )
}
