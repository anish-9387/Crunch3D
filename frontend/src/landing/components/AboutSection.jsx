export default function AboutSection({ onGenerateLods }) {
  return (
    <section id="about" className="w-full flex flex-col items-start justify-center pt-20 pb-16 relative z-10 px-4 md:px-0">
      <div className="flex items-center gap-4 mb-8">
        <span className="text-[#F2F2F2] text-[16px] md:text-[18px] font-medium tracking-tight px-1">01</span>
        <div className="flex items-center gap-2 px-5 py-2.5 bg-[#E4F1F1] rounded-[14px]">
          <span className="text-[#0A0A0A] text-[14px] md:text-[15px] font-semibold tracking-wide">About</span>
          <svg
            className="w-4 h-4 text-[#0A0A0A]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 2v20M17 5l-10 14M22 12H2M20 17L4 7" />
          </svg>
          <span className="text-[#0A0A0A] text-[14px] md:text-[15px] font-semibold tracking-wide">OptiMesh</span>
        </div>
      </div>

      <div className="w-full max-w-[1000px] text-left mb-20 px-1">
        <h2 className="text-[32px] md:text-[46px] lg:text-[54px] font-medium tracking-tight leading-[1.15] text-[#F2F2F2]">
          OptiMesh transforms heavy 3D models into optimized real-time assets for modern graphics workflows.
        </h2>
        <h3 className="text-[20px] md:text-[28px] lg:text-[34px] font-medium tracking-tight leading-[1.2] text-[#888888] mt-4">
          Designed for developers, artists, and real-time rendering systems.
        </h3>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 w-full lg:items-start">
        <div className="flex flex-col gap-6 text-left w-full relative">
          <div className="w-full aspect-square md:aspect-[4/4.5] bg-[#DDEBEB] rounded-[32px] overflow-hidden relative flex items-center justify-center p-6 border border-white/5">
            <div className="absolute inset-0 flex items-center justify-center opacity-50">
              <div className="w-[80%] h-[80%] rounded-full border-[1px] border-[#8BA7A7]" />
            </div>

            <div className="relative flex items-center gap-2">
              <div className="w-20 md:w-28 h-12 bg-[#FF3B3B] rounded-r-full rounded-l-[10px] flex items-center justify-center shadow-[0_4px_20px_rgba(255,59,59,0.3)]">
                <span className="text-[#200505] font-semibold tracking-wide text-[14px]">Cleanup</span>
              </div>
              <div className="flex-1 min-w-[60px] h-[2px] bg-[#FF3B3B]" />
              <div className="w-16 h-16 rounded-full border-2 border-[#FF3B3B] text-[#FF3B3B] flex items-center justify-center bg-white/20 backdrop-blur-sm">
                <svg
                  className="w-6 h-6"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                  <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
                  <line x1="12" y1="22.08" x2="12" y2="12" />
                </svg>
              </div>
            </div>

            <svg
              className="absolute top-10 right-10 w-12 h-12 text-[#FF3B3B] opacity-80"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 2v20M17 5l-10 14M22 12H2M20 17L4 7" />
            </svg>
          </div>

          <div className="flex flex-col gap-2 px-1">
            <h3 className="text-[#F2F2F2] text-[22px] font-semibold tracking-tight">Mesh Preprocessing</h3>
            <p className="text-[#888888] text-[15px] leading-relaxed">
              Automatically cleans and prepares complex 3D meshes before optimization.
            </p>
            <p className="text-[#666666] text-[13px] leading-relaxed mt-1">
              Removes duplicate vertices, fixes topology issues, and validates geometry.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-6 text-left w-full lg:-mt-10 relative">
          <button
            type="button"
            onClick={onGenerateLods}
            className="w-full bg-[#FF3B3B] rounded-[24px] px-6 py-5 flex items-center justify-between cursor-pointer shadow-[0_0_40px_-10px_rgba(255,59,59,0.5)] hover:bg-[#E63535] transition-colors relative z-20"
          >
            <span className="text-[#1A0505] text-[15px] font-semibold tracking-wider">GENERATE LODs</span>
            <div className="w-8 h-8 bg-[#1A0505] rounded-full flex items-center justify-center">
              <svg
                className="w-4 h-4 text-[#F2F2F2]"
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
          </button>

          <div className="w-full aspect-square md:aspect-[4/4.5] bg-[#E3F2F2] rounded-[32px] overflow-hidden relative flex items-center justify-center border border-white/5 p-6">
            <div className="relative flex flex-col items-center justify-center gap-6 z-10 w-full h-full">
              <div className="relative w-32 h-32 flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border border-[#9AC5C5]" />
                <div className="absolute inset-4 rounded-full border border-[#9AC5C5] opacity-50" />

                <svg
                  className="w-12 h-12 text-[#FF3B3B] z-10"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 2v20M17 5l-10 14M22 12H2M20 17L4 7" />
                </svg>
              </div>

              <div className="px-5 py-2.5 rounded-full border border-[#FF3B3B]/30 text-[#FF3B3B] bg-white/40 backdrop-blur-md shadow-sm">
                <span className="text-[14px] font-medium tracking-wide">Details Preserved!</span>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-2 px-1">
            <h3 className="text-[#F2F2F2] text-[22px] font-semibold tracking-tight">Feature-Aware Simplification</h3>
            <p className="text-[#888888] text-[15px] leading-relaxed">
              Detects important edges and preserves visual detail during polygon reduction.
            </p>
            <p className="text-[#666666] text-[13px] leading-relaxed mt-1">
              Uses curvature and boundary detection to maintain mesh quality.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-6 text-left w-full relative">
          <div className="w-full aspect-square md:aspect-[4/4.5] bg-[#DCEBEC] rounded-[32px] overflow-hidden relative flex items-center justify-center p-6 border border-white/5">
            <div className="relative w-full h-full flex items-center justify-center">
              <div className="absolute top-4 right-4 w-28 h-28 opacity-80 animate-[spin_10s_linear_infinite] pointer-events-none">
                <svg viewBox="0 0 100 100">
                  <path
                    d="M 50, 50 m -35, 0 a 35,35 0 1,1 70,0 a 35,35 0 1,1 -70,0"
                    fill="transparent"
                    id="circleTextPath"
                  />
                  <text fontSize="8" fill="#719898" letterSpacing="1.5" fontWeight="600">
                    <textPath href="#circleTextPath">GENERATE OPTIMIZE GENERATE OPTIMIZE</textPath>
                  </text>
                </svg>
              </div>

              <svg
                className="absolute top-12 right-12 w-10 h-10 text-[#FF3B3B]"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 2v20M17 5l-10 14M22 12H2M20 17L4 7" />
              </svg>

              <div className="absolute bottom-6 left-6 flex flex-col gap-3">
                <div className="w-32 h-10 rounded-full bg-[#B5CBCB] flex items-center justify-center border border-white/20 shadow-sm transform -rotate-12 translate-y-4 translate-x-4 opacity-80">
                  <span className="text-[#4C6666] font-medium text-[13px] uppercase tracking-wide">LOD 2</span>
                </div>
                <div className="w-32 h-10 rounded-full bg-[#AAC4C4] flex items-center justify-center border border-white/20 shadow-sm transform rotate-6 translate-x-12 opacity-90 z-10">
                  <span className="text-[#4C6666] font-medium text-[13px] uppercase tracking-wide">LOD 1</span>
                </div>
                <div className="w-32 h-10 rounded-full bg-[#9EB9B9] flex items-center justify-center border border-white/20 shadow-sm transform -rotate-3 z-20">
                  <span className="text-[#3A4D4D] font-semibold text-[13px] uppercase tracking-wide">LOD 0</span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-2 px-1">
            <h3 className="text-[#F2F2F2] text-[22px] font-semibold tracking-tight">Multi-Level LOD Generation</h3>
            <p className="text-[#888888] text-[15px] leading-relaxed">
              Automatically creates multiple optimized versions of the same 3D model.
            </p>
            <div className="flex flex-col gap-1 mt-1 text-[#666666] text-[13px]">
              <span className="font-semibold text-[#888888]">LOD0 → Original</span>
              <span>LOD1 → 50%</span>
              <span>LOD2 → 25%</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
