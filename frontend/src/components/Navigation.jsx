// frontend/src/components/Navigation.jsx
import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';

function Navigation() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const location = useLocation();
  
  // Close mobile menu when route changes
  useEffect(() => {
    setIsMenuOpen(false);
  }, [location]);

  const isActive = (path) => {
    return location.pathname === path;
  };

  const navItems = [
    { name: 'Home', path: '/' },
    { name: 'Menu', path: '/menu' },
    { name: 'Reservations', path: '/reservations' },
    { name: 'About Us', path: '/about' },
    { name: 'Gallery', path: '/gallery' }
  ];

  return (
    <nav className="bg-background shadow-md sticky top-0 z-50 backdrop-blur-sm bg-opacity-90">
      <div className="site-container px-4">
        <div className="flex justify-between items-center h-16">
          <Link to="/" className="text-2xl font-bold text-golden-brown tracking-tight hover:text-icon-blue transition-colors duration-300">
            Eternal Fusion Pavilion
          </Link>
          
          {/* Mobile menu button */}
          <button
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            className="md:hidden p-2 rounded-md hover:text-icon-blue transition-colors duration-300"
            aria-label="Toggle menu"
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          
          {/* Desktop navigation */}
          <div className="hidden md:flex space-x-1">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`relative px-4 py-2 font-medium transition-all duration-300 ${
                  isActive(item.path)
                    ? 'text-icon-blue'
                    : 'text-golden-brown hover:text-icon-blue'
                }`}
              >
                {item.name}
                {/* Active indicator */}
                {isActive(item.path) && (
                  <motion.div
                    className="absolute bottom-0 left-0 right-0 h-0.5 bg-icon-blue"
                    layoutId="navIndicator"
                    initial={false}
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                  />
                )}
              </Link>
            ))}
          </div>
        </div>
        
        {/* Mobile navigation */}
        {isMenuOpen && (
          <motion.div 
            className="md:hidden py-4 border-t border-border"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
          >
            <div className="flex flex-col space-y-1">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`block px-3 py-2 rounded-md transition-all duration-300 ${
                    isActive(item.path)
                      ? 'text-icon-blue bg-muted/50 border-l-4 border-icon-blue'
                      : 'text-golden-brown hover:text-icon-blue hover:bg-muted'
                  }`}
                  onClick={() => setIsMenuOpen(false)}
                >
                  {item.name}
                </Link>
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </nav>
  );
}

export default Navigation;