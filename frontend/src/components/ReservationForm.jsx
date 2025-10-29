"use client"

import { useState, useEffect } from "react"
import { reservationService } from "../services/api"
import { toast } from "react-toastify"

const SlotAvailabilityChecker = ({ locationId, date, time }) => {
  const [availability, setAvailability] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    const checkAvailability = async () => {
      if (!locationId || !date || !time) {
        setAvailability(null)
        return
      }

      setIsLoading(true)
      setAvailability(null)
      try {
        const data = await reservationService.getAvailability(locationId, date)
        const slot = data.slots.find((s) => s.time === time)
        if (slot) {
          setAvailability({
            available: slot.available,
            slotsLeft: slot.slotsLeft,
            guestsAvailable: slot.guestsAvailable,
          })
        } else {
          setAvailability({ available: false, slotsLeft: 0 })
        }
      } catch (error) {
        console.error("Error checking slot availability:", error)
        setAvailability({ available: false, slotsLeft: 0, error: true })
      } finally {
        setIsLoading(false)
      }
    }

    const timer = setTimeout(() => {
      checkAvailability()
    }, 300)

    return () => clearTimeout(timer)
  }, [locationId, date, time])

  if (isLoading) {
    return <p className="text-sm text-muted-foreground mt-2">Checking availability...</p>
  }

  if (!availability) {
    return null
  }

  return (
    <p className="text-sm mt-2 h-5">
      {availability.available ? (
        <span className="text-green-600 font-bold">
          {availability.slotsLeft} reservation slots available ({availability.guestsAvailable} guest capacity)
        </span>
      ) : (
        <span className="text-red-600 font-bold">
          {availability.error ? "Could not check availability." : "No availability for this time slot."}
        </span>
      )}
    </p>
  )
}

