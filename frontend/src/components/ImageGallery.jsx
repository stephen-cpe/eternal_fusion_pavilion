// frontend/src/components/ImageGallery.jsx
import React from 'react';
import { motion } from 'framer-motion';
import { galleryImages } from '../constants/galleryData';

const galleryVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6 } },
};

function ImageGallery({ openLightbox }) {
  return (

    <motion.div
      className="grid md:grid-cols-3 lg:grid-cols-4 gap-6"
      variants={galleryVariants}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, amount: 0.2 }}
    >
      {galleryImages.map((img, idx) => (
  
        <motion.div
          key={idx}
          className="group relative overflow-hidden rounded-xl shadow-md cursor-pointer"
          onClick={() => openLightbox(idx)}
          whileHover={{ y: -8, scale: 1.03 }}
          whileTap={{ scale: 0.98 }}
          transition={{ type: 'spring', stiffness: 300, damping: 20 }}
          variants={itemVariants}
        >
          <img
            src={img.src}
            alt={img.alt}
            className="w-full h-64 object-cover"
          />
          <div className="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center p-4">
            <p className="text-white font-semibold text-center">{img.alt}</p>
          </div>
        </motion.div>
      ))}
    </motion.div>
  );
}

export default ImageGallery;