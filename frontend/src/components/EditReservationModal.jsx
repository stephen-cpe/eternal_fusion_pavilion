// frontend/src/components/EditReservationModal.jsx
"use client"

import { useState, useEffect } from "react"
import { adminService, reservationService } from "../services/api"
import { toast } from "react-toastify"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"

function EditReservationModal({ isOpen, onClose, reservation, mode = "edit" }) {
  const [formData, setFormData] = useState({})
  const [timeSlots, setTimeSlots] = useState([])
  const [rooms, setRooms] = useState([])
  const queryClient = useQueryClient()

  // Pre-populate form when reservation or mode changes
  useEffect(() => {
    if (reservation) {
      setFormData({
        location_id: reservation.location_id || "",
        date: reservation.date || "",
        time: reservation.time || "",
        party_size: reservation.party_size || "",
        customer_name: reservation.customer?.name || "",
        customer_email: reservation.customer?.email || "",
        customer_phone: reservation.customer?.phone || "",
        special_requests: reservation.special_requests || "",
        status: reservation.status || "confirmed",
        room_id: reservation.room?.id || "",
      })
    }
  }, [reservation, isOpen]) // Re-populate when modal opens

  // Fetch locations
  const { data: locations, isLoading: locationsLoading } = useQuery({
    queryKey: ["locations"],
    queryFn: reservationService.getLocations,
  })

  // Fetch rooms when location changes
  const { data: roomData, isLoading: roomsLoading } = useQuery({
    queryKey: ["rooms", formData.location_id],
    queryFn: () => adminService.getRooms(formData.location_id),
    enabled: !!formData.location_id,
  })

  useEffect(() => {
    if (roomData) {
      setRooms(roomData)
    } else {
      setRooms([])
    }
    // Don't reset room_id if it's already set from the reservation
  }, [roomData])

  // Generate time slots when date changes
  useEffect(() => {
    if (formData.date) {
      const date = new Date(formData.date + "T00:00:00")
      const dayOfWeek = date.getUTCDay()
      const isSundayOrMonday = dayOfWeek === 0 || dayOfWeek === 1

      const startMinutes = 17 * 60 // 5:00 PM
      const endMinutes = isSundayOrMonday ? 21 * 60 : 23 * 60 // 9:00 PM or 11:00 PM

      const slots = []
      for (let minutes = startMinutes; minutes < endMinutes; minutes += 30) {
        const hour = Math.floor(minutes / 60)
        const minute = minutes % 60
        const timeValue = `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`
        slots.push(timeValue)
      }
      setTimeSlots(slots)
    } else {
      setTimeSlots([])
    }
  }, [formData.date])

  // Mutation for updating full details
  const updateDetailsMutation = useMutation({
    mutationFn: (data) => adminService.updateReservationDetails(reservation.id, data),
    onSuccess: () => {
      toast.success("Reservation updated successfully!")
      queryClient.invalidateQueries(["reservations"])
      queryClient.invalidateQueries(["dashboard"])
      onClose()
    },
    onError: (error) => {
      toast.error(error.message || "Failed to update reservation")
    },
  })

  // Mutation for updating room only
  const updateRoomMutation = useMutation({
    mutationFn: (data) => adminService.updateReservationRoom(reservation.id, data.room_id),
    onSuccess: () => {
      toast.success("Room assignment updated!")
      queryClient.invalidateQueries(["reservations"])
      queryClient.invalidateQueries(["dashboard"])
      queryClient.invalidateQueries(["auditLog"]) // Invalidate audit log
      onClose()
    },
    onError: (error) => {
      toast.error(error.message || "Failed to update room")
    },
  })

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const submissionData = {
      ...formData,
      party_size: Number(formData.party_size),
    }

    if (mode === "edit") {
      updateDetailsMutation.mutate(submissionData)
    } else if (mode === "room") {
      if (!formData.room_id) {
        toast.error("Please select a new room.")
        return
      }
      updateRoomMutation.mutate({ room_id: formData.room_id })
    }
  }

  if (!isOpen || !reservation) return null

  const isLoading = updateDetailsMutation.isPending || updateRoomMutation.isPending

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-60 p-4">
      <div className="bg-card rounded-xl shadow-lg w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <div className="p-6 border-b border-border">
            <h2 className="text-2xl font-bold">
              {mode === "edit" ? "Edit Reservation" : "Change Room Assignment"}
            </h2>
            <p className="text-sm text-muted-foreground">
              {mode === "edit"
                ? `Editing: ${reservation.reservation_number}`
                : `Reservation: ${reservation.reservation_number}`}
            </p>
          </div>

          <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Room (Always visible, but only field in 'room' mode) */}
            <div>
              <label className="block text-sm font-medium mb-2">Room*</label>
              <select
                name="room_id"
                value={formData.room_id || ""}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                disabled={!formData.location_id || roomsLoading}
              >
                <option value="">{roomsLoading ? "Loading rooms..." : "Select a room"}</option>
                {rooms.map((room) => (
                  <option key={room.id} value={room.id}>
                    {room.name} ({room.code})
                  </option>
                ))}
              </select>
              {mode === "edit" && (
                <p className="text-xs text-muted-foreground mt-1">
                  You can manually override the room assignment here.
                </p>
              )}
            </div>

            {/* --- All other fields are hidden if mode === 'room' --- */}
            {mode === "edit" && (
              <>
                {/* Location */}
                <div>
                  <label className="block text-sm font-medium mb-2">Location*</label>
                  <select
                    name="location_id"
                    value={formData.location_id}
                    onChange={handleChange}
                    className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                    required
                    disabled={locationsLoading}
                  >
                    <option value="">{locationsLoading ? "Loading..." : "Select a location"}</option>
                    {locations?.locations.map((location) => (
                      <option key={location.id} value={location.id}>
                        {location.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Date */}
                <div>
                  <label className="block text-sm font-medium mb-2">Date*</label>
                  <input
                    type="date"
                    name="date"
                    value={formData.date}
                    onChange={handleChange}
                    className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                    required
                    min={new Date().toISOString().split("T")[0]}
                    disabled={!formData.location_id}
                  />
                </div>

                {/* Time */}
                <div>
                  <label className="block text-sm font-medium mb-2">Time*</label>
                  <select
                    name="time"
                    value={formData.time}
                    onChange={handleChange}
                    className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                    required
                    disabled={!formData.date}
                  >
                    <option value="">{formData.date ? "Select a time" : "Select date first"}</option>
                    {timeSlots.map((slot, index) => (
                      <option key={index} value={slot}>
                        {slot}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Party Size */}
                <div>
                  <label className="block text-sm font-medium mb-2">Party Size*</label>
                  <input
                    type="number"
                    min="1"
                    max="30"
                    name="party_size"
                    value={formData.party_size}
                    onChange={handleChange}
                    placeholder="Number of guests (1-30)"
                    className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                    required
                  />
                  <p className="text-xs text-muted-foreground mt-1">Admin can book up to 30 guests.</p>
                </div>

                {/* Status */}
                <div>
                  <label className="block text-sm font-medium mb-2">Status*</label>
                  <select
                    name="status"
                    value={formData.status}
                    onChange={handleChange}
                    className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                    required
                  >
                    <option value="confirmed">Confirmed</option>
                    <option value="cancelled">Cancelled</option>
                    <option value="no-show">No Show</option>
                    <option value="completed">Completed</option>
                  </select>
                </div>

                {/* Customer Name */}
                <div>
                  <label className="block text-sm font-medium mb-2">Customer Name*</label>
                  <input
                    type="text"
                    name="customer_name"
                    value={formData.customer_name}
                    onChange={handleChange}
                    placeholder="Enter customer's full name"
                    className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                    required
                  />
                </div>

                {/* Customer Email */}
                <div>
                  <label className="block text-sm font-medium mb-2">Customer Email*</label>
                  <input
                    type="email"
                    name="customer_email"
                    value={formData.customer_email}
                    onChange={handleChange}
                    placeholder="customer@example.com"
                    className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                    required
                  />
                </div>

                {/* Customer Phone */}
                <div className="md:col-span-1">
                  <label className="block text-sm font-medium mb-2">Customer Phone (Optional)</label>
                  <input
                    type="tel"
                    name="customer_phone"
                    value={formData.customer_phone}
                    onChange={handleChange}
                    placeholder="(202) 555-4567"
                    className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>

                {/* Special Requests */}
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium mb-2">Special Requests (Optional)</label>
                  <textarea
                    name="special_requests"
                    value={formData.special_requests}
                    onChange={handleChange}
                    placeholder="Dietary restrictions, special occasions, etc."
                    rows="3"
                    className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </>
            )}
          </div>

          <div className="p-6 border-t border-border flex justify-end space-x-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-input rounded-md hover:bg-muted transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {isLoading ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default EditReservationModal
