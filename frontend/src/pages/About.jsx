import React from 'react';
import { Link } from 'react-router-dom';
import PageHeader from '../components/PageHeader';

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-background">
      <PageHeader 
        title="About Eternal Fusion Pavilion"
        description="A culinary sanctuary where tradition meets innovation, crafting unforgettable experiences across three continents."
        backgroundImage="/images/about.jpeg"
      />
        
      <section className="py-16 px-4">
        <div className="max-w-4xl mx-auto text-center">
            <h2 className="text-3xl font-bold text-deep-blue mb-6">Our Story</h2>
            <p className="text-lg text-muted-foreground leading-relaxed">
              The vision for Eternal Fusion Pavilion was born from a shared passion for culinary artistry, sparked during a young Japanese chef's travels through the vibrant kitchens of Italy and Spain. Inspired by the rich cultural traditions and professional excellence she encountered, Chef Michiko Hayashi forged lifelong connections with two remarkable talents: Chef Giovanni Castellani, whose Italian roots breathe soul into every dish, and Doña Esperanza Valdez, a master of Spanish hospitality. Years later, after achieving global acclaim, Michiko reunited with these accomplished professionals to create a restaurant that transcends borders. Together, they assembled an international dream team, blending Japanese precision, Italian warmth, and Spanish innovation into a dining experience that is not just a meal, but a global sanctuary for transformative moments.
            </p>
        </div>
      </section>

      <section className="py-16 px-4">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-4xl font-bold text-deep-blue mb-12 text-center">Meet Our Founders</h2>
          <div className="grid md:grid-cols-1 lg:grid-cols-3 gap-8">
            
            {/* Chef Michiko Hayashi */}
            <div className="bg-background p-8 rounded-lg shadow-2xl flex flex-col bg-card">
              <div className="flex flex-col items-center text-center">
                <img src="Chef-Michiko-profile.png" alt="Chef Michiko Hayashi" className="w-60 h-60 rounded-full object-cover mb-6" />
                <h3 className="text-2xl font-bold text-deep-blue mb-2">Chef Michiko Hayashi</h3>
                <p className="text-golden-brown font-semibold mb-4 ">Chef-Patron & Creative Director</p>
                <p className="text-muted-foreground leading-relaxed">
                  At just 31, Chef Michiko earned her third Michelin star, becoming one of the youngest chefs ever to reach this pinnacle. Her journey led her from Tokyo's most prestigious ryokans to the kitchens of Milan and Barcelona, where she perfected a unique blend of Eastern precision and Western innovation. Her philosophy is rooted in shokunin — the relentless pursuit of perfection through craft.
                </p>
              </div>
            </div>

            {/* Chef Giovanni Castellani */}
            <div className="bg-background p-8 rounded-lg shadow-2xl flex flex-col bg-card">
              <div className="flex flex-col items-center text-center">
                <img src="chef-giovanni-profile.png" alt="Chef Giovanni Castellani" className="w-60 h-60 rounded-full object-cover mb-6" />
                <h3 className="text-2xl font-bold text-deep-blue mb-2">Chef Giovanni Castellani</h3>
                <p className="text-golden-brown font-semibold mb-4">Culinary Architect & Innovation Director</p>
                <p className="text-muted-foreground leading-relaxed">
                   Born in Chianti, Giovanni inherited a reverence for terroir. After apprenticing at the three-Michelin-starred Enoteca Pinchiorri, he led the pasta station at Osteria Francescana during its reign as World's Best. His reputation is for cuisine that reads like a story without words, channeling Italian heritage through a global lens to connect cultures.
                </p>
              </div>
            </div>

            {/* Doña Esperanza Valdez */}
            <div className="bg-background p-8 rounded-lg shadow-2xl flex flex-col bg-card">
              <div className="flex flex-col items-center text-center">
                <img src="dona-esperanza-1.png" alt="Doña Esperanza Valdez" className="w-60 h-60 rounded-full object-cover mb-6" />
                <h3 className="text-2xl font-bold text-deep-blue mb-2">Doña Esperanza Valdez</h3>
                <p className="text-golden-brown font-semibold mb-4">Restaurateur & Experience Director</p>
                <p className="text-muted-foreground leading-relaxed">
                  Raised in her family's Barcelona tapas bar, Esperanza's genius lies in orchestrating the intangible elements of hospitality. She studied not only restaurants but theaters, museums, and luxury spas to understand how spaces shape emotions. To her, hospitality is a form of meditation—a practice of being fully present for another's experience.
                </p>
              </div>
            </div>

          </div>
        </div>
      </section>
      
      <section className="py-16 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-4xl font-bold text-deep-blue mb-6">Our Philosophy</h2>
          <p className="text-lg text-muted-foreground leading-relaxed">
            We believe the finest ingredients, mastered techniques, and heartfelt service create moments of pure magic. Each dish at Eternal Fusion Pavilion is a collaboration between cultures, a dialogue between tradition and innovation, and an invitation to experience something truly extraordinary.
          </p>
        </div>
      </section>

      <section className="py-16 px-4 bg-card">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-4xl font-bold text-deep-blue mb-12 text-center">Our Commitment</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-icon-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" /></svg>
              </div>
              <h3 className="text-xl font-semibold text-deep-blue mb-4">Ethical Sourcing</h3>
              <p className="text-muted-foreground">
                We partner with small-scale farmers in Japan, Italy, and Spain to honor the planet and support the artisans who make our fusion possible.
              </p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-icon-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" /></svg>
              </div>
              <h3 className="text-xl font-semibold text-deep-blue mb-4">Sustainability</h3>
              <p className="text-muted-foreground">
                From implementing zero-waste practices in our kitchens, we commit to ensuring every meal not only delights but also contributes to a better world.
              </p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-icon-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
              </div>
              <h3 className="text-xl font-semibold text-deep-blue mb-4">Community Impact</h3>
              <p className="text-muted-foreground">
                We are dedicated to fostering community by supporting local artisans and creating a space where connections are forged over exceptional food.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-16 px-4 bg-primary/5">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-deep-blue mb-4">Our Promise</h2>
          <p className="text-lg text-muted-foreground mb-8">
            To craft not just meals, but memories that last forever. Every visit to Eternal Fusion Pavilion is designed to be a transformative journey that engages all your senses and creates lasting impressions.
          </p>
          <div className="space-x-4">
            <Link to="/reservations" className="btn">
              Make a Reservation
            </Link>
            <Link to="/menu" className="btn-outline">
              View Our Menu
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}