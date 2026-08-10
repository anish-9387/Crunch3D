import Hero3DComparison from './Hero3DComparison'

export default function HeroSection({ onTryDemo }) {
  return (
    <section className="relative w-full flex flex-col lg:flex-row items-stretch justify-between pt-6 md:pt-10 pb-6 z-10 flex-1 lg:h-[90vh] gap-8 px-4 lg:px-12 max-w-[1600px] mx-auto">
      
      {/* LEFT COLUMN - TEXT & STATS */}
      <div className="w-full lg:w-1/2 flex flex-col justify-center text-left relative z-10 drop-shadow-md">
        
        <h1 className="text-[44px] md:text-[60px] lg:text-[70px] xl:text-[80px] tracking-tight leading-[1] mb-6 text-[#F2F2F2]">
          Next level of <br className="hidden md:block" />
          <span className="inline-flex items-center flex-wrap">
            <svg
              className="w-10 h-10 lg:w-[60px] lg:h-[60px] text-[#FF3B3B] mr-2 lg:mr-4 drop-shadow-md"
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
            <span className="text-[#FF3B3B] drop-shadow-md">mesh optimization</span>
          </span>
        </h1>

        <div className="grid grid-cols-2 gap-4 lg:gap-6 mb-8 opacity-90 max-w-[500px]">
          <div>
            <div className="text-[24px] xl:text-[30px] font-medium tracking-tight text-[#F2F2F2] mb-1 leading-tight">
              500k+
            </div>
            <div className="text-[12px] text-[#888] font-medium tracking-wide">Vertices Processed</div>
          </div>
          
          <div>
            <div className="text-[24px] xl:text-[30px] font-medium tracking-tight text-[#F2F2F2] mb-1 leading-tight">
              Up to 65%
            </div>
            <div className="text-[12px] text-[#888] font-medium tracking-wide">Polygon Reduction</div>
          </div>

          <div>
            <div className="text-[24px] xl:text-[30px] font-medium tracking-tight text-[#F2F2F2] mb-1 leading-tight">
              4
            </div>
            <div className="text-[12px] text-[#888] font-medium tracking-wide">LOD Levels Generated</div>
          </div>

          <div>
            <div className="text-[24px] xl:text-[30px] font-medium tracking-tight text-[#F2F2F2] mb-1 leading-tight">
              Real-Time
            </div>
            <div className="text-[12px] text-[#888] font-medium tracking-wide">Ready Assets</div>
          </div>
        </div>

        <button
          type="button"
          onClick={onTryDemo}
          className="group relative flex items-center justify-center w-[64px] h-[64px] rounded-full border border-white/10 bg-[#070707] hover:bg-[#FF3B3B] hover:border-[#FF3B3B] transition-all duration-300 shadow-[0_0_20px_-5px_rgba(255,255,255,0.1)] hover:shadow-[0_0_20px_rgba(255,59,59,0.4)]"
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

      {/* RIGHT COLUMN - 3D COMPARISON BOX */}
      <div className="w-full lg:w-1/2 relative min-h-[400px] lg:min-h-full rounded-[2rem] overflow-hidden border border-white/10 bg-[#050505] shadow-[0_0_40px_-10px_rgba(255,59,59,0.15)] flex-1">
        <Hero3DComparison />
      </div>

    </section>
  )
}
