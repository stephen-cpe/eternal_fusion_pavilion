// frontend/src/pages/Admin.jsx
"use client"

import { useState, useEffect } from "react"
import { toast } from "react-toastify"
import { adminService, reservationService } from "../services/api"
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query"
import AddReservationModal from "../components/AddReservationModal"
import EditReservationModal from "../components/EditReservationModal"

function AdminReservations() {
  const [selectedLocation, setSelectedLocation] = useState("")
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split("T")[0])
  const [locations, setLocations] = useState([])
  const [searchQuery, setSearchQuery] = useState("")
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)

  const [editModalOpen, setEditModalOpen] = useState(false)
  const [roomModalOpen, setRoomModalOpen] = useState(false)
  const [selectedReservation, setSelectedReservation] = useState(null)

  const queryClient = useQueryClient()

  useEffect(() => {
    const fetchLocations = async () => {
      try {
        const data = await reservationService.getLocations()
        setLocations(data.locations)
        if (data.locations.length > 0) {
          setSelectedLocation(data.locations[0].id.toString())
        }
      } catch (error) {
        console.error("Error fetching locations:", error)
        toast.error("Failed to load locations")
      }
    }
    fetchLocations()
  }, [])

  const reservationsQuery = useQuery({
    queryKey: ["reservations", selectedLocation, selectedDate, searchQuery],
    queryFn: () =>
      adminService.getReservations({
        location_id: selectedLocation,
        date: selectedDate,
        search: searchQuery,
      }),
    enabled: !!selectedLocation,
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, status }) => adminService.updateReservation(id, status),
    onSuccess: () => {
      toast.success("Reservation updated successfully")
      queryClient.invalidateQueries(["reservations"])
      queryClient.invalidateQueries(["dashboard"])
    },
    onError: (error) => {
      toast.error(error.message || "Failed to update reservation")
    },
  })

  const deleteMutation = useMutation({
    mutationFn: adminService.deleteReservation,
    onSuccess: () => {
      toast.success("Reservation deleted successfully")
      queryClient.invalidateQueries(["reservations"])
      queryClient.invalidateQueries(["dashboard"])
    },
    onError: (error) => {
      toast.error(error.message || "Failed to delete reservation")
    },
  })

  const handleUpdateReservation = (id, status) => {
    updateMutation.mutate({ id, status })
  }

  const handleDeleteReservation = (id) => {
    if (window.confirm("Are you sure you want to delete this reservation?")) {
      return
    }
    deleteMutation.mutate(id)
  }

  const handleOpenEditModal = (reservation) => {
    setSelectedReservation(reservation)
    setEditModalOpen(true)
  }

  const handleOpenRoomModal = (reservation) => {
    setSelectedReservation(reservation)
    setRoomModalOpen(true)
  }

  const handleCloseModals = () => {
    setSelectedReservation(null)
    setEditModalOpen(false)
    setRoomModalOpen(false)
  }

  const reservations = reservationsQuery.data || []

  return (
    <>
      <div className="container mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold">Reservation Management</h1>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors"
          >
            Add Reservation
          </button>
        </div>

        <div className="bg-card p-6 rounded-xl shadow-md mb-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Location</label>
              <select
                value={selectedLocation}
                onChange={(e) => setSelectedLocation(e.target.value)}
                className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
              >
                {locations.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Date</label>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div className="md:col-span-1">
              <label className="block text-sm font-medium mb-2">Search</label>
              <div className="flex">
                <input
                  type="text"
                  placeholder="Name, Email, Res #"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full px-4 py-2 border border-input rounded-l-md focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <button
                  onClick={() => setSearchQuery("")}
                  className="px-4 py-2 border border-l-0 border-input rounded-r-md hover:bg-muted transition-colors"
                >
                  Clear
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Reservations Table */}
        <div className="bg-card rounded-xl shadow-md overflow-hidden">
          {reservationsQuery.isLoading ? (
            <div className="text-center py-8">Loading reservations...</div>
          ) : reservationsQuery.isError ? (
            <div className="text-center py-8 text-red-600">Failed to load reservations</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border">
                <thead className="bg-muted">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Reservation #
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Date
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Time
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Guests
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Room
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Customer
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-card divide-y divide-border">
                  {reservations.length > 0 ? (
                    reservations.map((reservation) => (
                      <tr key={reservation.id}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-foreground">
                          {reservation.reservation_number}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">{reservation.date}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">{reservation.time}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">{reservation.party_size}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                          {reservation.room ? (
                            <div>
                              <div className="font-medium">{reservation.room.name}</div>
                              <div className="text-xs text-muted-foreground">{reservation.room.code}</div>
                            </div>
                          ) : (
                            <span className="text-muted-foreground">Not assigned</span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                          <div>{reservation.customer.name}</div>
                          <div className="text-muted-foreground text-xs">{reservation.customer.email}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
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
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-y-2 flex flex-col items-start">

                          <button
                            onClick={() => handleOpenEditModal(reservation)}
                            className="text-blue-600 hover:text-blue-900"
                          >
                            Edit
                          </button>

                          <button
                            onClick={() => handleOpenRoomModal(reservation)}
                            className="text-indigo-600 hover:text-indigo-900"
                          >
                            Change Room
                          </button>

                          <select
                            value={reservation.status}
                            onChange={(e) => handleUpdateReservation(reservation.id, e.target.value)}
                            className="border border-input rounded-md px-2 py-1 text-sm"
                            disabled={updateMutation.isPending}
                          >
                            <option value="confirmed">Confirmed</option>
                            <option value="cancelled">Cancelled</option>
                            <option value="no-show">No Show</option>
                            <option value="completed">Completed</option>
                          </select>
                          <button
                            onClick={() => handleDeleteReservation(reservation.id)}
                            className="text-red-600 hover:text-red-900"
                            disabled={deleteMutation.isPending}
                          >
                            Delete
                          </button>

                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="8" className="text-center py-8 text-muted-foreground">
                        No reservations found
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <AddReservationModal isOpen={isAddModalOpen} onClose={() => setIsAddModalOpen(false)} />

      <EditReservationModal
        isOpen={editModalOpen}
        onClose={handleCloseModals}
        reservation={selectedReservation}
        mode="edit"
      />
      <EditReservationModal
        isOpen={roomModalOpen}
        onClose={handleCloseModals}
        reservation={selectedReservation}
        mode="room"
      />

    </>
  )
}

export default AdminReservations
