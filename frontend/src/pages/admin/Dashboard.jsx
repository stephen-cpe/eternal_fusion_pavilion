// frontend/src/pages/admin/Dashboard.jsx
"use client"

import { useState, useEffect } from "react"
import { toast } from "react-toastify"
import { adminService, reservationService } from "../../services/api"
import { useQuery } from "@tanstack/react-query"

const RoomHeatmap = ({ roomData, timeSlots }) => {
  const getOccupancyColor = (percentage) => {
    if (percentage === 0) return "bg-gray-100"
    if (percentage < 50) return "bg-green-100 text-green-800"
    if (percentage < 80) return "bg-yellow-100 text-yellow-800"
    return "bg-red-100 text-red-800"
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse">
        <thead>
          <tr>
            <th className="border border-border px-4 py-2 bg-muted text-left text-sm font-medium">Room</th>
            {timeSlots.map((slot) => (
              <th key={slot} className="border border-border px-2 py-2 bg-muted text-center text-xs font-medium">
                {slot}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {roomData.map((room) => (
            <tr key={room.id}>
              <td className="border border-border px-4 py-2 text-sm font-medium">
                <div>{room.name}</div>
                <div className="text-xs text-muted-foreground">{room.code}</div>
              </td>
              {timeSlots.map((slot) => {
                const slotData = room.slots[slot] || { occupancy: 0, percentage: 0 }
                return (
                  <td
                    key={slot}
                    className={`border border-border px-2 py-2 text-center text-xs ${getOccupancyColor(
                      slotData.percentage,
                    )}`}
                  >
                    <div className="font-semibold">{slotData.occupancy}</div>
                    <div className="text-xs">{slotData.percentage}%</div>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const LocationStats = ({ stats, maxGuests, maxReservations }) => {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div className="bg-card p-4 rounded-lg border border-border">
        <div className="text-sm text-muted-foreground">Total Guests</div>
        <div className="text-2xl font-bold">{stats.total_guests}</div>
        <div className="text-xs text-muted-foreground">of {maxGuests} max</div>
      </div>
      <div className="bg-card p-4 rounded-lg border border-border">
        <div className="text-sm text-muted-foreground">Total Reservations</div>
        <div className="text-2xl font-bold">{stats.total_reservations}</div>
        <div className="text-xs text-muted-foreground">of {maxReservations} max</div>
      </div>
      <div className="bg-card p-4 rounded-lg border border-border">
        <div className="text-sm text-muted-foreground">Guest Capacity</div>
        <div className="text-2xl font-bold">{stats.guests_percentage}%</div>
        <div className="text-xs text-muted-foreground">utilized</div>
      </div>
      <div className="bg-card p-4 rounded-lg border border-border">
        <div className="text-sm text-muted-foreground">Reservation Capacity</div>
        <div className="text-2xl font-bold">{stats.reservations_percentage}%</div>
        <div className="text-xs text-muted-foreground">utilized</div>
      </div>
    </div>
  )
}

// Main Dashboard Component
function Dashboard() {
  const [selectedLocation, setSelectedLocation] = useState("")
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split("T")[0])
  const [locations, setLocations] = useState([])

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

  const dashboardQuery = useQuery({
    queryKey: ["dashboard", selectedLocation, selectedDate],
    queryFn: () => adminService.getDashboardStats(selectedLocation, selectedDate),
    enabled: !!selectedLocation && !!selectedDate,
  })

  const dashboardData = dashboardQuery.data

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">Reservation Dashboard</h1>

      <div className="bg-card p-6 rounded-xl shadow-md mb-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
        </div>
      </div>

      {dashboardQuery.isLoading ? (
        <div className="text-center py-8">Loading dashboard...</div>
      ) : dashboardQuery.isError ? (
        <div className="text-center py-8 text-red-600">Failed to load dashboard data</div>
      ) : dashboardData ? (
        <>
          {/* Location-wide stats for current view */}
          {dashboardData.location_stats && Object.keys(dashboardData.location_stats).length > 0 && (
            <div className="mb-8">
              <h2 className="text-xl font-semibold mb-4">Current Occupancy Overview</h2>
              <LocationStats
                stats={
                  dashboardData.location_stats[
                    Object.keys(dashboardData.location_stats).find((slot) => {
                      const now = new Date()
                      const currentTime = `${now.getHours().toString().padStart(2, "0")}:${now
                        .getMinutes()
                        .toString()
                        .padStart(2, "0")}`
                      return slot >= currentTime
                    }) || Object.keys(dashboardData.location_stats)[0]
                  ] || { total_guests: 0, total_reservations: 0, guests_percentage: 0, reservations_percentage: 0 }
                }
                maxGuests={dashboardData.location.max_guests_per_slot}
                maxReservations={dashboardData.location.max_reservations_per_slot}
              />
            </div>
          )}

          {/* Room Heatmap */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold mb-4">Room Occupancy Heatmap</h2>
            <div className="bg-card p-6 rounded-xl shadow-md">
              <RoomHeatmap roomData={dashboardData.room_heatmap} timeSlots={dashboardData.time_slots} />
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}

export default Dashboard