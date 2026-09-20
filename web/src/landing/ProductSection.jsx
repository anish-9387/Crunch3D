import React from 'react';

const LightningIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-white"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
);

const ShieldIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-white"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
);

const BoxIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-white"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
);

const FileIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-white/70"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><polyline points="13 2 13 9 20 9"></polyline></svg>
);

const HandArrow = () => (
  <svg width="40" height="50" viewBox="0 0 40 50" fill="none" stroke="rgba(255,255,255,0.7)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="absolute top-16 left-1/2 -translate-x-1/2 opacity-70">
    <path d="M30,5 Q5,25 15,45" />
    <path d="M5,35 L15,45 L25,40" />
  </svg>
);

export default function ProductSection() {
  return (
    <section id="features" className="relative w-full py-20 text-white" style={{ backgroundColor: '#F26522' }}>
      {/* Bleed from Hero Floor Glow to eliminate the seam */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[100%] md:w-[80%] h-[40vh] bg-[radial-gradient(ellipse_at_center,#FF8A47_0%,transparent_70%)] opacity-40 blur-2xl -translate-y-1/2 pointer-events-none z-0"></div>
      {/* Background Blobs (Adjusted for dark background) */}
      <div className="absolute top-0 left-0 w-[500px] h-[500px] bg-white/10 rounded-full blur-[100px] -translate-x-1/2 -translate-y-1/2 mix-blend-overlay"></div>
      <div className="absolute bottom-0 right-0 w-[800px] h-[600px] bg-white/5 rounded-full blur-[150px] translate-x-1/3 translate-y-1/3 mix-blend-overlay"></div>

      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 relative z-10 flex flex-col items-center">
        
        {/* Header */}
        <div className="flex flex-col items-center text-center mb-12 lg:mb-16 max-w-3xl">
          <div className="px-4 py-1.5 rounded-full bg-white/10 text-white text-[10px] md:text-xs font-bold tracking-widest mb-6 border border-white/20 shadow-[inset_0_1px_2px_rgba(255,255,255,0.3)] backdrop-blur-md">
            THE PRODUCT
          </div>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-black mb-4 lg:mb-6 tracking-tight text-white drop-shadow-sm" style={{ fontFamily: "'Fredoka', sans-serif" }}>
            Upload. <span className="text-white/80">Optimize.</span> Deploy.
          </h2>
          <p className="text-base md:text-lg lg:text-xl text-white/80 leading-relaxed font-poppins font-light px-4 md:px-0">
            Crunch3D turns heavy, unoptimized 3D meshes into production-ready assets in minutes — with AI that knows what matters.
          </p>
        </div>

        {/* 3-Column Layout */}
        <div className="grid grid-cols-1 xl:grid-cols-[250px_1fr_250px] gap-10 xl:gap-8 w-full items-center mb-16 xl:mb-20">
          
          {/* Left Column: Features */}
          <div className="flex flex-col gap-8 lg:gap-12 order-2 xl:order-1 px-4 sm:px-12 xl:px-0">
            {/* Feature 1 */}
            <div className="flex flex-row xl:flex-row gap-4 items-start">
              <div className="w-12 h-12 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center shrink-0 shadow-[inset_0_1px_2px_rgba(255,255,255,0.3)] border border-white/20">
                <LightningIcon />
              </div>
              <div className="flex flex-col text-left">
                <h3 className="text-lg font-bold text-white mb-1">AI-Powered Optimization</h3>
                <p className="text-white/70 text-sm leading-relaxed font-poppins font-light">Smartly reduces polygons while preserving details.</p>
              </div>
            </div>
            
            {/* Feature 2 */}
            <div className="flex flex-row xl:flex-row gap-4 items-start">
              <div className="w-12 h-12 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center shrink-0 shadow-[inset_0_1px_2px_rgba(255,255,255,0.3)] border border-white/20">
                <ShieldIcon />
              </div>
              <div className="flex flex-col text-left">
                <h3 className="text-lg font-bold text-white mb-1">Production Ready</h3>
                <p className="text-white/70 text-sm leading-relaxed font-poppins font-light">Optimized for games, AR/VR, and real-time.</p>
              </div>
            </div>

            {/* Feature 3 */}
            <div className="flex flex-row xl:flex-row gap-4 items-start">
              <div className="w-12 h-12 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center shrink-0 shadow-[inset_0_1px_2px_rgba(255,255,255,0.3)] border border-white/20">
                <BoxIcon />
              </div>
              <div className="flex flex-col text-left">
                <h3 className="text-lg font-bold text-white mb-1">Works with Any 3D Model</h3>
                <p className="text-white/70 text-sm leading-relaxed font-poppins font-light">Upload, optimize, and download in seconds.</p>
              </div>
            </div>
          </div>

          {/* Center Column: Image */}
          <div className="order-1 xl:order-2 w-full flex justify-center relative px-2 mt-4 xl:mt-0">
            {/* Ground Shadow */}
            <div className="absolute bottom-[2%] lg:bottom-[4%] left-1/2 -translate-x-1/2 w-[70%] h-[30px] lg:h-[50px] bg-black/40 rounded-[100%] blur-[20px] z-0"></div>
            <div className="absolute bottom-[2%] lg:bottom-[4%] left-1/2 -translate-x-1/2 w-[40%] h-[15px] lg:h-[25px] bg-black/50 rounded-[100%] blur-[12px] z-0"></div>
            
            <img src="/assets/product.png" alt="Crunch3D Product Interface" className="w-full max-w-[1100px] object-contain drop-shadow-2xl z-10 relative" />
          </div>

          {/* Right Column: Stats & Annotations */}
          <div className="flex flex-col gap-8 justify-center order-3 xl:order-3 relative h-full px-4 sm:px-12 xl:px-0">
            
            {/* Annotation Arrow (Desktop only) */}
            <div className="hidden xl:flex flex-col absolute top-0 right-0 xl:translate-x-4 xl:-translate-y-8 items-center rotate-6">
              <span className="text-white/90 font-medium text-lg" style={{ fontFamily: "'Fredoka', sans-serif" }}>Same character.</span>
              <span className="text-white/90 font-medium text-lg -mt-1" style={{ fontFamily: "'Fredoka', sans-serif" }}>Smarter meshes.</span>
              <HandArrow />
            </div>

            {/* Stats Card */}
            <div className="bg-white/10 backdrop-blur-xl border border-white/20 rounded-3xl p-5 lg:p-6 shadow-[0_20px_40px_-15px_rgba(0,0,0,0.2),inset_0_2px_4px_rgba(255,255,255,0.2)] flex flex-col gap-4 max-w-[320px] mx-auto xl:mx-0 w-full mt-4 xl:mt-32">
              <div className="flex flex-col">
                <span className="text-2xl lg:text-3xl font-black text-white" style={{ fontFamily: "'Fredoka', sans-serif" }}>10x</span>
                <span className="text-white/70 text-xs font-poppins font-light">Faster Workflow</span>
              </div>
              <div className="w-full h-px bg-white/10"></div>
              <div className="flex flex-col">
                <span className="text-2xl lg:text-3xl font-black text-white" style={{ fontFamily: "'Fredoka', sans-serif" }}>~95%</span>
                <span className="text-white/70 text-xs font-poppins font-light">Smaller Files</span>
              </div>
              <div className="w-full h-px bg-white/10"></div>
              <div className="flex flex-col">
                <span className="text-2xl lg:text-3xl font-black text-white" style={{ fontFamily: "'Fredoka', sans-serif" }}>4 LODs</span>
                <span className="text-white/70 text-xs font-poppins font-light">Ready to Deploy</span>
              </div>
            </div>

          </div>
        </div>

        {/* Bottom Bar: Supported Formats */}
        <div className="w-full max-w-6xl bg-white/10 backdrop-blur-xl border border-white/20 shadow-[0_10px_30px_-10px_rgba(0,0,0,0.2),inset_0_2px_4px_rgba(255,255,255,0.2)] py-3 px-6 md:px-10 flex flex-row items-center justify-between gap-4 overflow-x-auto rounded-full hide-scrollbar">
          
          <div className="flex flex-row items-center gap-6 shrink-0">
            <span className="text-[10px] md:text-xs font-bold text-white/60 tracking-widest leading-tight font-poppins">SUPPORTED<br/>FORMATS</span>
            <div className="h-8 w-px bg-white/10"></div>
            
            <div className="flex flex-row items-center gap-6">
              {['OBJ', 'STL', 'PLY', 'GLB', 'GLTF', 'FBX', 'OFF'].map(format => (
                <div key={format} className="flex items-center gap-1.5 text-white/90 font-light text-xs md:text-sm font-poppins cursor-default shrink-0">
                  <FileIcon />
                  {format}
                </div>
              ))}
            </div>
          </div>

          <div className="hidden lg:flex items-center gap-6 shrink-0">
            <div className="h-8 w-px bg-white/10"></div>
            <div className="text-[10px] md:text-xs font-bold text-white/60 tracking-widest text-right font-poppins">
              UP TO 50MB<br/>PER FILE
            </div>
          </div>
        </div>

      </div>
    </section>
  );
}
