import { UseCaseCanvas } from './UseCases3D'

export default function UseCasesSection() {
  const useCases = [
    {
      id: 'gaming',
      title: 'Gaming & Interactive',
      description: 'Automatically generate LODs for entire environments and character rosters. Ensure smooth frame rates on any hardware.',
      stats: ['Up to 80% polygon reduction', 'Automated LOD chains', 'Preserved animations'],
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
          <rect x="2" y="6" width="20" height="12" rx="2" ry="2" />
          <path d="M6 12h4M8 10v4M15 13h.01M18 11h.01" />
        </svg>
      )
    },
    {
      id: 'ecommerce',
      title: 'Web & E-Commerce',
      description: 'Deliver instant load times for 3D product configurators. Crunch down massive CAD exports into web-friendly GLB files.',
      stats: ['90% smaller file sizes', 'Sub-second load times', 'Texture baking support'],
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
          <circle cx="9" cy="21" r="1" /><circle cx="20" cy="21" r="1" />
          <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
        </svg>
      )
    },
    {
      id: 'arvr',
      title: 'AR / VR & Spatial',
      description: 'Meet strict polygon budgets for Meta Quest and Apple Vision. Reduce geometric complexity while preserving fidelity.',
      stats: ['Strict poly-count targeting', 'Draw call reduction', 'Mobile-first geometry'],
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
          <path d="M2 12h4l3-9 5 18 3-9h5" />
        </svg>
      )
    },
    {
      id: 'archviz',
      title: 'Architecture & BIM',
      description: 'Convert heavy BIM and CAD data into lightweight meshes ready for real-time walkthroughs and virtual staging.',
      stats: ['Hidden surface removal', 'BIM data cleanup', 'Instancing optimization'],
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
          <path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v3M12 14v3M16 14v3" />
        </svg>
      )
    }
  ]

  return (
    <section id="use-cases" className="w-full flex flex-col items-center justify-center py-12 lg:py-0 lg:h-[90vh] lg:max-h-[900px] lg:min-h-[700px] relative z-10 px-4 md:px-0">
      <div className="w-full max-w-[1200px] flex flex-col items-center justify-center h-full relative z-10">
        
        {/* Header */}
        <div className="flex flex-col items-center text-center mb-6 lg:mb-10 pointer-events-none">
          <div className="flex items-center gap-2 px-4 py-1.5 bg-white/5 border border-white/10 rounded-full mb-4">
            <span className="text-[#F2F2F2] text-[12px] font-semibold tracking-wide">Use Cases</span>
          </div>
          <h2 className="text-[28px] md:text-[36px] lg:text-[40px] font-medium tracking-tight leading-[1.1] text-[#F2F2F2] max-w-[800px]">
            Optimized meshes for every <span className="text-[#FF3B3B]">industry.</span>
          </h2>
        </div>

        {/* 2x2 Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-6 w-full">
          {useCases.map((useCase) => (
            <div key={useCase.id} className="group relative bg-[#0A0A0A] rounded-[24px] border border-white/5 hover:border-white/10 overflow-hidden transition-all duration-500 flex flex-col min-h-[300px] lg:h-[320px]">
              
              {/* Interactive 3D Canvas */}
              <div className="absolute top-0 right-0 w-[50%] lg:w-[55%] h-full z-0 pointer-events-auto flex items-center justify-center">
                <div className="absolute inset-0 bg-gradient-to-l from-transparent via-transparent to-[#0A0A0A] z-10 pointer-events-none" />
                <UseCaseCanvas type={useCase.id} />
              </div>

              {/* Text Content (Overlaid to the left) */}
              <div className="relative z-20 w-full md:w-[60%] flex flex-col h-full p-6 lg:p-8 pointer-events-none">
                <div className="w-10 h-10 rounded-[12px] bg-white/5 border border-white/10 flex items-center justify-center mb-4 text-[#FF3B3B] shadow-lg group-hover:scale-110 transition-transform duration-500">
                  {useCase.icon}
                </div>
                
                <h3 className="text-[18px] lg:text-[20px] font-semibold text-[#F2F2F2] mb-2 tracking-tight drop-shadow-lg">{useCase.title}</h3>
                
                <p className="text-[#888888] text-[13px] leading-relaxed mb-4 drop-shadow-md">
                  {useCase.description}
                </p>
                
                <div className="mt-auto flex flex-col gap-2.5">
                  {useCase.stats.map((stat, i) => (
                    <div key={i} className="flex items-center gap-2 text-[12px] text-[#cccccc] font-medium w-max">
                      <div className="w-4 h-4 rounded-full bg-[#FF3B3B]/20 flex items-center justify-center text-[#FF3B3B] flex-shrink-0">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="w-2.5 h-2.5">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                      <span className="drop-shadow-md">{stat}</span>
                    </div>
                  ))}
                </div>
              </div>

            </div>
          ))}
        </div>

      </div>
    </section>
  )
}
