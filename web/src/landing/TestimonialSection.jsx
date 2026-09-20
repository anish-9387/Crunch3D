import React from 'react';

const testimonialsRow1 = [
  { name: 'Aarav P.', role: 'Game Developer', rating: 5, text: 'Crunch3D completely changed our workflow. We optimized our entire game map in hours instead of weeks.' },
  { name: 'Priya S.', role: '3D Artist', rating: 4, text: 'The quality retention is insane. It drops the polygon count by 90% but you literally cannot tell the difference visually.' },
  { name: 'Rahul K.', role: 'AR/VR Engineer', rating: 5, text: 'Our mobile VR app was struggling with performance until we crunched all our meshes. Now it runs at a buttery smooth 90fps.' },
  { name: 'Neha G.', role: 'Technical Artist', rating: 4, text: 'The LOD generation alone is worth it. It creates perfect simplified versions with a single click.' },
];

const testimonialsRow2 = [
  { name: 'Vikram D.', role: 'Indie Creator', rating: 5, text: 'Finally an optimizer that just works. I throw anything at it, and it gives me a perfectly clean, low-poly mesh back.' },
  { name: 'Anjali M.', role: 'VFX Supervisor', rating: 3, text: 'Saves us massive amounts of time on background assets. A must-have tool for any serious 3D pipeline.' },
  { name: 'Karthik R.', role: 'E-commerce', rating: 5, text: 'Loading 3D products on our website used to take forever. Crunch3D made them lightweight without losing any detail.' },
  { name: 'Sneha V.', role: 'Studio Head', rating: 4, text: 'We scaled our asset production massively. The automated optimization integrates seamlessly into our build process.' },
];

const StarRating = ({ rating }) => (
  <div className="flex gap-1 mb-4">
    {[...Array(5)].map((_, i) => (
      <svg key={i} width="18" height="18" viewBox="0 0 24 24" fill={i < rating ? "#F26522" : "#ffe0d1"} className="drop-shadow-sm">
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
      </svg>
    ))}
  </div>
);

const TestimonialCard = ({ name, role, text, rating }) => (
  <div className="w-[280px] md:w-[420px] bg-white rounded-2xl p-6 md:p-8 shadow-xl flex-shrink-0 mx-3 md:mx-4 border border-gray-100 flex flex-col justify-between transition-transform hover:-translate-y-1">
    <div>
      <StarRating rating={rating} />
      <p className="text-gray-700 font-poppins text-sm md:text-base leading-relaxed mb-6 md:mb-8 font-medium">"{text}"</p>
    </div>
    <div className="flex items-center gap-3 md:gap-4">
      <div className="w-10 h-10 md:w-12 md:h-12 rounded-full bg-gradient-to-tr from-[#F26522] to-[#FF8A47] flex items-center justify-center text-white font-black text-base md:text-lg shadow-md">
        {name.charAt(0)}
      </div>
      <div className="flex flex-col">
        <span className="font-bold text-gray-900 text-sm md:text-base">{name}</span>
        <span className="text-[#F26522] text-[10px] md:text-xs font-bold uppercase tracking-widest mt-0.5">{role}</span>
      </div>
    </div>
  </div>
);

export default function TestimonialSection() {
  return (
    <section className="relative w-full py-16 md:py-24 overflow-hidden" style={{ backgroundColor: '#F26522' }}>
      <style>{`
        @keyframes scroll-left {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        @keyframes scroll-right {
          0% { transform: translateX(-50%); }
          100% { transform: translateX(0); }
        }
        .animate-scroll-left {
          animation: scroll-left 35s linear infinite;
        }
        .animate-scroll-right {
          animation: scroll-right 35s linear infinite;
        }
        .animate-scroll-left:hover, .animate-scroll-right:hover {
          animation-play-state: paused;
        }
      `}</style>
      
      <div className="w-full flex flex-col items-center relative z-10 mb-10 md:mb-16 px-4 md:px-6">
        <div className="bg-white/20 text-white backdrop-blur-md text-[10px] md:text-[11px] font-bold tracking-widest px-4 py-1.5 rounded-full uppercase font-poppins mb-4 md:mb-6 border border-white/30">
          Wall of Love
        </div>
        
        <h2 className="text-[32px] md:text-[54px] font-black text-white leading-tight text-center" style={{ fontFamily: "'Fredoka', sans-serif" }}>
          Don't just take <span className="text-white/80">our word for it.</span>
        </h2>
      </div>

      <div className="relative w-full flex flex-col gap-6 md:gap-8 flex-nowrap py-4 md:py-6">
        {/* Row 1 - Moving Left */}
        <div className="flex w-max animate-scroll-left items-stretch">
          {[...testimonialsRow1, ...testimonialsRow1].map((t, i) => (
            <TestimonialCard key={i} {...t} />
          ))}
        </div>

        {/* Row 2 - Moving Right */}
        <div className="flex w-max animate-scroll-right items-stretch">
          {[...testimonialsRow2, ...testimonialsRow2].map((t, i) => (
            <TestimonialCard key={i} {...t} />
          ))}
        </div>
        
        {/* Gradient Edges for smooth fading (matching background color) */}
        <div className="absolute inset-y-0 left-0 w-8 md:w-[200px] pointer-events-none z-20" style={{ background: 'linear-gradient(to right, #F26522, transparent)' }}></div>
        <div className="absolute inset-y-0 right-0 w-8 md:w-[200px] pointer-events-none z-20" style={{ background: 'linear-gradient(to left, #F26522, transparent)' }}></div>
      </div>
    </section>
  );
}
