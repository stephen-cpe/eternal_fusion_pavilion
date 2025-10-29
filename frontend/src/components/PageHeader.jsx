import React from 'react';

function PageHeader({ title, description, backgroundImage }) {
  return (
    <section className="relative py-24 px-4">
      {/* Background image container with 16:9 aspect ratio */}
      <div 
        className="absolute inset-0 bg-cover bg-center bg-no-repeat"
        style={{ 
          backgroundImage: `url(${backgroundImage})`,
        }}
      >
        {/* Dark overlay for better text readability */}
        <div className="absolute inset-0 overlay-dark"></div>
      </div>
      
      {/* Content container */}
      <div className="relative z-10 max-w-4xl mx-auto text-center text-background">
        <h1 className="text-5xl md:text-6xl font-bold mb-6 text-balance text-white">
          {title}
        </h1>
        <p className="text-xl max-w-2xl mx-auto text-pretty text-white/90">
          {description}
        </p>
      </div>
    </section>
  );
}

export default PageHeader;