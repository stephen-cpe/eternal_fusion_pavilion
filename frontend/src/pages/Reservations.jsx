// eslint-disable-next-line no-unused-vars
import React, { useState } from 'react';
import ReservationForm from '../components/ReservationForm';
import PageHeader from '../components/PageHeader';

function Reservations() {
  return (
    <div className="min-h-screen bg-background">
        {/* Hero Section */}
        <PageHeader 
        title="Make a Reservation"
        description="Reserve your table for a dining experience that transcends borders and creates lasting memories. We look forward to welcoming you to Eternal Fusion Pavilion."
        backgroundImage="/images/reservations.jpeg"
      />
        
        {/* Reservation Form Section */}
        <section className="py-16 px-4">
          <div className="max-w-2xl mx-auto">
            <ReservationForm />
          </div>
        </section>

        {/* Reservation Information + Contact Us*/}
        <section className="py-16 px-4 bg-primary/5">
          <div className="max-w-4xl mx-auto">
            <div className="grid md:grid-cols-2 gap-12">
              {/* Reservation Information */}
              <div>
                <h2 className="text-3xl font-bold text-foreground mb-6">Reservation Information</h2>
                <div className="space-y-4 text-muted-foreground">
                  <p>
                    <strong className="text-foreground">Dining Hours:</strong><br />
                    Tuesday - Saturday: 5:00 PM – 11:00 PM<br />
                    Sunday - Monday: 5:00 PM – 9:00 PM
                  </p>
                  <p>
                    <strong className="text-foreground">Party Size:</strong><br />
                    We accommodate parties of up to 12 guests. For larger groups, please call us directly.
                  </p>
                  <p>
                    <strong className="text-foreground">Cancellation Policy:</strong><br />
                    Please notify us at least 2 hours in advance if you need to cancel or modify your reservation.
                  </p>
                </div>
              </div>

              {/* Contact Us */}
              <div>
                <h2 className="text-3xl font-bold text-foreground mb-6">Contact Us</h2>
                <div className="space-y-6">
                  {/* Milan */}
                  <div className="flex items-start space-x-3">
                    <svg className="w-6 h-6 text-icon-blue mt-1 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
                    </svg>
                    <div>
                      <p className="font-semibold">Milan, Italy</p>
                      <p className="text-muted-foreground">
                        1234 Via Della Seta, Suite 100<br />
                        +39 02 5555 1234
                      </p>
                    </div>
                  </div>

                  {/* Barcelona */}
                  <div className="flex items-start space-x-3">
                    <svg className="w-6 h-6 text-icon-blue mt-1 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
                    </svg>
                    <div>
                      <p className="font-semibold">Barcelona, Spain</p>
                      <p className="text-muted-foreground">
                        5678 Carrer de la Fusió, Suite 100<br />
                        +34 93 555 5678
                      </p>
                    </div>
                  </div>

                  {/* Tokyo */}
                  <div className="flex items-start space-x-3">
                    <svg className="w-6 h-6 text-icon-blue mt-1 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
                    </svg>
                    <div>
                      <p className="font-semibold">Tokyo, Japan</p>
                      <p className="text-muted-foreground">
                        9101 Marunouchi, Chiyoda-ku<br />
                        +81 3 5555 9101
                      </p>
                    </div>
                  </div>

                  <div className="bg-card p-6 rounded-lg mt-6">
                    <p className="text-sm text-muted-foreground">
                      For special requests, dietary restrictions, or large party reservations, please call any of our locations directly.
                      We're happy to accommodate your needs.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
    </div>
  );
}

export default Reservations;