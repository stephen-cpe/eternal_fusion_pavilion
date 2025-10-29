// frontend/src/pages/admin/AuditLog.jsx
"use client"

import { useQuery } from "@tanstack/react-query"
import { adminService } from "../../services/api"

// Skeleton row component
const SkeletonRow = () => (
  <tr>
    <td className="px-6 py-4">
      <div className="h-4 bg-gray-200 rounded w-28 animate-pulse"></div>
    </td>
    <td className="px-6 py-4">
      <div className="h-4 bg-gray-200 rounded w-32 animate-pulse"></div>
    </td>
    <td className="px-6 py-4">
      <div className="h-4 bg-gray-200 rounded w-24 animate-pulse"></div>
    </td>
    <td className="px-6 py-4">
      <div className="h-4 bg-gray-200 rounded w-20 animate-pulse"></div>
    </td>
    <td className="px-6 py-4">
      <div className="h-4 bg-gray-200 rounded w-48 animate-pulse"></div>
    </td>
  </tr>
)

// Error and refetch component
const LoadError = ({ onRetry }) => (
  <div className="text-center py-10 px-6 bg-red-50 border border-red-200 rounded-lg">
    <h3 className="text-lg font-semibold text-red-700">Failed to load audit log.</h3>
    <p className="text-red-600 mb-4">An error occurred while fetching data.</p>
    <button onClick={onRetry} className="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700 transition-colors">
      Retry?
    </button>
  </div>
)

function AuditLog() {
  const {
    data: logs,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["auditLog"],
    queryFn: () => adminService.getAuditLog(100), // Fetch last 100 events
  })

  // Helper to format the details JSON
  const formatDetails = (details) => {
    if (!details || Object.keys(details).length === 0) {
      return <span className="text-muted-foreground italic">No details</span>
    }
    // Special formatting for soft block overrides
    if (details.action === "manual_room_override" && details.soft_block_override) {
      return (
        <span className="font-medium text-amber-700">
          Soft block overridden. Moved from room {details.old_room_id} to {details.new_room_id}.
        </span>
      )
    }
    // Default JSON formatting
    return <pre className="text-xs bg-muted p-2 rounded">{JSON.stringify(details, null, 2)}</pre>
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">Admin Audit Log</h1>

      <div className="bg-card rounded-xl shadow-md overflow-hidden">
        <h2 className="text-xl font-semibold p-6 border-b border-border">Recent Admin Actions</h2>
        {isError ? (
          <LoadError onRetry={() => refetch()} />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-muted">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Timestamp</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Admin</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Action</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Entity</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Details</th>
                </tr>
              </thead>
              <tbody className="bg-card divide-y divide-border">
                {isLoading ? (
                  Array(10)
                    .fill(0)
                    .map((_, i) => <SkeletonRow key={i} />)
                ) : logs && logs.length > 0 ? (
                  logs.map((log) => (
                    <tr key={log.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-foreground">
                        {log.admin_name || "N/A"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">{log.action}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                        {log.entity_type} (ID: {log.entity_id})
                      </td>
                      <td className="px-6 py-4 text-sm text-foreground">{formatDetails(log.details)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="5" className="px-6 py-8 text-center text-muted-foreground">
                      No audit logs found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default AuditLog
