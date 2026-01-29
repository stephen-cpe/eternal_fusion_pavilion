// frontend/src/components/Hero.jsx
import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import RestaurantName from './RestaurantName';

const heroVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      delayChildren: 0.3,
      staggerChildren: 0.3,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.8, ease: "easeOut" }
  },
};


function Hero() {
  return (
    <section className="relative h-screen flex items-center justify-center">
      <div
        className="absolute inset-0 bg-cover bg-center bg-no-repeat"
        style={{
          backgroundImage: "url('/images/eternal-fusion-pavillion-main.jpeg')",
        }}
      >
        <div className="absolute inset-0 overlay-dark"></div>
      </div>
      <div className="relative z-10 text-center text-background max-w-4xl mx-auto px-4">

        <motion.div
          variants={heroVariants}
          initial="hidden"
          animate="visible"
        >

          <motion.div variants={itemVariants}>
            <RestaurantName
              outlineWidth={4.0}
              outlineColor="#539394"
              textColor="white"
            />
          </motion.div>

          <motion.p
            variants={itemVariants}
            className="text-xl md:text-2xl mb-8 text-pretty max-w-2xl mx-auto text-white rye-regular"
          >
            A sanctuary where Japanese precision, Italian warmth, and Spanish innovation converge for an unforgettable dining experience.
          </motion.p>

          <motion.div
            variants={itemVariants}
            className="space-x-4"
          >
            <Link
              to="/reservations"
              className="btn"
            >
              Make a Reservation
            </Link>
            <Link
              to="/menu"
              className="btn-outline"
            >
              View Menu
            </Link>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}

export default Hero;