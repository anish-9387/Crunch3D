import React from 'react';
import footerMascot from '../../assets/footer.png';

export default function FooterSection() {
  return (
    <footer className="w-full flex flex-col font-sans">
      {/* Top Section - Newsletter & Mascot */}
      <div className="relative w-full bg-[#F26522] pt-16 md:pt-24 pb-8 overflow-visible">
        <div className="w-full max-w-[1400px] mx-auto px-6 lg:px-12 flex flex-col md:flex-row items-center justify-between z-30 relative">
          
          <div className="flex-1 max-w-xl z-20 text-left">
            <h2 className="text-[42px] md:text-[64px] lg:text-[72px] font-black leading-[0.95] text-white mb-6 uppercase tracking-tight" style={{ fontFamily: "'Fredoka', sans-serif" }}>
              Build<br/>
              <span className="text-white">Better Worlds</span><br/>
              Together.
            </h2>
            
            <p className="text-white/90 text-lg md:text-xl font-light mb-8 max-w-md mx-auto md:mx-0 font-poppins">
              Get updates, new features, community stories and 3D tips — straight to your inbox.
            </p>
            
            <div className="relative w-full max-w-[480px] mx-0">
              <div className="flex items-center bg-white rounded-full p-1.5 sm:p-2 shadow-lg border border-gray-100">
                <div className="pl-3 sm:pl-4 pr-1 sm:pr-2 text-gray-400 hidden sm:block">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
                </div>
                <input 
                  type="email" 
                  placeholder="Enter your email" 
                  className="flex-1 bg-transparent border-none outline-none px-4 sm:px-2 text-sm sm:text-base text-gray-700 placeholder-gray-400 font-poppins min-w-0"
                />
                <button className="bg-[#F26522] text-white px-5 sm:px-8 py-2.5 md:py-3 rounded-full text-sm sm:text-base font-bold flex items-center gap-1 sm:gap-2 hover:bg-[#d8561b] transition-colors shadow-md whitespace-nowrap">
                  Subscribe
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="hidden sm:block"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                </button>
              </div>
              <p className="text-white/70 text-xs mt-3 font-medium text-left">No spam. Just the good stuff.</p>
            </div>
          </div>

          <div className="flex relative w-full h-[240px] sm:h-[280px] md:h-[300px] md:w-[400px] lg:w-[500px] mt-16 md:mt-0 z-30 justify-center md:justify-end items-end md:ml-auto">
            <img 
              src={footerMascot} 
              alt="Crunch3D Mascot Laying Down" 
              className="absolute right-auto md:right-[-20px] lg:right-[-40px] bottom-[-38px] md:bottom-[-96px] w-[340px] sm:w-[400px] md:w-[450px] lg:w-[600px] h-auto max-w-none object-contain origin-bottom md:origin-bottom-right z-50 drop-shadow-[0_20px_30px_rgba(0,0,0,0.4)] md:drop-shadow-[0_30px_40px_rgba(0,0,0,0.4)]"
            />
          </div>
        </div>
        
        {/* Decorative floor glow behind mascot */}
        <div className="absolute bottom-0 right-0 w-full md:w-[50%] h-[100px] md:h-[150px] bg-gradient-to-t from-[#F26522]/20 to-transparent pointer-events-none z-0"></div>
      </div>

      {/* Bottom Section - Footer Links */}
      <div className="relative w-full bg-[#F26522] pt-20 md:pt-14 pb-12 z-20 shadow-[0_-20px_30px_rgba(0,0,0,0.1)]">
        <div className="w-full max-w-[1400px] mx-auto px-6 lg:px-12">
          
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-12 gap-y-12 gap-x-6 lg:gap-8 pb-12 md:pb-16 border-b border-white/20">
            
            {/* Column 1: Brand & Socials */}
            <div className="col-span-2 md:col-span-4 lg:col-span-4 flex flex-col gap-5 md:gap-6 items-start text-left">
              <div className="flex items-center gap-2">
                <img src="../../assets/logo.png" alt="Crunch3D Logo" className="w-8 h-8" onError={(e) => e.target.style.display = 'none'} />
                <span className="text-white font-black text-2xl tracking-tight" style={{ fontFamily: "'Fredoka', sans-serif" }}>CRUNCH3D</span>
              </div>
              
              <div className="flex flex-col items-start">
                <h4 className="text-white font-bold text-lg mb-2">Same Character.<br/>Smarter Meshes.</h4>
                <p className="text-white/80 text-sm font-poppins font-light leading-relaxed max-w-xs md:max-w-[280px]">
                  Crunch3D empowers creators, studios, and developers with AI-powered 3D optimization tools to build faster, simpler, and bigger.
                </p>
              </div>

              <div className="flex items-center justify-start gap-3 mt-2 md:mt-4">
                {[
                  { name: 'Twitter', url: 'https://x.com/TeamCrunch3d', icon: <path d="M22 4s-.7 2.1-2 3.4c1.6 10-9.4 17.3-18 11.6 2.2.1 4.4-.6 6-2C3 15.5.5 9.6 3 5c2.2 2.6 5.6 4.1 9 4-.9-4.2 4-6.6 7-3.8 1.1 0 3-1.2 3-1.2z"></path> },
                  { name: 'Github', url: 'https://github.com/Lesgo-HQ', icon: <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path> },
                  { name: 'LinkedIn', url: 'https://www.linkedin.com/company/lesgohq', icon: <><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"></path><rect x="2" y="9" width="4" height="12"></rect><circle cx="4" cy="4" r="2"></circle></> },
                  { name: 'Instagram', url: 'https://www.instagram.com/lesgohq/', icon: <><rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line></> },
                ].map((social, idx) => (
                  <a key={idx} href={social.url} target="_blank" rel="noopener noreferrer" className="w-8 h-8 rounded-full border border-white/30 flex items-center justify-center text-white hover:bg-white/10 transition-colors cursor-pointer">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{social.icon}</svg>
                  </a>
                ))}
              </div>
            </div>

            {/* Column 2: Links */}
            <div className="col-span-1 md:col-span-2 lg:col-span-2 flex flex-col gap-3 md:gap-4 items-start text-left">
              <h5 className="text-white font-bold mb-1 md:mb-2 text-base md:text-lg">Product</h5>
              {[
                { label: 'Features', hash: '#features' },
                { label: 'Use Cases', hash: '#about' },
                { label: 'Pricing', hash: '#pricing' }
              ].map((link, i) => (
                <a key={i} href={link.hash} className="text-white/80 hover:text-white text-sm font-poppins transition-colors">{link.label}</a>
              ))}
            </div>

            {/* Column 3: Resources */}
            <div className="col-span-1 md:col-span-2 lg:col-span-2 flex flex-col gap-3 md:gap-4 items-start text-left">
              <h5 className="text-white font-bold mb-1 md:mb-2 text-base md:text-lg">Resources</h5>
              {['Documentation'].map((link, i) => (
                <a key={i} href="#" className="text-white/80 hover:text-white text-sm font-poppins transition-colors">{link}</a>
              ))}
            </div>

            {/* Column 4: Quote Block */}
            <div className="col-span-2 md:col-span-4 lg:col-span-4 flex flex-col gap-5 md:gap-6 lg:pl-12 items-start text-left mt-2 md:mt-0">
              <div className="flex flex-col items-start">
                <p className="text-white font-medium text-sm leading-relaxed font-poppins mb-3 md:mb-4">
                  "Better tools.<br className="hidden md:block" />Brighter creators.<br className="hidden md:block" />A more open 3D world."
                </p>
                <div className="w-12 h-[1px] bg-white/40 mb-3 md:mb-4"></div>
                <p className="text-white/80 text-sm font-poppins leading-relaxed max-w-[280px] md:max-w-none">
                  Join a global community of builders, artists, and dreamers.
                </p>
              </div>
              <button className="bg-white text-gray-900 px-6 py-3 rounded-full font-bold text-sm flex items-center justify-between w-full sm:w-auto md:w-full max-w-[280px] md:max-w-none hover:bg-gray-50 transition-colors shadow-lg shadow-black/10 gap-2">
                Get Started
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
              </button>
            </div>

          </div>

          {/* Copyright Bar */}
          <div className="flex flex-col-reverse md:flex-row items-center md:items-center justify-between py-6 text-white/60 text-xs font-poppins gap-4 md:gap-4 text-left">
            <p className="w-full text-left md:w-auto">© 2026 Crunch3D by <a href="https://lesgo.works" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors underline">Lesgo</a>. All rights reserved.</p>
            <div className="flex flex-wrap justify-start items-center gap-4 md:gap-6 w-full md:w-auto">
              <a href="#" className="hover:text-white transition-colors">Privacy Policy</a>
              <a href="#" className="hover:text-white transition-colors">Terms of Service</a>
              <a href="#" className="hover:text-white transition-colors">Cookies</a>
              <a href="#" className="hover:text-white transition-colors">Sitemap</a>
            </div>
          </div>

        </div>
      </div>
    </footer>
  );
}
