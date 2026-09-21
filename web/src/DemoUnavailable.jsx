import React from 'react';

const logo = '/assets/logo.png';
const errordemo = '/assets/errordemo.png';

export default function DemoUnavailable({ onBackToHome }) {
  return (
    <div className="h-screen w-full bg-brand-orange flex flex-col font-poppins relative overflow-hidden">
      {/* Navbar Area (Simplified for Demo Error Page) */}
      <nav className="absolute top-0 left-0 w-full z-10 px-6 lg:px-12 py-6 flex items-center justify-between">
        <div className="w-full max-w-[1600px] mx-auto flex items-center">
          <div className="flex items-center gap-2 md:gap-3 cursor-pointer" onClick={onBackToHome}>
            <img src={logo} alt="Crunch3D" className="h-10 md:h-14 object-contain drop-shadow-md" />
            <span className="font-bold text-xl md:text-2xl tracking-wide text-white" style={{ fontFamily: "'Fredoka', sans-serif" }}>
              CRUNCH3D
            </span>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="flex-1 w-full max-w-5xl mx-auto flex flex-col items-center justify-center px-4 pt-24 pb-12 z-10 text-white text-center">
        
        {/* Character Image */}
        <div className="w-full max-w-3xl mb-4 relative">
          <img 
            src={errordemo} 
            alt="Demo is sleeping" 
            className="w-full h-auto object-contain drop-shadow-2xl transform scale-110 md:scale-125" 
          />
        </div>

        {/* Text Content */}
        <h1 className="text-4xl md:text-6xl font-black mb-4 tracking-tight drop-shadow-sm">
          Oops! Our demo is sleeping.
        </h1>
        <div className="max-w-2xl mx-auto mb-10 space-y-2 opacity-90 text-sm md:text-base leading-relaxed">
          <p>
            We've hit the free tier limits on our Render deployment, 
            and the demo is currently unavailable.
          </p>
          <p>
            But don't worry - we're working on bringing it back online soon!
          </p>
          <p className="pt-2 font-medium">
            Till then, watch the demo video below to see how it works.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center gap-4 w-full sm:w-auto">
          <button 
            onClick={onBackToHome}
            className="w-full sm:w-auto px-8 py-3 rounded-full font-semibold flex items-center justify-center gap-2 bg-white/10 hover:bg-white/20 border border-white/30 backdrop-blur-md transition-all active:scale-95 text-white"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12"></line>
              <polyline points="12 19 5 12 12 5"></polyline>
            </svg>
            Go Back
          </button>
          
          <a 
            href="https://drive.google.com/file/d/1x-3gV_UtNdBh5WAfDCDK4AtYNk9HewL0/view?usp=drive_link" 
            target="_blank" 
            rel="noopener noreferrer"
            className="w-full sm:w-auto px-8 py-3 rounded-full font-semibold flex items-center justify-center gap-2 bg-white text-brand-orange hover:bg-brand-white shadow-lg hover:shadow-xl transition-all active:scale-95"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
            Watch Video Demo
          </a>
        </div>
        
      </div>
    </div>
  );
}
