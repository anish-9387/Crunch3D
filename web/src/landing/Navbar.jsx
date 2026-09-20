import React from 'react';
import logo from '../../assets/logo.png';

export default function Navbar({ onTryDemo }) {
  return (
    <nav className="fixed top-0 left-0 w-full z-[999] px-6 lg:px-12 py-6 flex items-center justify-between">
      <div className="w-full max-w-[1600px] mx-auto flex items-center justify-between">
        <div className="flex items-center gap-2 md:gap-3">
          <img src={logo} alt="Crunch3D" className="h-10 md:h-14 object-contain drop-shadow-md" />
          <span className="font-bold text-xl md:text-2xl tracking-wide text-white" style={{ fontFamily: "'Fredoka', sans-serif" }}>CRUNCH3D</span>
        </div>

        <div className="hidden lg:flex items-center gap-1 bg-gradient-to-b from-white/20 to-white/5 backdrop-blur-xl rounded-full px-2 py-1.5 border border-white/30 shadow-[0_10px_20px_-5px_rgba(0,0,0,0.15),inset_0_2px_4px_rgba(255,255,255,0.3),inset_0_-2px_4px_rgba(0,0,0,0.1)]">
          {[
            { label: 'Product', hash: '#features' },
            { label: 'Use Cases', hash: '#about' },
            { label: 'Pricing', hash: '#pricing' },
            { label: 'Docs', hash: '#' }
          ].map((item) => (
            <a key={item.label} href={item.hash} className="px-6 py-2 rounded-full text-sm font-medium hover:bg-white/20 transition-all hover:shadow-[inset_0_1px_2px_rgba(255,255,255,0.2)] text-white">
              {item.label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-2 md:gap-4">
          <button onClick={onTryDemo} className="px-4 md:px-6 py-2 md:py-2.5 rounded-full font-semibold flex items-center gap-2 bg-gradient-to-b from-white to-white/70 backdrop-blur-xl border border-white/60 hover:from-white hover:to-white/90 transition-all active:scale-95 text-xs md:text-sm shadow-[0_10px_20px_-5px_rgba(0,0,0,0.15),inset_0_3px_5px_rgba(255,255,255,1),inset_0_-3px_5px_rgba(0,0,0,0.1)] text-[#B83E08] whitespace-nowrap">
            Get Started
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="md:w-[16px] md:h-[16px]"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
          </button>
        </div>
      </div>
    </nav>
  );
}
