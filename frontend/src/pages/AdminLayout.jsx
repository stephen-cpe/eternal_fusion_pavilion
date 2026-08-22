// frontend/src/pages/AdminLayout.jsx
import React from 'react';
import { Outlet } from 'react-router-dom';
import AdminNavigation from '../components/AdminNavigation';
import { useQuery } from '@tanstack/react-query';
import { adminService } from '../services/api';

function AdminLayout() {

  const customersQuery = useQuery({
    queryKey: ['customers'],
    queryFn: adminService.getCustomers,
    refetchOnWindowFocus: false,
  });

  const subscribersQuery = useQuery({
    queryKey: ['subscribers'],
    queryFn: adminService.getSubscribers,
    refetchOnWindowFocus: false,
  });

  return (
    <div className="min-h-screen flex flex-col bg-muted">
      <AdminNavigation />
      <main className="flex-grow">
        <Outlet context={{ customersQuery, subscribersQuery }} />
      </main>
    </div>
  );
}

export default AdminLayout;
