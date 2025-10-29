// frontend/src/components/RestaurantName.jsx
import React from 'react';

const RestaurantName = ({ 
  outlineWidth = 1,      // Width of the outline in pixels
  outlineColor = 'black', // Color of the outline
  textColor = 'white',    // Color of the text itself
  hoverScale = 1.05       // Scale factor on hover
}) => {
  return (
    <h1 
      className="text-7xl md:text-9xl font-bold mb-4 text-balance tracking-wide transition-all duration-300"
      style={{
        color: textColor,
        WebkitTextStroke: `${outlineWidth}px ${outlineColor}`,
        textStroke: `${outlineWidth}px ${outlineColor}` // Standard property for future compatibility
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = `scale(${hoverScale})`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'scale(1)';
      }}
    >
      Eternal Fusion Pavilion
    </h1>
  );
};

export default RestaurantName;