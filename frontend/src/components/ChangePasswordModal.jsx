// frontend/src/components/ChangePasswordModal.jsx
import React, { useState } from 'react';
import { adminService } from '../services/api';
import { toast } from 'react-toastify';

function ChangePasswordModal({ isOpen, onClose }) {
  const [passwords, setPasswords] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  });
  const [isLoading, setIsLoading] = useState(false);

  if (!isOpen) return null;

  const handleChange = (e) => {
    const { name, value } = e.target;
    setPasswords(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (passwords.newPassword !== passwords.confirmPassword) {
      toast.error("New passwords do not match.");
      return;
    }
    setIsLoading(true);
    try {
      await adminService.updatePassword(passwords);
      toast.success('Password updated successfully!');
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
        <h2 className="text-xl font-bold mb-4">Change Password</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground">Current Password</label>
            <input type="password" name="currentPassword" value={passwords.currentPassword} onChange={handleChange} className="mt-1 block w-full px-3 py-2 border border-input rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground">New Password</label>
            <input type="password" name="newPassword" value={passwords.newPassword} onChange={handleChange} className="mt-1 block w-full px-3 py-2 border border-input rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground">Confirm New Password</label>
            <input type="password" name="confirmPassword" value={passwords.confirmPassword} onChange={handleChange} className="mt-1 block w-full px-3 py-2 border border-input rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background" required />
          </div>
          <div className="flex justify-end space-x-4 pt-4">
            <button type="button" onClick={onClose} className="px-4 py-2 bg-muted rounded-md hover:opacity-90 transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={isLoading} className="px-4 py-2 bg-deep-blue text-white rounded-md hover:bg-darker-blue disabled:opacity-50 transition-colors">
              {isLoading ? 'Saving...' : 'Update Password'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default ChangePasswordModal;