// frontend/src/pages/admin/Newsletter.jsx
import React from 'react';
import { useOutletContext } from 'react-router-dom';

// Skeleton row component
const SkeletonRow = () => (
  <tr>
    <td className="px-6 py-4"><div className="h-4 bg-gray-200 rounded w-12 animate-pulse"></div></td>
    <td className="px-6 py-4"><div className="h-4 bg-gray-200 rounded w-48 animate-pulse"></div></td>
    <td className="px-6 py-4"><div className="h-4 bg-gray-200 rounded w-32 animate-pulse"></div></td>
    <td className="px-6 py-4"><div className="h-4 bg-gray-200 rounded w-24 animate-pulse"></div></td>
    <td className="px-6 py-4"><div className="h-4 bg-gray-200 rounded w-28 animate-pulse"></div></td>
  </tr>
);

// Error and refetch component
const LoadError = ({ onRetry }) => (
  <div className="text-center py-10 px-6 bg-red-50 border border-red-200 rounded-lg">
    <h3 className="text-lg font-semibold text-red-700">Failed to load subscribers.</h3>
    <p className="text-red-600 mb-4">An error occurred while fetching data.</p>
    <button
      onClick={onRetry}
      className="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700 transition-colors"
    >
      Retry?
    </button>
  </div>
);

function Newsletter() {
  const { subscribersQuery } = useOutletContext();
  const { data: subscribers, isLoading, isError, refetch } = subscribersQuery;

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">Newsletter Management</h1>
      
      <div className="bg-white rounded-xl shadow-md overflow-hidden">
        <h2 className="text-xl font-semibold p-6 border-b">Newsletter Subscribers</h2>
        {isError ? (
          <LoadError onRetry={() => refetch()} />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Subscribed At</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {isLoading ? (
                  // Show 5 skeleton rows while loading
                  Array(5).fill(0).map((_, i) => <SkeletonRow key={i} />)
                ) : subscribers && subscribers.length > 0 ? (
                  subscribers.map(sub => (
                    <tr key={sub.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">{sub.id}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">{sub.email}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">{sub.name || 'N/A'}</td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${sub.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                          {sub.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">{new Date(sub.subscribed_at).toLocaleDateString()}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="5" className="px-6 py-8 text-center text-gray-500">
                      No subscribers found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default Newsletter;
