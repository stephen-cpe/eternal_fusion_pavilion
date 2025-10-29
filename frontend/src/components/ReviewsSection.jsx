import React from 'react';

function ReviewsSection() {
  const reviews = [
    {
      quote: "A transcendent culinary journey. Each dish is a masterpiece.",
      source: "The International Food Critic",
      rating: 5
    },
    {
      quote: "The pinnacle of fine dining. Flawless service and unforgettable flavors.",
      source: "Epicurean Weekly",
      rating: 5
    },
    {
      quote: "Eternal Fusion Pavilion doesn't just serve food, it serves art.",
      source: "Culinary Horizons Journal",
      rating: 5
    },
    {
      quote: "An experience that redefines what a restaurant can be. Absolutely breathtaking.",
      source: "The Elite Culinary Palate",
      rating: 5
    }
  ];

  const renderStars = (rating) => {
    return (
      <div className="flex text-yellow-400 justify-center">
        {[...Array(5)].map((_, i) => (
          <svg 
            key={i}
            className={`w-5 h-5 ${i < rating ? 'fill-current' : 'stroke-current'}`}
            viewBox="0 0 24 24"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth="2"
              d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
            />
          </svg>
        ))}
      </div>
    );
  };

  return (
    <section className="py-16 px-4">
      <div className="site-container">
        <div className="bg-card p-8 rounded-lg shadow-sm mb-12 text-center">
          <h2 className="text-3xl font-bold text-deep-blue mb-4">What Our Guests Say</h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Don't just take our word for it. Here's what critics and valued guests have to say about their dining experience at Eternal Fusion Pavilion.
          </p>
        </div>
        
        <div className="flex justify-center">
          <div className="grid md:grid-cols-2 gap-8 max-w-5xl">
            {reviews.map((review, index) => (
              <div key={index} className="bg-card p-6 rounded-lg shadow-lg border border-border">
                <div className="flex flex-col h-full">
                  <div className="mb-4">
                    {renderStars(review.rating)}
                  </div>
                  <blockquote className="text-lg text-deep-blue italic flex-grow text-center">
                    "{review.quote}"
                  </blockquote>
                  <footer className="mt-4 text-golden-brown font-semibold text-center">
                    {review.source}
                  </footer>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export default ReviewsSection;