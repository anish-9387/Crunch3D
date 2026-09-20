import { useState, useEffect } from 'react'
import logo from '../../assets/logo.png'
import heroImage from '../../assets/heroImage.png'
import ProductSection from './ProductSection'
import UseCasesSection from './UseCasesSection'
import Navbar from './Navbar'
import PricingSection from './PricingSection'
import TestimonialSection from './TestimonialSection'
import FooterSection from './FooterSection'

export default function LandingPage({ onTryDemo }) {
  return (
    <div id="top" className="w-full flex flex-col font-sans overflow-x-hidden bg-[#F26522]">
      <Navbar onTryDemo={onTryDemo} />

      <div className="relative w-full min-h-screen text-white flex flex-col" style={{ backgroundColor: '#F26522', fontFamily: "'Poppins', sans-serif" }}>
        {/* Studio Backdrop Floor Perspective */}
        <div className="absolute bottom-0 left-0 w-full h-[50vh] pointer-events-none z-0">
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[100%] md:w-[80%] h-[80%] bg-[radial-gradient(ellipse_at_center,#FF8A47_0%,transparent_70%)] opacity-40 blur-2xl"></div>
        </div>

        {/* Background Glow */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-[800px] h-[800px] bg-white/20 blur-[120px] rounded-full mix-blend-overlay"></div>
        </div>

        <div className="relative z-10 w-full max-w-[1600px] mx-auto px-6 lg:px-12 flex-1 flex flex-col min-h-screen pt-20 md:pt-32 lg:pt-36">
          {/* Main Content */}
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_auto_1fr] gap-4 lg:gap-8 items-center content-start lg:content-center pt-6 lg:pt-2 pb-12 lg:pb-12">

            {/* Left Column */}
            <div className="order-2 lg:order-1 flex flex-col items-start gap-4 lg:gap-8 z-20 text-left mt-2 lg:mt-0">
              <div className="bg-white/10 backdrop-blur-md border border-white/20 px-4 py-2 rounded-full flex items-center gap-2 text-[10px] md:text-xs font-semibold tracking-wider">
                <div className="w-2.5 h-2.5 rounded-full bg-white/80 shadow-[0_0_8px_rgba(255,255,255,0.8)]"></div>
                AI-POWERED MESH OPTIMIZATION
              </div>

              <h1 className="font-bold text-[44px] md:text-[60px] lg:text-[85px] leading-[0.95] lg:leading-[0.95] text-[#FFF4EB] drop-shadow-lg tracking-tight" style={{ fontFamily: "'Fredoka', sans-serif" }}>
                LESS<br />POLYGONS<br />MORE<br />WORLDS.
              </h1>

              <div className="grid grid-cols-2 sm:flex sm:flex-row items-center sm:justify-start gap-3 lg:gap-4 mt-1 w-full sm:w-auto">
                <button onClick={onTryDemo} className="w-full sm:w-[170px] lg:w-[220px] h-[46px] lg:h-[56px] justify-center bg-gradient-to-b from-white to-white/70 backdrop-blur-xl border border-white/60 rounded-full font-light lg:font-semibold flex items-center gap-1.5 lg:gap-2 hover:from-white hover:to-white/90 transition-all active:scale-95 text-[12px] lg:text-base shadow-[0_15px_25px_-5px_rgba(0,0,0,0.15),inset_0_4px_6px_rgba(255,255,255,1),inset_0_-4px_6px_rgba(0,0,0,0.1)] whitespace-nowrap text-[#B83E08]">
                  Try Crunch3D
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="lg:w-[16px] lg:h-[16px]"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                </button>
                <button className="w-full sm:w-[170px] lg:w-[220px] h-[46px] lg:h-[56px] justify-center bg-gradient-to-b from-white/30 to-white/5 backdrop-blur-xl border border-white/30 rounded-full font-light lg:font-semibold flex items-center gap-2 lg:gap-3 hover:from-white/40 hover:to-white/10 transition-all active:scale-95 text-[12px] lg:text-base shadow-[0_15px_25px_-5px_rgba(0,0,0,0.2),inset_0_4px_6px_rgba(255,255,255,0.4),inset_0_-4px_6px_rgba(0,0,0,0.1)] whitespace-nowrap text-white">
                  <div className="bg-gradient-to-b from-white/50 to-white/20 rounded-full w-6 h-6 lg:w-7 lg:h-7 flex items-center justify-center pl-[2px] shadow-[inset_0_1px_2px_rgba(255,255,255,0.8)] border border-white/20">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" className="lg:w-[12px] lg:h-[12px]"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                  </div>
                  Watch Demo
                </button>
              </div>

              <div className="hidden lg:flex mt-auto pt-16 flex-col items-start gap-4 w-full">
                <p className="text-[10px] md:text-xs font-semibold tracking-widest text-white/70 uppercase text-center lg:text-left">Trusted by Creators Worldwide</p>
                <div className="flex flex-wrap justify-center lg:justify-start items-center gap-6 lg:gap-8 text-white/90">
                  <div className="flex items-center gap-2 font-bold text-lg">
                    <svg className="w-7 h-7 fill-white" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="m12.9288 4.2939 3.7997 2.1929c.1366.077.1415.2905 0 .3675l-4.515 2.6076a.4192.4192 0 0 1-.4246 0L7.274 6.8543c-.139-.0745-.1415-.293 0-.3675l3.7972-2.193V0L1.3758 5.5977V16.793l3.7177-2.1456v-4.3858c-.0025-.1565.1813-.2682.318-.1838l4.5148 2.6076a.4252.4252 0 0 1 .2136.3676v5.2127c.0025.1565-.1813.2682-.3179.1838l-3.7996-2.1929-3.7178 2.1457L12 24l9.6954-5.5977-3.7178-2.1457-3.7996 2.1929c-.1341.082-.3229-.0248-.3179-.1838V13.053c0-.1565.087-.2956.2136-.3676l4.5149-2.6076c.134-.082.3228.0224.3179.1838v4.3858l3.7177 2.1456V5.5977L12.9288 0Z" /></svg>
                    Unity
                  </div>
                  <div className="flex items-center gap-2 font-bold text-lg">
                    <svg className="w-7 h-7 fill-white" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12.51 13.214c.046-.8.438-1.506 1.03-2.006a3.424 3.424 0 0 1 2.212-.79c.85 0 1.631.3 2.211.79.592.5.983 1.206 1.028 2.005.045.823-.285 1.586-.865 2.153a3.389 3.389 0 0 1-2.374.938 3.393 3.393 0 0 1-2.376-.938c-.58-.567-.91-1.33-.865-2.152M7.35 14.831c.006.314.106.922.256 1.398a7.372 7.372 0 0 0 1.593 2.757 8.227 8.227 0 0 0 2.787 2.001 8.947 8.947 0 0 0 3.66.76 8.964 8.964 0 0 0 3.657-.772 8.285 8.285 0 0 0 2.785-2.01 7.428 7.428 0 0 0 1.592-2.762 6.964 6.964 0 0 0 .25-3.074 7.123 7.123 0 0 0-1.016-2.779 7.764 7.764 0 0 0-1.852-2.043h.002L13.566 2.55l-.02-.015c-.492-.378-1.319-.376-1.86.002-.547.382-.609 1.015-.123 1.415l-.001.001 3.126 2.543-9.53.01h-.013c-.788.001-1.545.518-1.695 1.172-.154.665.38 1.217 1.2 1.22V8.9l4.83-.01-8.62 6.617-.034.025c-.813.622-1.075 1.658-.563 2.313.52.667 1.625.668 2.447.004L7.414 14s-.069.52-.063.831zm12.09 1.741c-.97.988-2.326 1.548-3.795 1.55-1.47.004-2.827-.552-3.797-1.538a4.51 4.51 0 0 1-1.036-1.622 4.282 4.282 0 0 1 .282-3.519 4.702 4.702 0 0 1 1.153-1.371c.942-.768 2.141-1.183 3.396-1.185 1.256-.002 2.455.41 3.398 1.175.48.391.87.854 1.152 1.367a4.28 4.28 0 0 1 .522 1.706 4.236 4.236 0 0 1-.239 1.811 4.54 4.54 0 0 1-1.035 1.626" /></svg>
                    blender
                  </div>
                  <div className="flex items-center gap-2 font-bold text-lg">
                    <svg className="w-7 h-7 fill-white" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 0a12 12 0 1012 12A12 12 0 0012 0zm0 23.52A11.52 11.52 0 1123.52 12 11.52 11.52 0 0112 23.52zm7.13-9.791c-.206.997-1.126 3.557-4.06 4.942l-1.179-1.325-1.988 2a7.338 7.338 0 01-5.804-2.978 2.859 2.859 0 00.65.123c.326.006.678-.114.678-.66v-5.394a.89.89 0 00-1.116-.89c-.92.212-1.656 2.509-1.656 2.509a7.304 7.304 0 012.528-5.597 7.408 7.408 0 013.73-1.721c-1.006.573-1.57 1.507-1.57 2.29 0 1.262.76 1.109.984.923v7.28a1.157 1.157 0 00.148.256 1.075 1.075 0 00.88.445c.76 0 1.747-.868 1.747-.868V9.172c0-.6-.452-1.324-.905-1.572 0 0 .838-.149 1.484.346a5.537 5.537 0 01.387-.425c1.508-1.48 2.929-1.902 4.112-2.112 0 0-2.151 1.69-2.151 3.96 0 1.687.043 5.801.043 5.801.799.771 1.986-.342 3.059-1.441Z" /></svg>
                    UNREAL
                  </div>
                  <div className="flex items-center gap-2 font-bold text-lg">
                    <svg className="w-7 h-7 fill-white" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M11.3 0A11.983 11.983 0 0 0 .037 11a13.656 13.656 0 0 0 0 2 11.983 11.983 0 0 0 11.29 11h1.346a12.045 12.045 0 0 0 11.3-11.36 13.836 13.836 0 0 0 0-1.7A12.049 12.049 0 0 0 12.674 0zM15 6.51l2.99 1.74s-6.064 3.24-6.084 3.24S5.812 8.27 5.8 8.26l2.994-1.77 2.992-1.76zm-6.476 5.126L11 13v5.92l-2.527-1.4-2.46-1.43v-5.76zm9.461 1.572v2.924L15.5 17.574 13 19.017v-6.024l2.489-1.345 2.5-1.355z" /></svg>
                    Sketchfab
                  </div>
                </div>
              </div>
            </div>

            {/* Center Column - Character */}
            <div className="order-1 lg:order-2 relative flex justify-center items-end h-full w-full max-w-[320px] md:max-w-[500px] xl:max-w-[600px] mx-auto z-10 py-0 lg:pb-8 group">
              {/* Realistic 3D Ground Shadow */}
              <div className="absolute bottom-6 lg:bottom-6 left-1/2 -translate-x-1/2 w-[250px] lg:w-[400px] h-[25px] lg:h-[40px] bg-black/30 rounded-[100%] blur-xl z-10"></div>
              <div className="absolute bottom-6 lg:bottom-6 left-1/2 -translate-x-1/2 w-[120px] lg:w-[200px] h-[10px] lg:h-[15px] bg-black/40 rounded-[100%] blur-md z-10"></div>

              <img src={heroImage} alt="3D Character" className="w-full max-h-[45vh] md:max-h-[60vh] lg:max-h-[75vh] object-contain drop-shadow-[0_15px_30px_rgba(0,0,0,0.15)] z-20 relative transition-transform duration-500 origin-bottom" />

              {/* Hover Hand-drawn Cloud Bubble */}
              <div className="absolute top-[5%] lg:top-[15%] left-[80%] md:left-[90%] lg:left-[100%] opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-30 pointer-events-none drop-shadow-2xl">
                <div className="relative bg-white px-6 py-4 md:px-8 md:py-6" style={{ borderRadius: "255px 15px 225px 15px/15px 225px 15px 255px" }}>
                  <div className="text-xl md:text-3xl font-bold whitespace-nowrap text-[#F26522]" style={{ fontFamily: "cursive", transform: "rotate(2deg)" }}>
                    Hey, I m Mr Crunch
                  </div>
                  {/* Curvy tail pointing to mascot */}
                  <svg className="absolute -bottom-6 left-2 w-10 h-10 text-white transform -scale-x-100 -rotate-12" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M 0 0 C 12 0 24 12 24 24 C 20 12 10 5 0 0 Z" />
                  </svg>
                </div>
              </div>


            </div>

            {/* Right Column - Steps */}
            <div className="order-3 flex flex-col items-center lg:items-end justify-center gap-8 z-20 relative lg:pt-12 lg:pl-12 w-full mt-4 lg:mt-0">
              {[
                { title: 'Upload', desc: 'Any 3D model', icon: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg> },
                { title: 'Optimize', desc: 'AI does the work', icon: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"></path><path d="M5 3v4"></path><path d="M19 17v4"></path><path d="M3 5h4"></path><path d="M17 19h4"></path></svg> },
                { title: 'Deploy', desc: 'Ready for real worlds', icon: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="6" y1="12" x2="10" y2="12"></line><line x1="8" y1="10" x2="8" y2="14"></line><line x1="15" y1="13" x2="15.01" y2="13"></line><line x1="18" y1="11" x2="18.01" y2="11"></line><rect x="2" y="6" width="20" height="12" rx="2"></rect></svg> }
              ].map((step, idx) => (
                <div key={idx} className="relative w-full max-w-[300px]">
                  <div className="bg-white/10 backdrop-blur-md border border-white/20 p-5 rounded-[24px] flex flex-col gap-1 z-10 relative shadow-xl hover:bg-white/15 transition-colors cursor-pointer">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 bg-white/20 border border-white/30 flex items-center justify-center rounded-[14px] text-white shadow-sm flex-shrink-0">
                        {step.icon}
                      </div>
                      <div>
                        <div className="font-bold text-lg text-white tracking-wide">{step.title}</div>
                        <div className="text-sm text-white/70 font-medium">{step.desc}</div>
                      </div>
                    </div>
                  </div>
                  {idx < 2 && (
                    <div className="absolute left-[44px] bottom-[-32px] h-8 w-[1px] bg-white/30 z-0"></div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Mobile Only: Trusted By (Moved to bottom) */}
          <div className="flex lg:hidden flex-col items-center gap-4 w-full pb-12 z-20">
            <p className="text-[10px] md:text-xs font-semibold tracking-widest text-white/70 uppercase text-center">Trusted by Creators Worldwide</p>
            <div className="flex flex-wrap justify-center items-center gap-6 text-white/90">
              <div className="flex items-center gap-2 font-bold text-lg">
                <svg className="w-6 h-6 fill-white" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="m12.9288 4.2939 3.7997 2.1929c.1366.077.1415.2905 0 .3675l-4.515 2.6076a.4192.4192 0 0 1-.4246 0L7.274 6.8543c-.139-.0745-.1415-.293 0-.3675l3.7972-2.193V0L1.3758 5.5977V16.793l3.7177-2.1456v-4.3858c-.0025-.1565.1813-.2682.318-.1838l4.5148 2.6076a.4252.4252 0 0 1 .2136.3676v5.2127c.0025.1565-.1813.2682-.3179.1838l-3.7996-2.1929-3.7178 2.1457L12 24l9.6954-5.5977-3.7178-2.1457-3.7996 2.1929c-.1341.082-.3229-.0248-.3179-.1838V13.053c0-.1565.087-.2956.2136-.3676l4.5149-2.6076c.134-.082.3228.0224.3179.1838v4.3858l3.7177 2.1456V5.5977L12.9288 0Z" /></svg>
                Unity
              </div>
              <div className="flex items-center gap-1.5 font-bold text-lg">
                <svg className="w-6 h-6 fill-white" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M16.924 10.354c-.161-.643-.532-1.396-1.125-2.028a31.392 31.392 0 0 0-2.483-2.313c-.143-.119-.34-.239-.567-.323C11.517 5.23 9.471 5 7.159 5c-.753 0-1.28.083-1.468.203-1.638 1.054-2.493 2.91-2.453 5.378.021 1.341.34 3.018.995 4.885.64 1.848 1.488 3.593 2.452 4.965.748 1.077 1.435 1.579 2.057 1.554.298-.01.62-.154.981-.407.41-.284 1.002-.857 1.642-1.745l.061-.082-1.662-1.428-.052.062c-.445.549-.806.942-1.071 1.157-.222.176-.39.23-.464.24-.132.016-.484-.282-.953-.948a17.653 17.653 0 0 1-1.951-3.878 20.463 20.463 0 0 1-1.042-4.14 16.936 16.936 0 0 1 1.776-.902 24.394 24.394 0 0 1 5.926-.967l.115 1.15-.347-.223c.273.195.592.51.986.993.473.57.87 1.258 1.156 1.956.12.289.208.571.267.818.067.28.077.469.043.535a.258.258 0 0 1-.168.125.792.792 0 0 1-.368-.02 2.585 2.585 0 0 1-.58-.23c-1.282-.676-3.136-2.15-4.839-4.148L8.718 10l1.996 1.517.202-.23c1.36-1.551 2.898-2.795 3.963-3.376a2.02 2.02 0 0 1 .521-.212c.18-.046.402-.027.604.093.203.119.349.336.43.684a3.864 3.864 0 0 1 .054 1.705 9.176 9.176 0 0 1-.59 2.09c-.43 1.002-1.037 2.001-1.748 2.872a15.82 15.82 0 0 1-2.42 2.383l1.503 1.62c.703-.526 1.488-1.238 2.298-2.133 1.054-1.163 1.968-2.52 2.575-3.876a8.91 8.91 0 0 0 .913-2.923c.04-.693-.035-1.378-.283-1.85z" /></svg>
                Blender
              </div>
              <div className="flex items-center gap-1.5 font-bold text-lg leading-none">
                <div className="w-6 h-6 border-2 border-white rounded-full flex items-center justify-center font-bold text-[10px]">U</div>
                <div className="flex flex-col">
                  <span className="text-[10px] leading-[1]">UNREAL</span>
                  <span className="text-[10px] leading-[1]">ENGINE</span>
                </div>
              </div>
              <div className="flex items-center gap-1.5 font-bold text-lg">
                <svg className="w-6 h-6 fill-white" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12.067.013 1.69 5.86v12.285l10.377 5.842L22.463 18.1V5.811L12.067.013Zm.141 12.379L4.695 10.603l6.467-3.748 7.336 2.883-6.29 2.654Zm.376.541v10.513L2.613 17.511V7.7l9.97 6.233ZM12.72 13.31l9.263-4.225v8.528l-9.263 5.378v-9.68Z" /></svg>
                Sketchfab
              </div>
            </div>
          </div>

          {/* Scroll Indicator */}
          <div className="absolute bottom-8 right-12 hidden lg:flex items-center gap-3 text-xs font-semibold tracking-wider text-white/70 z-20">
            <div className="w-8 h-8 border border-white/30 rounded-full flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><polyline points="19 12 12 19 5 12"></polyline></svg>
            </div>
            SCROLL TO EXPLORE
          </div>
        </div>
      </div>
      <ProductSection />
      <UseCasesSection />
      <TestimonialSection />
      <PricingSection />
      <FooterSection />
    </div>
  )
}
