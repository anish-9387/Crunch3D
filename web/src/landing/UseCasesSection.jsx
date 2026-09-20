import React from 'react';

const cases = [
  {
    title: 'Gaming',
    desc: 'Lighter assets, smoother frames, bigger worlds.',
    tags: ['Open World', 'Mobile Games', 'AAA'],
    img: '/usecases/gaming.jpg',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F26522" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"></rect><path d="M6 12h4"></path><path d="M8 10v4"></path><line x1="15" y1="13" x2="15.01" y2="13"></line><line x1="18" y1="11" x2="18.01" y2="11"></line></svg>
    )
  },
  {
    title: 'AR/VR',
    desc: 'Optimized meshes for immersive experiences.',
    tags: ['Meta Quest', 'AR Apps', 'Real-time'],
    img: '/usecases/ar_vr.jpg',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F26522" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12v-4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v4"></path><path d="M22 12a10.02 10.02 0 0 1-5 8.66l-3-1.74a10.05 10.05 0 0 0-4 0l-3 1.74A10.02 10.02 0 0 1 2 12"></path><circle cx="12" cy="12" r="3"></circle></svg>
    )
  },
  {
    title: 'Film & Animation',
    desc: 'High-quality models, production-ready.',
    tags: ['VFX', 'Cinematics', 'CGI'],
    img: '/usecases/film.jpg',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F26522" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg>
    )
  },
  {
    title: 'Product Design',
    desc: 'Simplify, iterate, and visualize faster.',
    tags: ['Concepts', 'Prototypes', 'E-commerce'],
    img: '/usecases/product.jpg',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F26522" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
    )
  },
  {
    title: 'Architecture',
    desc: 'Detailed environments, optimized for the web.',
    tags: ['BIM', 'Web Viewer', 'Virtual Tours'],
    img: '/usecases/architecture.jpg',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F26522" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect><line x1="9" y1="22" x2="9" y2="22"></line><line x1="15" y1="22" x2="15" y2="22"></line><line x1="9" y1="18" x2="9" y2="18"></line><line x1="15" y1="18" x2="15" y2="18"></line><line x1="9" y1="14" x2="9" y2="14"></line><line x1="15" y1="14" x2="15" y2="14"></line><line x1="9" y1="10" x2="9" y2="10"></line><line x1="15" y1="10" x2="15" y2="10"></line><line x1="9" y1="6" x2="9" y2="6"></line><line x1="15" y1="6" x2="15" y2="6"></line></svg>
    )
  },
  {
    title: 'Industrial & CAD',
    desc: 'Handle complex models with ease.',
    tags: ['Manufacturing', 'Simulation', 'Digital Twins'],
    img: '/usecases/industrial.jpg',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F26522" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
    )
  },
  {
    title: 'Research & Education',
    desc: 'Work with large datasets, without the hardware limits.',
    tags: ['Museums', 'Academic', 'Open Source'],
    img: '/usecases/research.jpg',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F26522" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"></path><path d="M6 12v5c3 3 9 3 12 0v-5"></path></svg>
    )
  },
  {
    title: 'Web & Metaverse',
    desc: 'Optimized 3D for the open web.',
    tags: ['WebGL', 'Metaverse', 'Real-time'],
    img: '/usecases/web.jpg',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F26522" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
    )
  }
];

export default function UseCasesSection() {
  return (
    <section id="about" className="relative w-full py-20 pb-32 overflow-hidden" style={{ backgroundColor: '#F26522' }}>
      <div className="w-full max-w-[1600px] mx-auto px-6 lg:px-12 flex flex-col items-center relative z-10">
        
        {/* Header */}
        <div className="flex flex-col items-center text-center gap-4 mb-10">
          <div className="bg-white/20 text-white backdrop-blur-md text-[11px] font-bold tracking-widest px-4 py-1.5 rounded-full uppercase font-poppins">
            Use Cases
          </div>
          
          <h2 className="text-[40px] md:text-[60px] font-black text-white leading-tight" style={{ fontFamily: "'Fredoka', sans-serif" }}>
            Built for <span className="text-white/80">every 3D world.</span>
          </h2>
          
          <p className="max-w-2xl text-white/80 text-sm md:text-base font-poppins font-light leading-relaxed">
            From games to the real world — Crunch3D helps creators, developers, and industries ship lighter, faster, and better 3D assets.
          </p>
        </div>

        {/* Grid Container */}
        <div className="relative w-full mt-10 flex flex-col lg:block">
          {/* Central Character Overlay */}
          <div className="relative lg:absolute lg:top-1/2 lg:left-1/2 lg:-translate-x-1/2 lg:-translate-y-1/2 w-[280px] sm:w-[350px] lg:w-[450px] xl:w-[550px] h-[300px] sm:h-[400px] lg:h-[500px] xl:h-[600px] z-20 pointer-events-none flex items-center justify-center mx-auto mb-8 lg:mb-0">
            
            {/* Floor Shadow */}
            <div className="absolute bottom-4 md:bottom-8 lg:bottom-12 left-1/2 -translate-x-1/2 w-[150px] md:w-[200px] lg:w-[250px] h-[20px] md:h-[30px] bg-black/50 rounded-full blur-[12px] md:blur-[16px] z-0"></div>
            
            <img src="/assets/usecase.png" alt="Use Cases Character" className="w-full h-full object-contain relative z-10" />
          </div>

          {/* Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 relative z-10 w-full">
            {cases.map((usecase, idx) => (
              <React.Fragment key={usecase.title}>
                <div className="bg-white rounded-2xl overflow-hidden shadow-[0_10px_20px_rgba(0,0,0,0.1),_0_3px_6px_rgba(0,0,0,0.05)] border border-gray-100 flex flex-col group">
                  
                  {/* Image */}
                  <div className="h-32 md:h-36 w-full bg-gray-50 relative overflow-hidden flex-shrink-0 border-b border-gray-100 p-2">
                    <img src={usecase.img} alt={usecase.title} className="w-full h-full object-cover rounded-xl" />
                    <div className="absolute top-4 left-4 w-8 h-8 bg-white/90 backdrop-blur-sm rounded-lg shadow-sm flex items-center justify-center z-10">
                      {usecase.icon}
                    </div>
                  </div>

                {/* Content */}
                <div className="p-4 md:p-5 flex flex-col flex-1 gap-2 relative">
                  {/* Arrow Icon */}
                  <div className="absolute top-4 right-4 w-7 h-7 rounded-full border border-gray-200 flex items-center justify-center text-gray-400 bg-gray-50 group-hover:bg-[#F26522] group-hover:border-[#F26522] group-hover:text-white transition-colors">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                  </div>
                  
                  <h3 className="font-bold text-gray-900 text-base pr-8">{usecase.title}</h3>
                  <p className="text-gray-600 text-[11px] font-poppins font-light leading-relaxed mb-3 flex-1">
                    {usecase.desc}
                  </p>
                  
                  <div className="flex flex-wrap gap-1.5 mt-auto">
                    {usecase.tags.map(tag => (
                      <span key={tag} className="text-[9px] bg-orange-50 text-[#F26522] px-2 py-1 rounded-full font-bold border border-orange-100 shadow-sm">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              
              {/* Inject empty column for mascot */}
              {(idx === 1 || idx === 5) && <div className="hidden lg:block pointer-events-none"></div>}
            </React.Fragment>
            ))}
          </div>
        </div>



      </div>
    </section>
  );
}
