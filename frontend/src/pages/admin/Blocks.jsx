"use client"

import { useState, useEffect } from "react"
import { toast } from "react-toastify"
import { adminService, reservationService } from "../../services/api"
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query"

function Blocks() {
  const [locations, setLocations] = useState([])
  const [selectedLocation, setSelectedLocation] = useState("")
  const [showAddForm, setShowAddForm] = useState(false)
  const [newBlock, setNewBlock] = useState({
    location_id: "",
    room_id: "",
    start_date: "",
    end_date: "",
    start_time: "",
    end_time: "",
    block_type: "hard",
    reason: "",
  })
  const [rooms, setRooms] = useState([])

  const queryClient = useQueryClient()

  useEffect(() => {
    const fetchLocations = async () => {
      try {
        const data = await reservationService.getLocations()
        setLocations(data.locations)
        if (data.locations.length > 0) {
          setSelectedLocation(data.locations[0].id.toString())
          setNewBlock((prev) => ({ ...prev, location_id: data.locations[0].id.toString() }))
        }
      } catch (error) {
        console.error("Error fetching locations:", error)
        toast.error("Failed to load locations")
      }
    }
    fetchLocations()
  }, [])

  useEffect(() => {
    if (newBlock.location_id) {
      const fetchRooms = async () => {
        try {
          const data = await adminService.getRooms(newBlock.location_id)
          setRooms(data)
        } catch (error) {
          console.error("Error fetching rooms:", error)
        }
      }
      fetchRooms()
    }
  }, [newBlock.location_id])

  const blocksQuery = useQuery({
    queryKey: ["blocks", selectedLocation],
    queryFn: () => adminService.getBlocks(selectedLocation),
    enabled: !!selectedLocation,
  })

  const createMutation = useMutation({
    mutationFn: adminService.createBlock,
    onSuccess: () => {
      toast.success("Block created successfully")
      queryClient.invalidateQueries(["blocks"])
      setShowAddForm(false)
      setNewBlock({
        location_id: selectedLocation,
        room_id: "",
        start_date: "",
        end_date: "",
        start_time: "",
        end_time: "",
        block_type: "hard",
        reason: "",
      })
    },
    onError: (error) => {
      toast.error(error.message || "Failed to create block")
    },
  })

  const deleteMutation = useMutation({
    mutationFn: adminService.deleteBlock,
    onSuccess: () => {
      toast.success("Block deleted successfully")
      queryClient.invalidateQueries(["blocks"])
    },
    onError: (error) => {
      toast.error(error.message || "Failed to delete block")
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    createMutation.mutate(newBlock)
  }

  const handleDelete = (blockId) => {
    if (window.confirm("Are you sure you want to delete this block?")) {
      deleteMutation.mutate(blockId)
    }
  }

  const blocks = blocksQuery.data || []

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Reservation Blocks</h1>
        <button
          onClick={() => setShowAddForm(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors"
        >
          Create Block
        </button>
      </div>

      <div className="bg-card p-6 rounded-xl shadow-md mb-8">
        <label className="block text-sm font-medium mb-2">Filter by Location</label>
        <select
          value={selectedLocation}
          onChange={(e) => setSelectedLocation(e.target.value)}
          className="w-full md:w-64 px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
        >
          {locations.map((loc) => (
            <option key={loc.id} value={loc.id}>
              {loc.name}
            </option>
          ))}
        </select>
      </div>

      {showAddForm && (
        <div className="bg-card p-6 rounded-xl shadow-md mb-8">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">Create New Block</h2>
            <button onClick={() => setShowAddForm(false)} className="text-muted-foreground hover:text-foreground">
              ✕
            </button>
          </div>
          <form onSubmit={handleSubmit}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Location*</label>
                <select
                  value={newBlock.location_id}
                  onChange={(e) => setNewBlock({ ...newBlock, location_id: e.target.value })}
                  className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  required
                >
                  {locations.map((loc) => (
                    <option key={loc.id} value={loc.id}>
                      {loc.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">
                  Room (Optional - leave empty for location-wide)
                </label>
                <select
                  value={newBlock.room_id}
                  onChange={(e) => setNewBlock({ ...newBlock, room_id: e.target.value })}
                  className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="">Location-wide block</option>
                  {rooms.map((room) => (
                    <option key={room.id} value={room.id}>
                      {room.name} ({room.code})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Start Date*</label>
                <input
                  type="date"
                  value={newBlock.start_date}
                  onChange={(e) => setNewBlock({ ...newBlock, start_date: e.target.value })}
                  className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">End Date*</label>
                <input
                  type="date"
                  value={newBlock.end_date}
                  onChange={(e) => setNewBlock({ ...newBlock, end_date: e.target.value })}
                  className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Start Time*</label>
                <input
                  type="time"
                  value={newBlock.start_time}
                  onChange={(e) => setNewBlock({ ...newBlock, start_time: e.target.value })}
                  className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">End Time*</label>
                <input
                  type="time"
                  value={newBlock.end_time}
                  onChange={(e) => setNewBlock({ ...newBlock, end_time: e.target.value })}
                  className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Block Type*</label>
                <select
                  value={newBlock.block_type}
                  onChange={(e) => setNewBlock({ ...newBlock, block_type: e.target.value })}
                  className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  required
                >
                  <option value="hard">Hard (No overrides)</option>
                  <option value="soft">Soft (Manager can override)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Reason</label>
                <input
                  type="text"
                  value={newBlock.reason}
                  onChange={(e) => setNewBlock({ ...newBlock, reason: e.target.value })}
                  placeholder="e.g., Private event, Maintenance"
                  className="w-full px-3 py-2 border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            </div>
            <div className="mt-6 flex justify-end space-x-4">
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-4 py-2 border border-input rounded-md hover:bg-muted transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {createMutation.isPending ? "Creating..." : "Create Block"}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-card rounded-xl shadow-md overflow-hidden">
        {blocksQuery.isLoading ? (
          <div className="text-center py-8">Loading blocks...</div>
        ) : blocksQuery.isError ? (
          <div className="text-center py-8 text-red-600">Failed to load blocks</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-muted">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Location
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Room
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Date Range
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Time Range
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Reason
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-card divide-y divide-border">
                {blocks.length > 0 ? (
                  blocks.map((block) => (
                    <tr key={block.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">{block.location_name}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                        {block.room_name || <span className="text-muted-foreground italic">Location-wide</span>}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                        {block.start_date} to {block.end_date}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                        {block.start_time} - {block.end_time}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                            block.block_type === "hard" ? "bg-red-100 text-red-800" : "bg-yellow-100 text-yellow-800"
                          }`}
                        >
                          {block.block_type}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-foreground">{block.reason || "-"}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <button
                          onClick={() => handleDelete(block.id)}
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
                    <td colSpan="7" className="text-center py-8 text-muted-foreground">
                      No blocks found
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

export default Blocks
