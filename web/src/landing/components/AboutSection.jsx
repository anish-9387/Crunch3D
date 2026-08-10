export default function AboutSection({ onGenerateLods }) {
  return (
    <section id="about" className="w-full flex flex-col items-center justify-center pt-24 pb-20 relative z-10 px-4 md:px-0">
      <div className="w-full max-w-[1200px] flex flex-col items-center">
        
        {/* Header */}
        <div className="flex flex-col items-center text-center mb-16">
          <div className="flex items-center gap-2 px-5 py-2.5 bg-white/5 border border-white/10 rounded-full mb-8">
            <span className="text-[#F2F2F2] text-[14px] font-semibold tracking-wide">Capabilities</span>
          </div>
          <h2 className="text-[36px] md:text-[52px] lg:text-[64px] font-medium tracking-tight leading-[1.1] text-[#F2F2F2] max-w-[900px]">
            Engineered for <span className="text-[#FF3B3B]">performance.</span><br />
            Built for scale.
          </h2>
          <p className="text-[18px] md:text-[20px] text-[#888888] mt-6 max-w-[600px] leading-relaxed">
            Everything you need to seamlessly integrate optimized 3D assets into your real-time graphics workflows.
          </p>
        </div>

        {/* Bento Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 w-full auto-rows-[280px]">
          
          {/* Card 1: LOD Generation (Span 2) */}
          <div className="md:col-span-2 bg-[#0A0A0A] rounded-[32px] overflow-hidden flex flex-col md:flex-row p-8 relative border border-white/5 hover:border-white/10 transition-colors group">
            <div className="absolute inset-0 bg-gradient-to-br from-[#FF3B3B]/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
            <div className="flex flex-col justify-between h-full z-10 w-full md:w-1/2">
              <div>
                <h3 className="text-[#F2F2F2] text-[24px] font-semibold tracking-tight mb-2">Multi-Level LODs</h3>
                <p className="text-[#888888] text-[15px] leading-relaxed">
                  Automatically generate an entire chain of level-of-detail models (LOD0, LOD1, LOD2) from a single high-poly source mesh.
                </p>
              </div>
              <button
                onClick={onGenerateLods}
                className="mt-6 md:mt-0 w-fit flex items-center gap-2 px-6 py-3 bg-[#FF3B3B] text-[#1A0505] rounded-full font-semibold text-[14px] hover:bg-white hover:text-black transition-colors"
              >
                Generate LODs Now
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
              </button>
            </div>
            <div className="hidden md:flex w-1/2 h-full relative items-center justify-center">
              <div className="flex flex-col gap-3 transform rotate-6 translate-x-8">
                <div className="px-8 py-3 rounded-full border border-white/20 bg-white/5 backdrop-blur-md shadow-2xl flex items-center justify-between w-48">
                  <span className="text-white font-medium text-sm">LOD 0</span>
                  <span className="text-white/40 text-xs">100%</span>
                </div>
                <div className="px-8 py-3 rounded-full border border-white/20 bg-white/5 backdrop-blur-md shadow-2xl flex items-center justify-between w-40 translate-x-8">
                  <span className="text-white font-medium text-sm">LOD 1</span>
                  <span className="text-white/40 text-xs">50%</span>
                </div>
                <div className="px-8 py-3 rounded-full border border-white/20 bg-white/5 backdrop-blur-md shadow-2xl flex items-center justify-between w-32 translate-x-16">
                  <span className="text-white font-medium text-sm">LOD 2</span>
                  <span className="text-white/40 text-xs">25%</span>
                </div>
              </div>
            </div>
          </div>

          {/* Card 2: Format Support (Span 1) */}
          <div className="md:col-span-1 bg-[#0A0A0A] rounded-[32px] overflow-hidden flex flex-col p-8 relative border border-white/5 hover:border-white/10 transition-colors group">
            <div className="flex-1 w-full flex items-center justify-center relative mb-6">
               <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-white/10 to-transparent opacity-50" />
               <div className="flex flex-wrap gap-2 justify-center z-10">
                 {['OBJ', 'GLB', 'FBX', 'STL'].map(ext => (
                   <span key={ext} className="px-3 py-1.5 rounded-lg bg-white/10 text-white/80 text-xs font-bold tracking-wider">{ext}</span>
                 ))}
               </div>
            </div>
            <div className="z-10">
              <h3 className="text-[#F2F2F2] text-[20px] font-semibold tracking-tight mb-2">Universal Formats</h3>
              <p className="text-[#888888] text-[14px] leading-relaxed">
                Native support for industry standard 3D formats. No plugins needed.
              </p>
            </div>
          </div>

          {/* Card 3: Feature-Aware (Span 1, RowSpan 2) */}
          <div className="md:col-span-1 md:row-span-2 bg-[#0A0A0A] rounded-[32px] overflow-hidden flex flex-col p-8 relative border border-white/5 hover:border-white/10 transition-colors group">
             <div className="absolute top-0 left-0 w-full h-1/2 bg-gradient-to-b from-[#FF3B3B]/10 to-transparent opacity-50" />
             <div className="flex-1 w-full flex items-center justify-center relative my-8 min-h-[200px]">
                <div className="w-32 h-40 border border-white/20 rounded-[40px] transform -rotate-12 flex items-center justify-center relative overflow-hidden group-hover:rotate-0 transition-transform duration-700">
                   <div className="absolute inset-0 bg-white/5" />
                   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="w-16 h-16 text-[#FF3B3B] opacity-80"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                </div>
             </div>
             <div className="z-10 mt-auto">
              <h3 className="text-[#F2F2F2] text-[24px] font-semibold tracking-tight mb-3">Feature-Aware Simplification</h3>
              <p className="text-[#888888] text-[15px] leading-relaxed">
                Our advanced curvature detection algorithms preserve critical visual details, sharp edges, and boundaries while aggressively reducing polygon counts in flat areas.
              </p>
            </div>
          </div>

          {/* Card 4: Mesh Preprocessing (Span 2) */}
          <div className="md:col-span-2 bg-[#0A0A0A] rounded-[32px] overflow-hidden flex flex-col p-8 relative border border-white/5 hover:border-white/10 transition-colors group">
            <div className="flex-1 w-full flex items-center gap-8 z-10 mb-6 relative">
               <div className="w-16 h-16 rounded-2xl bg-white/10 border border-white/20 flex items-center justify-center">
                 <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-8 h-8 text-white/50"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
               </div>
               <div className="h-[2px] flex-1 bg-gradient-to-r from-white/20 to-[#FF3B3B]/50 relative overflow-hidden">
                 <div className="absolute top-0 left-0 h-full w-1/3 bg-[#FF3B3B] animate-[slide_2s_ease-in-out_infinite]" />
               </div>
               <div className="w-16 h-16 rounded-2xl bg-[#FF3B3B]/10 border border-[#FF3B3B]/30 flex items-center justify-center shadow-[0_0_30px_rgba(255,59,59,0.2)]">
                 <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-8 h-8 text-[#FF3B3B]"><path d="M5 13l4 4L19 7"/></svg>
               </div>
            </div>
            <div className="z-10 mt-auto w-full md:w-2/3">
              <h3 className="text-[#F2F2F2] text-[20px] font-semibold tracking-tight mb-2">Automated Preprocessing</h3>
              <p className="text-[#888888] text-[14px] leading-relaxed">
                Automatically merges duplicate vertices, repairs broken topology, and validates geometric integrity before optimization begins.
              </p>
            </div>
          </div>

          {/* Card 5: Fast Pipeline (Span 1) */}
          <div className="md:col-span-1 bg-[#0A0A0A] rounded-[32px] overflow-hidden flex flex-col p-8 relative border border-white/5 hover:border-white/10 transition-colors group">
            <div className="flex-1 w-full flex items-center justify-start gap-3 z-10 mb-6">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="w-2 rounded-full bg-[#FF3B3B] transition-all duration-300" style={{ height: `${20 + Math.random() * 40}px`, animation: `pulse ${1 + i * 0.2}s infinite` }} />
              ))}
            </div>
            <div className="z-10 mt-auto">
              <h3 className="text-[#F2F2F2] text-[20px] font-semibold tracking-tight mb-2">Smart Architecture</h3>
              <p className="text-[#888888] text-[14px] leading-relaxed">
                Powered by Python and PyMeshLab for robust QEM decimation, enhanced with Graph Neural Networks for feature preservation.
              </p>
            </div>
          </div>

          {/* Card 6: Material Preservation (Span 1) */}
          <div className="md:col-span-1 bg-[#0A0A0A] rounded-[32px] overflow-hidden flex flex-col p-8 relative border border-white/5 hover:border-white/10 transition-colors group">
             <div className="flex-1 w-full flex items-center justify-center relative mb-6">
               <div className="w-20 h-20 rounded-full bg-gradient-to-tr from-blue-500 via-purple-500 to-[#FF3B3B] animate-[spin_4s_linear_infinite] opacity-80 blur-[2px]" />
             </div>
            <div className="z-10 mt-auto">
              <h3 className="text-[#F2F2F2] text-[20px] font-semibold tracking-tight mb-2">Materials Kept</h3>
              <p className="text-[#888888] text-[14px] leading-relaxed">
                Retains all texture mapping and UV data flawlessly during reduction.
              </p>
            </div>
          </div>

        </div>
      </div>
    </section>
  )
}
