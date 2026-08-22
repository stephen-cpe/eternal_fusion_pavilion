// frontend/src/components/ChangeNameModal.jsx
import React, { useState, useEffect } from 'react';
import { adminService } from '../services/api';
import { toast } from 'react-toastify';

function ChangeNameModal({ isOpen, onClose, currentName, onSuccess }) {
  const [fullName, setFullName] = useState(currentName);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setFullName(currentName);
  }, [currentName]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await adminService.updateName(fullName);
      toast.success('Name updated successfully!');
      onSuccess(); // Re-fetch profile data in parent
      onClose();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-card rounded-lg shadow-lg p-6 w-full max-w-md">
        <h2 className="text-xl font-bold mb-4">Change Your Name</h2>
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label htmlFor="fullName" className="block text-sm font-medium text-foreground">Full Name</label>
            <input
              type="text"
              id="fullName"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-input rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
              required
            />
          </div>
          <div className="flex justify-end space-x-4">
            <button type="button" onClick={onClose} className="px-4 py-2 bg-muted rounded-md hover:opacity-90 transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={isLoading} className="px-4 py-2 bg-deep-blue text-white rounded-md hover:bg-darker-blue disabled:opacity-50 transition-colors">
              {isLoading ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default ChangeNameModal;