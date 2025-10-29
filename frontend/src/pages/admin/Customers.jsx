"use client"

import { useState } from "react"
import { useOutletContext } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { adminService } from "../../services/api"
import EditCustomerModal from "../../components/EditCustomerModal"

const SkeletonRow = () => (
  <tr>
    <td className="px-6 py-4">
      <div className="h-4 bg-gray-200 rounded w-12 animate-pulse"></div>
    </td>
    <td className="px-6 py-4">
      <div className="h-4 bg-gray-200 rounded w-32 animate-pulse"></div>
    </td>
    <td className="px-6 py-4">
      <div className="h-4 bg-gray-200 rounded w-48 animate-pulse"></div>
    </td>
    <td className="px-6 py-4">
      <div className="h-4 bg-gray-200 rounded w-24 animate-pulse"></div>
    </td>
    <td className="px-6 py-4">
      <div className="h-4 bg-gray-200 rounded w-28 animate-pulse"></div>
    </td>
    <td className="px-6 py-4">
      <div className="h-4 bg-gray-200 rounded w-16 animate-pulse"></div>
    </td>
  </tr>
)

const LoadError = ({ onRetry }) => (
  <div className="text-center py-10 px-6 bg-red-50 border border-red-200 rounded-lg">
    <h3 className="text-lg font-semibold text-red-700">Failed to load customer data.</h3>
    <p className="text-red-600 mb-4">An error occurred while fetching data.</p>
    <button onClick={onRetry} className="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700 transition-colors">
      Retry?
    </button>
  </div>
)