function ReservationForm() {
  const [locations, setLocations] = useState([])
  const [formData, setFormData] = useState({
    location_id: "",
    date: "",
    time: "",
    party_size: "",
    name: "",
    email: "",
    phone: "",
    special_requests: "",
  })
  const [timeSlots, setTimeSlots] = useState([])
  const [message, setMessage] = useState("")
  const [messageType, setMessageType] = useState("")
  const [showLargePartyBanner, setShowLargePartyBanner] = useState(false)

  useEffect(() => {
    const fetchLocations = async () => {
      try {
        const data = await reservationService.getLocations()
        setLocations(data.locations)
      } catch (error) {
        console.error("Error fetching locations:", error)
        toast.error("Failed to load locations")
      }
    }
    fetchLocations()
  }, [])

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

        const displayDate = new Date()
        displayDate.setHours(hour, minute, 0)
        const timeFormatted = displayDate.toLocaleTimeString("en-US", {
          hour: "numeric",
          minute: "2-digit",
          hour12: true,
        })

        slots.push({ display: timeFormatted, value: timeValue })
      }

      setTimeSlots(slots)
      setFormData((prev) => ({ ...prev, time: "" }))
    } else {
      setTimeSlots([])
    }
  }, [formData.date])

  useEffect(() => {
    if (formData.party_size && Number.parseInt(formData.party_size) > 12) {
      setShowLargePartyBanner(true)
    } else {
      setShowLargePartyBanner(false)
    }
  }, [formData.party_size])

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (Number.parseInt(formData.party_size) > 12) {
      toast.error("For parties larger than 12 guests, please call us directly.")
      return
    }

    try {
      const data = await reservationService.createReservation(formData)

      toast.success(`Reservation confirmed! Your reservation number is ${data.reservationNumber}`, {
        position: "top-right",
        autoClose: 5000,
        hideProgressBar: false,
        closeOnClick: true,
        pauseOnHover: true,
        draggable: true,
        theme: "light",
      })

      setMessage(`Reservation confirmed: ${data.message}`)
      setMessageType("success")
      setFormData({
        location_id: "",
        date: "",
        time: "",
        party_size: "",
        name: "",
        email: "",
        phone: "",
        special_requests: "",
      })
      setTimeSlots([])
    } catch (err) {
      toast.error(`Error: ${err.message}`, {
        position: "top-right",
        autoClose: 5000,
        hideProgressBar: false,
        closeOnClick: true,
        pauseOnHover: true,
        draggable: true,
        theme: "light",
      })

      setMessage(`Error: ${err.message}`)
      setMessageType("error")
    }
  }

  const getDayName = (dateString) => {
    const date = new Date(dateString + "T00:00:00")
    const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    return days[date.getUTCDay()]
  }

  const getAvailableTimesText = (dateString) => {
    const date = new Date(dateString + "T00:00:00")
    const dayOfWeek = date.getUTCDay()
    const isSundayOrMonday = dayOfWeek === 0 || dayOfWeek === 1
    return isSundayOrMonday ? "5:00 PM - 8:30 PM" : "5:00 PM - 10:30 PM"
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h2 className="text-3xl font-bold text-deep-blue mb-6">Reserve Your Table</h2>
      <p className="text-muted-foreground mb-8">
        Please fill out the form below to reserve your table. We'll confirm your reservation shortly.
      </p>

      {showLargePartyBanner && (
        <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <p className="text-amber-800 text-sm">
            <strong>Large Party Notice:</strong> For special requests, dietary restrictions, or large party reservations
            (more than 12 guests), please call us directly.
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6 bg-card p-8 rounded-xl shadow-lg border border-border">
        <div>
          <label className="block text-sm font-medium text-deep-blue mb-2">Location*</label>
          <select
            name="location_id"
            value={formData.location_id}
            onChange={handleChange}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-deep-blue shadow-sm focus:border-primary focus:ring focus:ring-primary focus:ring-opacity-50"
            required
          >
            <option value="">Select a location</option>
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-deep-blue mb-2">Date*</label>
          <input
            type="date"
            name="date"
            value={formData.date}
            onChange={handleChange}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-deep-blue shadow-sm focus:border-primary focus:ring focus:ring-primary focus:ring-opacity-50"
            required
            min={new Date().toISOString().split("T")[0]}
            disabled={!formData.location_id}
          />
          {!formData.location_id && (
            <p className="text-sm text-muted-foreground mt-2">Please select a location first</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-deep-blue mb-2">Time*</label>
          <select
            name="time"
            value={formData.time}
            onChange={handleChange}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-deep-blue shadow-sm focus:border-primary focus:ring focus:ring-primary focus:ring-opacity-50"
            required
            disabled={!formData.date}
          >
            <option value="">Select a time</option>
            {timeSlots.map((slot, index) => (
              <option key={index} value={slot.value}>
                {slot.display}
              </option>
            ))}
          </select>
          {!formData.date && <p className="text-sm text-muted-foreground mt-2">Please select a date first</p>}
          {formData.date && timeSlots.length > 0 && (
            <p className="text-sm text-muted-foreground mt-2">
              {getDayName(formData.date)} hours: {getAvailableTimesText(formData.date)}
            </p>
          )}

          {formData.location_id && formData.date && formData.time && (
            <SlotAvailabilityChecker locationId={formData.location_id} date={formData.date} time={formData.time} />
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-deep-blue mb-2">Number of Guests*</label>
          <input
            type="number"
            min="1"
            max="12"
            name="party_size"
            value={formData.party_size}
            onChange={handleChange}
            placeholder="Number of guests (1-12)"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-deep-blue shadow-sm focus:border-primary focus:ring focus:ring-primary focus:ring-opacity-50"
            required
          />
          <p className="text-sm text-muted-foreground mt-2">Maximum 12 guests for online bookings</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-deep-blue mb-2">Full Name*</label>
          <input
            type="text"
            name="name"
            value={formData.name}
            onChange={handleChange}
            placeholder="Enter your full name"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-deep-blue shadow-sm focus:border-primary focus:ring focus:ring-primary focus:ring-opacity-50"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-deep-blue mb-2">Email Address*</label>
          <input
            type="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            placeholder="you@example.com"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-deep-blue shadow-sm focus:border-primary focus:ring focus:ring-primary focus:ring-opacity-50"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-deep-blue mb-2">Phone (Optional)</label>
          <input
            type="tel"
            name="phone"
            value={formData.phone}
            onChange={handleChange}
            placeholder="(202) 555-4567"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-deep-blue shadow-sm focus:border-primary focus:ring focus:ring-primary focus:ring-opacity-50"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-deep-blue mb-2">Special Requests (Optional)</label>
          <textarea
            name="special_requests"
            value={formData.special_requests}
            onChange={handleChange}
            placeholder="Dietary restrictions, accessibility needs, special occasions, etc."
            rows="3"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-deep-blue shadow-sm focus:border-primary focus:ring focus:ring-primary focus:ring-opacity-50"
          />
        </div>

        <button type="submit" className="btn w-full">
          Make Reservation
        </button>

        {message && (
          <div
            className={`mt-6 p-4 rounded-lg text-center text-lg font-medium ${
              messageType === "success"
                ? "bg-green-100 text-green-800 border border-green-200"
                : "bg-red-100 text-red-800 border border-red-200"
            }`}
          >
            {message}
          </div>
        )}
      </form>
    </div>
  )
}

export default ReservationForm
