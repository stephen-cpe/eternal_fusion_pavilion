// frontend/src/pages/admin/PlaceholderPage.jsx
import React from 'react';

function PlaceholderPage({ title, message }) {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="bg-white p-12 rounded-xl shadow-md text-center">
        <h1 className="text-3xl font-bold mb-4">{title}</h1>
        <p className="text-lg text-gray-600">{message}</p>
      </div>
    </div>
  );
}

export default PlaceholderPage;