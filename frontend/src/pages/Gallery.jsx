// frontend/src/pages/Gallery.jsx
import React, { useState } from 'react';
import ImageGallery from '../components/ImageGallery';
import Lightbox from '../components/Lightbox';
import AwardsSection from '../components/AwardsSection';
import ReviewsSection from '../components/ReviewsSection';
import PageHeader from '../components/PageHeader';
import { galleryImages } from '../constants/galleryData';

function Gallery() {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [currentImageIndex, setCurrentImageIndex] = useState(0);
  
  const openLightbox = (index) => {
    setCurrentImageIndex(index);
    setLightboxOpen(true);
  };

  const closeLightbox = () => {
    setLightboxOpen(false);
  };

  const nextImage = () => {
    setCurrentImageIndex((prevIndex) => (prevIndex + 1) % galleryImages.length);
  };

  const prevImage = () => {
    setCurrentImageIndex((prevIndex) => (prevIndex - 1 + galleryImages.length) % galleryImages.length);
  };

  return (
    <div className="min-h-screen bg-background">
       <PageHeader 
        title="Gallery"
        description="Discover the essence of Eternal Fusion Pavilion—a curated collection of images highlighting our elegant ambiance and behind-the-scenes glimpses of our cultural collaboration."
        backgroundImage="/images/gallery.jpeg"
      />

      {/* Gallery Content Section */}
      <section className="py-16 px-4">
        <div className="site-container">
          <ImageGallery openLightbox={openLightbox} />
        </div>
      </section>

      {/* Awards Section */}
      <AwardsSection />

      {/* Reviews Section */}
      <ReviewsSection />

      {/* Lightbox Component */}
      <Lightbox
        images={galleryImages}
        currentIndex={currentImageIndex}
        isOpen={lightboxOpen}
        onClose={closeLightbox}
        onNext={nextImage}
        onPrev={prevImage}
      />
    </div>
  );
}

export default Gallery;