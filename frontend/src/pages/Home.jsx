// frontend/src/pages/Home.jsx
import React from 'react';
import { Link } from 'react-router-dom';
import Hero from '../components/Hero';
import NewsletterSignup from '../components/NewsletterSignup';


function Home() {
  return (
    <div>
      <Hero />
      <main>
        <section className="py-16 px-4">
          <div className="max-w-4xl mx-auto text-center">
            <h2 className="text-4xl font-bold text-deep-blue mb-8">Welcome to Eternal Fusion Pavilion</h2>
            <p className="text-lg text-muted-foreground mb-12 max-w-3xl mx-auto">
              A culinary sanctuary where tradition meets innovation, crafting unforgettable experiences across three continents. We blend Japanese precision, Italian warmth, and Spanish innovation to provide a dining experience that is not just a meal, but a global sanctuary for transformative moments.
            </p>

            <div className="grid md:grid-cols-3 gap-8 mb-16">
              <div className="bg-card p-8 rounded-lg shadow-sm hover:shadow-md transition-shadow">
                <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-icon-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                </div>
                <h3 className="text-xl font-semibold mb-4">Our Menu</h3>
                <p className="text-muted-foreground mb-6">Discover our curated dishes where cultures converge on a plate, crafted with passion and precision.</p>
                <Link to="/menu" className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 border bg-background shadow-xs hover:bg-accent hover:text-accent-foreground h-9 px-4 py-2">View Menu</Link>
              </div>

              <div className="bg-card p-8 rounded-lg shadow-sm hover:shadow-md transition-shadow">
                <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-icon-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
                <h3 className="text-xl font-semibold mb-4">Make a Reservation</h3>
                <p className="text-muted-foreground mb-6">Book your table for a transformative dining experience in one of our global sanctuaries.</p>
                <Link to="/reservations" className="btn">Reserve Now</Link>
              </div>

              <div className="bg-card p-8 rounded-lg shadow-sm hover:shadow-md transition-shadow">
                 <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-icon-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
                <h3 className="text-xl font-semibold mb-4">Our Story</h3>
                <p className="text-muted-foreground mb-6">Learn how a shared passion for culinary artistry united three masters from across the globe.</p>
                <Link to="/about" className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 border bg-background shadow-xs hover:bg-accent hover:text-accent-foreground h-9 px-4 py-2">Learn More</Link>
              </div>
            </div>
          </div>
        </section>

        <section className="py-16 px-4 bg-card">
           <div className="max-w-6xl mx-auto">
                <h2 className="text-3xl font-bold text-deep-blue mb-10 text-center">Visit Us Today</h2>
                <div className="grid md:grid-cols-3 gap-12 items-start">
                    {/* Milan */}
                    <div>
                        <h3 className="text-2xl font-semibold mb-4 text-center md:text-left">Milan, Italy</h3>
                        <div className="space-y-4">
                             <div className="flex items-start space-x-3">
                                <svg className="w-6 h-6 text-icon-blue mt-1 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                                <div>
                                    <p className="font-semibold">Address</p>
                                    <p className="text-muted-foreground">1234 Via Della Seta, Suite 100<br />Milan, Italy</p>
                                </div>
                            </div>
                             <div className="flex items-start space-x-3">
                                <svg className="w-6 h-6 text-icon-blue mt-1 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" /></svg>
                                <div>
                                    <p className="font-semibold">Phone</p>
                                    <p className="text-muted-foreground">+39 02 5555 1234</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    {/* Barcelona */}
                    <div>
                        <h3 className="text-2xl font-semibold mb-4 text-center md:text-left">Barcelona, Spain</h3>
                        <div className="space-y-4">
                             <div className="flex items-start space-x-3">
                                <svg className="w-6 h-6 text-icon-bluemt-1 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                                <div>
                                    <p className="font-semibold">Address</p>
                                    <p className="text-muted-foreground">5678 Carrer de la Fusió, Suite 100<br />Barcelona, Spain</p>
                                </div>
                            </div>
                             <div className="flex items-start space-x-3">
                                <svg className="w-6 h-6 text-icon-blue mt-1 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" /></svg>
                                <div>
                                    <p className="font-semibold">Phone</p>
                                    <p className="text-muted-foreground">+34 93 555 5678</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    {/* Tokyo */}
                    <div>
                        <h3 className="text-2xl font-semibold mb-4 text-center md:text-left">Tokyo, Japan</h3>
                        <div className="space-y-4">
                             <div className="flex items-start space-x-3">
                                <svg className="w-6 h-6 text-icon-blue mt-1 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                                <div>
                                    <p className="font-semibold">Address</p>
                                    <p className="text-muted-foreground">9101 Marunouchi, Chiyoda-ku<br />Tokyo, Japan</p>
                                </div>
                            </div>
                             <div className="flex items-start space-x-3">
                                <svg className="w-6 h-6 text-icon-blue mt-1 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" /></svg>
                                <div>
                                    <p className="font-semibold">Phone</p>
                                    <p className="text-muted-foreground">+81 3 5555 9101</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div className="text-center mt-12">
                     <div className="flex items-center justify-center space-x-3">
                         <svg className="w-6 h-6 text-icon-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        <div>
                          <p className="font-semibold text-lg">Hours</p>
                          <p className="text-muted-foreground">
                            Tuesday – Saturday: 5:00 PM – 11:00 PM | Sunday - Monday: 5:00 PM – 9:00 PM
                          </p>
                        </div>
                    </div>
                </div>
            </div>
        </section>
        <NewsletterSignup />
      </main>
    </div>
  );
}

export default Home;