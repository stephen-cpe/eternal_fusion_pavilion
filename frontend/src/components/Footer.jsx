// frontend/src/components/Footer.jsx
import React from 'react';
function Footer() {
  return (
    <footer className="bg-footer-bg text-white py-12 mt-16 [&_p]:text-white [&_p]:text-base justify-items-center">
      <div className="container px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-8">
          {/* Branding */}
          <div className="flex flex-col">
            <h3 className="text-3xl font-bold text-golden-brown mb-4 tracking-tight">Eternal Fusion Pavilion</h3>
            <p className="text-white/90 mb-4 text-lg flex-grow">A culinary sanctuary across three continents.</p>
          </div>
          {/* Milan Location */}
          <div>
            <h4 className="text-xl font-semibold mb-4 text-white">Milan, Italy</h4>
            <div className="space-y-2 text-white/90">
              <p className="flex">
                <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                1234 Via Della Seta, Suite 100
              </p>
              <p className="flex">
                <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                </svg>
                +39 02 5555 1234
              </p>
            </div>
          </div>
          {/* Barcelona Location */}
          <div>
            <h4 className="text-xl font-semibold mb-4 text-white">Barcelona, Spain</h4>
            <div className="space-y-2 text-white/90">
              <p className="flex">
                <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                5678 Carrer de la Fusió, Suite 100
              </p>
              <p className="flex">
                <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                </svg>
                +34 93 555 5678
              </p>
            </div>
          </div>
          {/* Tokyo Location */}
          <div>
            <h4 className="text-xl font-semibold mb-4 text-white">Tokyo, Japan</h4>
            <div className="space-y-2 text-white/90">
              <p className="flex">
                <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                9101 Marunouchi, Chiyoda-ku
              </p>
              <p className="flex">
                <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                </svg>
                +81 3 5555 9101
              </p>
            </div>
          </div>
          {/* Hours Section */}
          <div>
            <h4 className="text-lg font-semibold tracking-wide text-white mb-4">Hours</h4>
            <div className="space-y-2 text-white/90">
              <p className="flex">
                <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Tuesday - Saturday: 5:00 PM – 11:00 PM
              </p>
              <p className="flex">
                <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Sunday - Monday: 5:00 PM – 9:00 PM
              </p>
            </div>
          </div>
        </div>
        <div className="border-t border-accent/30 mt-8 pt-8 text-center text-white/70">
          <p>&copy; {new Date().getFullYear()} Eternal Fusion Pavilion. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}
export default Footer;