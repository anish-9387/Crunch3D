import React, { useState } from 'react';

export default function PricingSection() {
  const [isYearly, setIsYearly] = useState(false);

  const plans = [
    {
      name: 'Free',
      subtitle: 'For curious minds',
      basePrice: 0,
      period: '/ month',
      img: '/assets/pricingfree.png',
      imgOffset: 'translate-y-6',
      annotation: 'Just exploring?',
      features: [
        'Basic mesh optimization',
        'Standard file sizes',
        'Community support'
      ],
      buttonText: 'Get Started',
      buttonStyle: 'border border-[#F26522] text-[#F26522] hover:bg-[#F26522] hover:text-white',
    },
    {
      name: 'Pro',
      subtitle: 'For creators & professionals',
      basePrice: 999,
      period: '/ month',
      img: '/assets/pricingpro.png',
      imgOffset: 'translate-y-2',
      annotation: 'This feels right!',
      isPopular: true,
      features: [
        'Everything in Free',
        'Advanced optimization',
        'Higher file limits',
        'Priority support',
        'Early access to new features'
      ],
      buttonText: 'Choose Pro',
      buttonStyle: 'bg-[#F26522] text-white hover:bg-[#d8561b] shadow-lg shadow-orange-500/30',
    },
    {
      name: 'Enterprise',
      subtitle: 'For teams & organizations',
      basePrice: 'Custom',
      period: '',
      img: '/assets/pricingenterprise.png',
      imgOffset: 'translate-y-1',
      annotation: 'Scale bigger.',
      features: [
        'Everything in Pro',
        'Custom limits',
        'Dedicated support',
        'SLA & compliance',
        'Custom integrations'
      ],
      buttonText: 'Contact Sales',
      buttonStyle: 'border border-gray-300 text-gray-700 hover:bg-gray-50',
    }
  ];

  return (
    <section id="pricing" className="relative w-full min-h-[92vh] flex flex-col justify-center py-10 z-30" style={{ backgroundColor: '#F26522' }}>
      <div className="w-full max-w-[1400px] mx-auto px-3 md:px-6 lg:px-12 relative z-10 flex flex-col justify-center h-full">
        
        {/* Header */}
        <div className="flex flex-col items-center text-center gap-4 mb-6 relative">
          <div className="bg-white/20 text-white backdrop-blur-md text-[11px] font-bold tracking-widest px-4 py-1.5 rounded-full uppercase font-poppins border border-white/30">
            PRICING
          </div>
          
          <h2 className="text-[32px] md:text-[50px] font-black text-white leading-tight uppercase" style={{ fontFamily: "'Fredoka', sans-serif" }}>
            Built for every builder.
          </h2>
          
          <p className="max-w-2xl text-white/90 text-sm md:text-base font-poppins font-light leading-relaxed">
            Simple, transparent pricing. No hidden fees. Upgrade or downgrade anytime.
          </p>

          {/* Toggle */}
          <div className="flex items-center gap-1 mt-4 bg-white/20 backdrop-blur-md p-1.5 rounded-full border border-white/30">
            <button 
              onClick={() => setIsYearly(false)} 
              className={`px-6 py-2 rounded-full text-sm font-semibold transition-all ${!isYearly ? 'bg-white text-[#F26522] shadow-sm' : 'text-white hover:bg-white/10'}`}
            >
              Monthly
            </button>
            <button 
              onClick={() => setIsYearly(true)} 
              className={`px-6 py-2 rounded-full text-sm font-semibold transition-all flex items-center gap-2 ${isYearly ? 'bg-white text-[#F26522] shadow-sm' : 'text-white hover:bg-white/10'}`}
            >
              Yearly
              <span className={`text-[10px] px-2 py-0.5 rounded-full ${isYearly ? 'bg-orange-100 text-[#F26522]' : 'bg-[#F26522] text-white'}`}>Save 20%</span>
            </button>
          </div>
        </div>

        {/* Pricing Cards */}
        <div className="w-full grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8 mt-8 md:mt-12 max-w-6xl mx-auto items-stretch px-2 md:px-0">
          {plans.map((plan, idx) => (
            <div key={idx} className={`relative bg-gradient-to-b from-[#ffeddf] to-[#fff5ec] rounded-[32px] overflow-visible flex flex-col shadow-2xl p-1.5 md:p-2 lg:p-3 pt-6 lg:pt-8 transition-transform hover:-translate-y-2 ${plan.isPopular ? 'border-4 border-white ring-4 ring-[#F26522]/30 z-10 scale-100 md:scale-[1.02]' : 'border border-white/50'}`}>
              
              {plan.isPopular && (
                <div className="absolute -top-5 left-1/2 -translate-x-1/2 bg-[#F26522] text-white px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 shadow-lg z-20 border-2 border-white whitespace-nowrap">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                  Most Popular
                </div>
              )}

              {/* Image Section (Top Half) */}
              <div className="h-[180px] lg:h-[200px] w-full relative z-30 flex justify-center items-end">
                <img src={plan.img} alt={plan.name} className={`h-[120%] w-auto object-contain object-bottom drop-shadow-[0_-10px_15px_rgba(0,0,0,0.1)] ${plan.imgOffset || ''}`} />
              </div>

              {/* Content Section (Inner White Card) */}
              <div className="p-4 md:p-6 flex flex-col flex-1 bg-white rounded-[24px] z-20 shadow-sm relative">
                <h3 className="font-bold text-[28px] text-gray-900 leading-none">{plan.name}</h3>
                <p className="text-gray-500 text-[13px] font-medium mt-1">{plan.subtitle}</p>
                
                <div className="flex items-end gap-1 mt-4 mb-5 h-12">
                  {isYearly && typeof plan.basePrice === 'number' && plan.basePrice > 0 ? (
                    <div className="flex flex-col items-start justify-end h-full">
                      <span className="line-through text-gray-400 text-[16px] font-bold leading-none mb-1" style={{ fontFamily: "'Fredoka', sans-serif" }}>₹{plan.basePrice}</span>
                      <span className="text-[32px] font-black text-gray-900 leading-none" style={{ fontFamily: "'Fredoka', sans-serif" }}>₹{Math.floor(plan.basePrice * 0.8)}</span>
                    </div>
                  ) : (
                    <span className="text-[32px] font-black text-gray-900 leading-none h-full flex items-end" style={{ fontFamily: "'Fredoka', sans-serif" }}>
                      {plan.basePrice === 0 ? '₹0' : (plan.basePrice === 'Custom' ? 'Custom' : `₹${plan.basePrice}`)}
                    </span>
                  )}
                  <span className="text-gray-500 font-medium mb-0.5">{plan.period}</span>
                </div>

                <div className="flex-1 flex flex-col gap-2.5">
                  {plan.features.map((feat, fidx) => (
                    <div key={fidx} className="flex items-start gap-2">
                      <div className="w-4 h-4 rounded-full bg-orange-100 text-[#F26522] flex items-center justify-center flex-shrink-0 mt-0.5">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                      </div>
                      <span className="text-gray-600 text-[13px] font-medium">{feat}</span>
                    </div>
                  ))}
                </div>

                <button className={`w-full py-3 mt-6 rounded-full font-bold text-sm flex items-center justify-center gap-2 transition-all ${plan.buttonStyle}`}>
                  {plan.buttonText}
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                </button>
              </div>
            </div>
          ))}
        </div>

      </div>
    </section>
  );
}
