// frontend/src/pages/Menu.jsx
import React, { useState } from 'react';
import { motion } from 'framer-motion';
import Lightbox from '../components/Lightbox';
import PageHeader from '../components/PageHeader';

const gridContainerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
};

const gridItemVariants = {
  hidden: { opacity: 0, y: 20, scale: 0.95 },
  visible: { 
    opacity: 1, 
    y: 0, 
    scale: 1,
    transition: { duration: 0.5, ease: 'easeOut' }
  },
};

function Menu() {
  const menuSections = [
    {
      title: "Starters",
      items: [
        { src: "/images/bruschetta-trilogy.png", name: "Bruschetta Trilogy", description: "Heirloom tomato with aged balsamic, white bean truffle purée, and Iberico ham with piquillo peppers", price: "$24.00" },
        { src: "/images/Kaiseki-Caesar.png", name: "Kaiseki Caesar", description: "Baby gem lettuce, house-cured bottarga, shiso Caesar dressing, parmesan tuile, and tempura anchovy", price: "$26.00" },
        { src: "/images/Bluefin-Tuna-Crudo.png", name: "Bluefin Tuna Crudo", description: "Akami and chu-toro, Sicilian blood orange, shaved fennel, Arbequina olive oil, and togarashi salt", price: "$38.00" },
        { src: "/images/pulpo-carpaccio.png", name: "Pulpo Carpaccio", description: "Sous-vide Galician octopus, charred padron peppers, nduja vinaigrette, and micro basil", price: "$32.00" },
      ],
    },
    {
      title: "Main Courses",
      items: [
        { src: "/images/Miso-Glazed-King-Salmon.png", name: "Miso-Glazed King Salmon", description: "Saikyo miso marinade, roasted San Marzano tomatoes, saffron beurre blanc, and grilled asparagus", price: "$58.00" },
        { src: "/images/A5-Wagyu-Ribeye.png", name: "A5 Wagyu Ribeye", description: "8 oz Miyazaki beef, bone marrow salsa verde, patatas bravas, and aged Parmigiano-Reggiano", price: "$165.00" },
        { src: "/images/Truffle-Risotto.png", name: "Truffle Risotto", description: "Carnaroli rice, Périgord truffle, porcini dashi, aged Grana Padano, and truffle foam", price: "$48.00" },
        { src: "/images/Lobster-Paella-Negra.png", name: "Lobster Paella Negra", description: "Maine lobster, squid ink bomba rice, spot prawns, sofrito, and alioli espuma", price: "$78.00" },
        { src: "/images/Duck-Confit-Ramen.png", name: "Duck Confit Ramen", description: "48-hour tonkotsu-duck broth, handmade pasta, foie gras butter, Iberico pancetta, and soft quail egg", price: "$65.00" },
        { src: "/images/Branzino-en-Papillote.png", name: "Branzino en Papillote", description: "Mediterranean sea bass, uni butter, shaved bottarga, baby vegetables, and sake-vermouth reduction", price: "$72.00" },
      ],
    },
    {
       title: "Desserts",
       items: [
         { src: "/images/Deconstructed-Tiramisu.png", name: "Deconstructed Tiramisu", description: "Espresso-soaked savoiardi, mascarpone mousse, Valrhona cocoa dust, and gold leaf", price: "$22.00" },
         { src: "/images/Basque-Burnt-Cheesecake.png", name: "Basque Burnt Cheesecake", description: "Idiazábal cheese blend, yuzu curd, black sesame crumble, and seasonal berry compote", price: "$24.00" },
         { src: "/images/Matcha-Flan.png", name: "Matcha Flan", description: "Ceremonial grade matcha custard, Pedro Ximénez caramel, candied ginger, and almond florentine", price: "$20.00" },
         { src: "/images/choco-souffle.png", name: "Chocolate Soufflé", description: "Valrhona Guanaja 70%, miso caramel center, vanilla gelato, and edible flowers", price: "$26.00" },
       ],
    },
    {
      title: "Beverages",
      items: [
        { src: "/images/Red-Wine-Selection.png", name: "Red Wine Selection", description: "Curated selection of Barolo, Rioja Gran Reserva, and premium Japanese wines", price: "$28.00" },
        { src: "/images/White-Wine-Selection.jpeg", name: "White Wine Selection", description: "Featuring Albariño, Soave Classico, and Koshu wines", price: "$24.00" },
        { src: "/images/Artisan-Beer-Selection.png", name: "Artisan Beer Selection", description: "Japanese craft ales, Italian birra artigianale, Spanish craft cervezas", price: "$15.00" },
        { src: "/images/Espresso-Service.png", name: "Espresso Service", description: "Single origin beans, traditional or shakerato preparation", price: "$11.00" },
        { src: "/images/Premium-Sake-Flight.png", name: "Premium Sake Flight", description: "Three expressions: Junmai Daiginjo, aged Koshu, and sparkling nigori", price: "$35.00" },
        { src: "/images/Signature-Cocktails.png", name: "Signature Cocktails", description: "Yuzu Negroni, Cava Sangria, Umami Martini with white miso and sake", price: "$22.00" },
      ],
    },
  ];

  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [currentImageIndex, setCurrentImageIndex] = useState(0);
  const menuImages = menuSections.flatMap(section =>
    section.items.map(item => ({
      src: item.src,
      alt: item.name
    }))
  );
  const openLightbox = (index) => {
    setCurrentImageIndex(index);
    setLightboxOpen(true);
  };
  const closeLightbox = () => {
    setLightboxOpen(false);
  };
  const nextImage = () => {
    setCurrentImageIndex((prevIndex) => (prevIndex + 1) % menuImages.length);
  };
  const prevImage = () => {
    setCurrentImageIndex((prevIndex) => (prevIndex - 1 + menuImages.length) % menuImages.length);
  };

  return (
    <div className="min-h-screen bg-background">
      <PageHeader
        title="Our Menu"
        description="A symphony of flavors where Japanese precision, Italian soul, and Spanish passion unite on every plate."
        backgroundImage="/images/menu.jpeg"
      />

      <section className="relative py-24 px-4">
        <div className="site-container">

          {menuSections.map((section, sectionIndex) => (
            <div key={sectionIndex} className="mb-20">
              <h2 className="text-3xl font-bold text-deep-blue mb-10 text-center">{section.title}</h2>
              {/* 3. Apply variants to the grid container */}
              <motion.div
                className="grid grid-cols-1 md:grid-cols-2 gap-8"
                variants={gridContainerVariants}
                initial="hidden"
                whileInView="visible" // Animate when it scrolls into view
                viewport={{ once: true, amount: 0.2 }} // Options for whileInView
              >
                {section.items.map((item, itemIndex) => {
                  const globalIndex = menuSections
                    .slice(0, sectionIndex)
                    .reduce((acc, curr) => acc + curr.items.length, 0) + itemIndex;
                  return (
                    // 4. Apply item variants to each grid item
                    <motion.div
                      key={itemIndex}
                      variants={gridItemVariants}
                      className="bg-card p-6 rounded-lg shadow-sm hover:shadow-md transition-shadow border border-border"
                    >
                      <div className="flex gap-5">
                        <div className="flex-shrink-0 cursor-pointer" onClick={() => openLightbox(globalIndex)}>
                          <img
                            src={item.src}
                            alt={item.name}
                            className="w-20 h-20 rounded-lg object-cover shadow-sm hover:opacity-90 transition-opacity"
                          />
                        </div>

                        <div className="flex-grow">
                          <div className="flex justify-between items-start">
                            <div>
                              <h3 className="text-xl font-semibold text-golden-brown">{item.name}</h3>
                              <p className="text-muted-foreground mt-1">{item.description}</p>
                            </div>
                            <span className="text-lg font-semibold text-golden-brown whitespace-nowrap ml-4">{item.price}</span>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </motion.div>
            </div>
          ))}

          <div className="mt-16 text-center">
            <h2 className="text-3xl font-bold text-deep-blue mb-4">Ready to Experience Our Cuisine?</h2>
            <p className="text-lg text-muted-foreground mb-8 max-w-2xl mx-auto">
              Make a reservation today and let our international culinary team craft a transformative dining experience that blends global traditions for you.
            </p>
            <a
              href="/reservations"
              className="btn"
            >
              Make a Reservation
            </a>
          </div>

        </div>
      </section>

      <Lightbox
        images={menuImages}
        currentIndex={currentImageIndex}
        isOpen={lightboxOpen}
        onClose={closeLightbox}
        onNext={nextImage}
        onPrev={prevImage}
      />
    </div>
  );
}

export default Menu;