function Customers() {
  const { customersQuery } = useOutletContext()
  const { data: customers, isLoading, isError, refetch } = customersQuery

  const [searchQuery, setSearchQuery] = useState("")
  const [selectedCustomer, setSelectedCustomer] = useState(null)

  const [isViewModalOpen, setIsViewModalOpen] = useState(false)
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)

  // Query for customer's reservation history
  const customerReservationsQuery = useQuery({
    queryKey: ["customerReservations", selectedCustomer?.email],
    queryFn: () => adminService.getReservations({ search: selectedCustomer?.email }),
    enabled: !!selectedCustomer,
  })

  const filteredCustomers = customers?.filter(
    (customer) =>
      customer.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      customer.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      customer.phone?.toLowerCase().includes(searchQuery.toLowerCase()),
  )

  const handleViewDetails = (customer) => {
    setSelectedCustomer(customer)
    setIsViewModalOpen(true)
  }

  const handleCloseDetails = () => {
    setSelectedCustomer(null)
    setIsViewModalOpen(false)
  }

  const handleCloseEditModal = () => {
    setSelectedCustomer(null)
    setIsEditModalOpen(false)
  }

  const handleOpenEditModal = (customer) => {
    setSelectedCustomer(customer)
    setIsEditModalOpen(true)
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">Customer Management</h1>

      {/* Search Bar */}
      <div className="bg-card p-6 rounded-xl shadow-md mb-8">
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search by name, email, or phone..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <button
            onClick={() => setSearchQuery("")}
            className="px-4 py-2 border border-input rounded-md hover:bg-muted transition-colors"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Customer Stats */}
      {!isLoading && !isError && customers && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <div className="bg-card p-4 rounded-lg border border-border">
            <div className="text-sm text-muted-foreground">Total Customers</div>
            <div className="text-2xl font-bold">{customers.length}</div>
          </div>
          <div className="bg-card p-4 rounded-lg border border-border">
            <div className="text-sm text-muted-foreground">Newsletter Subscribers</div>
            <div className="text-2xl font-bold">{customers.filter((c) => c.newsletter_signup).length}</div>
          </div>
          <div className="bg-card p-4 rounded-lg border border-border">
            <div className="text-sm text-muted-foreground">New This Month</div>
            <div className="text-2xl font-bold">
              {
                customers.filter((c) => {
                  const createdDate = new Date(c.created_at)
                  const now = new Date()
                  return createdDate.getMonth() === now.getMonth() && createdDate.getFullYear() === now.getFullYear()
                }).length
              }
            </div>
          </div>
        </div>
      )}

      {/* Customers Table */}
      <div className="bg-card rounded-xl shadow-md overflow-hidden mb-12">
        <h2 className="text-xl font-semibold p-6 border-b border-border">Registered Customers</h2>
        {isError ? (
          <LoadError onRetry={() => refetch()} />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-muted">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Name</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Email</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Phone</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">
                    Newsletter
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Signed Up</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-card divide-y divide-border">
                {isLoading ? (
                  Array(5)
                    .fill(0)
                    .map((_, i) => <SkeletonRow key={i} />)
                ) : filteredCustomers && filteredCustomers.length > 0 ? (
                  filteredCustomers.map((customer) => (
                    <tr key={customer.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">{customer.id}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-foreground">
                        {customer.name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">{customer.email}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">{customer.phone || "N/A"}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        {customer.newsletter_signup ? (
                          <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                            Yes
                          </span>
                        ) : (
                          <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">
                            No
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                        {new Date(customer.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <button
                          onClick={() => handleViewDetails(customer)}
                          className="text-primary hover:text-primary/80"
                        >
                          View Details
                        </button>
                        <button
                          onClick={() => handleOpenEditModal(customer)}
                          className="text-blue-600 hover:text-blue-900 ml-4"
                        >
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="7" className="px-6 py-8 text-center text-muted-foreground">
                      {searchQuery ? "No customers match your search" : "No customers found"}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Customer Details Modal */}
      {selectedCustomer && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-card rounded-xl shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-border flex justify-between items-center">
              <h2 className="text-2xl font-bold">Customer Details</h2>
              <button onClick={handleCloseDetails} className="text-muted-foreground hover:text-foreground text-2xl">
                ×
              </button>
            </div>

            <div className="p-6">
              {/* Customer Info */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Name</label>
                  <p className="text-lg font-semibold">{selectedCustomer.name}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Email</label>
                  <p className="text-lg">{selectedCustomer.email}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Phone</label>
                  <p className="text-lg">{selectedCustomer.phone || "N/A"}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Newsletter</label>
                  <p className="text-lg">{selectedCustomer.newsletter_signup ? "Subscribed" : "Not subscribed"}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Customer Since</label>
                  <p className="text-lg">{new Date(selectedCustomer.created_at).toLocaleDateString()}</p>
                </div>
              </div>

              {/* Reservation History */}
              <div className="mt-8">
                <h3 className="text-xl font-semibold mb-4">Reservation History</h3>
                {customerReservationsQuery.isLoading ? (
                  <div className="text-center py-4">Loading reservations...</div>
                ) : customerReservationsQuery.isError ? (
                  <div className="text-center py-4 text-red-600">Failed to load reservations</div>
                ) : customerReservationsQuery.data && customerReservationsQuery.data.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-border">
                      <thead className="bg-muted">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase">
                            Reservation #
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase">
                            Date
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase">
                            Time
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase">
                            Guests
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase">
                            Location
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase">
                            Status
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-card divide-y divide-border">
                        {customerReservationsQuery.data.map((reservation) => (
                          <tr key={reservation.id}>
                            <td className="px-4 py-2 text-sm font-medium">{reservation.reservation_number}</td>
                            <td className="px-4 py-2 text-sm">{reservation.date}</td>
                            <td className="px-4 py-2 text-sm">{reservation.time}</td>
                            <td className="px-4 py-2 text-sm">{reservation.party_size}</td>
                            <td className="px-4 py-2 text-sm">{reservation.location.name}</td>
                            <td className="px-4 py-2 text-sm">
                              <span
                                className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                                  reservation.status === "confirmed"
                                    ? "bg-green-100 text-green-800"
                                    : reservation.status === "cancelled"
                                      ? "bg-red-100 text-red-800"
                                      : "bg-yellow-100 text-yellow-800"
                                }`}
                              >
                                {reservation.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-center py-4 text-muted-foreground">No reservations found for this customer</p>
                )}
              </div>
            </div>

            <div className="p-6 border-t border-border flex justify-end">
              <button
                onClick={handleCloseDetails}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      <EditCustomerModal
        isOpen={isEditModalOpen}
        onClose={handleCloseEditModal}
        customer={selectedCustomer}
      />

    </div>
  )
}

export default Customers
