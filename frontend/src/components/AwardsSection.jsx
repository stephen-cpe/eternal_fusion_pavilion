import React from 'react';

function AwardsSection() {
  const awards = [
    {
      title: "Masters of Culinary Craft Award",
      year: "2025",
      organization: "International Academy of Culinary Arts",
      icon: (
        <svg className="w-8 h-8 text-icon-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7.21 15 2.66 7.14a2 2 0 0 1 .13-2.2L4.4 2.8A2 2 0 0 1 6 2h12a2 2 0 0 1 1.6.8l1.6 2.14a2 2 0 0 1 .14 2.2L16.79 15"/><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
        d="M11 12 5.12 2.2"/><path strokeLinecap="round" strokeLinejoin="round"  strokeWidth={2} d="m13 12 5.88-9.8"/><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h8"/><circle strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} cx="12" cy="17" r="5"/><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18v-2h-.5"/></svg>
      )
    },
    {
      title: "World Fusion Culinary Artistry Award",
      year: "2025",
      organization: "Global Culinary Times",
      icon: (
        <svg className="w-8 h-8 text-icon-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 
        4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" /></svg>
      )
    },
    {
      title: "International Epicurean Innovation Award",
      year: "2026",
      organization: "World Culinary Alliance",
      icon: (
        <svg className="w-8 h-8 text-icon-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" strokeWidth={2} d="M16.5 18.75h-9m9 0a3 3 0 
          0 1 3 3h-15a3 3 0 0 1 3-3m9 0v-3.375c0-.621-.503-1.125-1.125-1.125h-.871M7.5 18.75v-3.375c0-.621.504-1.125 1.125-1.125h.872m5.007 0H9.497m5.007 0a7.454 7.454 0 0 1-.982-3.172M9.497 14.25a7.454 7.454 0 0 0 .981-3.172M5.25 4.236c-.982.143-1.954.317-2.916.52A6.003 6.003 0 0 0 7.73 9.728M5.25 4.236V4.5c0 2.108.966 3.99 2.48 5.228M5.25 4.236V2.721C7.456 2.41 9.71 2.25 12 2.25c2.291 0 4.545.16 6.75.47v1.516M7.73 9.728a6.726 6.726 0 0 0 2.748 1.35m8.272-6.842V4.5c0 2.108-.966 3.99-2.48 5.228m2.48-5.492a46.32 46.32 0 0 1 2.916.52 6.003 6.003 0 0 1-5.395 4.972m0 0a6.726 6.726 0 0 1-2.749 1.35m0 0a6.772 6.772 0 0 1-3.044 0" /></svg>
      )
    },
    {
      title: "Culinary Vanguard Award",
      year: "2026",
      organization: "Restaurant & Hotel Magazine",
      icon: (
        <svg className="w-8 h-8 text-icon-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 
        00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" /></svg>
      )
    }
  ];

  return (
    <section className="py-16 px-4">
      <div className="site-container">
        <div className="bg-card p-8 rounded-lg shadow-sm mb-12 text-center">
          <h2 className="text-3xl font-bold text-deep-blue mb-4">Awards & Recognition</h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Globally recognized for our commitment to culinary innovation, fusion artistry, and exceptional service.
          </p>
        </div>
        
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
          {awards.map((award, index) => (
            <div key={index} className="bg-background p-8 rounded-lg shadow-2xl text-center">
              <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                {award.icon}
              </div>
              <h3 className="text-xl font-semibold text-golden-brown mb-2">{award.title}</h3>
              <p className="text-primary font-semibold text-lg mb-1">{award.year}</p>
              {award.organization && <p className="text-muted-foreground text-sm">{award.organization}</p>}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default AwardsSection;