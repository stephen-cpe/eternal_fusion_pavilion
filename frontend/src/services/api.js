const getApiBaseUrl = () => {
  // In development, use the proxy path; in production, use relative path
  if (process.env.NODE_ENV === "production") {
    return "/api"
  } else {
    // During development, Vite proxy will handle /api requests
    return "/api"
  }
}

const API_BASE_URL = getApiBaseUrl()

export const reservationService = {
  getLocations: async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/reservations/locations`)
      if (!response.ok) {
        throw new Error("Failed to fetch locations")
      }
      return await response.json()
    } catch (error) {
      console.error("Locations fetch error:", error)
      throw error
    }
  },

  getAvailability: async (locationId, date) => {
    try {
      const response = await fetch(`${API_BASE_URL}/reservations/availability?location_id=${locationId}&date=${date}`)
      if (!response.ok) {
        throw new Error("Failed to fetch availability")
      }
      return await response.json()
    } catch (error) {
      console.error("Reservation availability error:", error)
      throw error
    }
  },

  createReservation: async (reservationData) => {
    try {
      const response = await fetch(`${API_BASE_URL}/reservations/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(reservationData),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || "Failed to create reservation")
      }

      return await response.json()
    } catch (error) {
      console.error("Reservation creation error:", error)
      throw error
    }
  },
}

export const adminService = {
  login: async (username, password) => {
    const response = await fetch(`${API_BASE_URL}/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ username, password }),
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.error || "Login failed")
    }
    return data
  },
  logout: async () => {
    const response = await fetch(`${API_BASE_URL}/admin/logout`, {
      method: "POST",
      credentials: "include",
    })
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.error || "Logout failed")
    }
    return await response.json()
  },
  getReservations: async (filters = {}) => {
    const params = new URLSearchParams()
    if (filters.location_id) params.append("location_id", filters.location_id)
    if (filters.date) params.append("date", filters.date)
    if (filters.search) params.append("search", filters.search)

    const response = await fetch(`${API_BASE_URL}/admin/reservations?${params.toString()}`, {
      method: "GET",
      credentials: "include",
    })
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.error || "Failed to fetch reservations")
    }
    return response.json()
  },

  getProfile: async () => {
    const response = await fetch(`${API_BASE_URL}/admin/profile`, {
      credentials: "include",
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.error || "Failed to fetch profile")
    }
    return data
  },

  updateName: async (fullName) => {
    const response = await fetch(`${API_BASE_URL}/admin/profile/name`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ fullName }),
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.error || "Failed to update name")
    }
    return data
  },

  updatePassword: async (passwords) => {
    const response = await fetch(`${API_BASE_URL}/admin/profile/password`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(passwords),
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.error || "Failed to update password")
    }
    return data
  },

  getDashboardStats: async (locationId, date) => {
    const response = await fetch(`${API_BASE_URL}/admin/dashboard/stats?location_id=${locationId}&date=${date}`, {
      method: "GET",
      credentials: "include",
    })
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.error || "Failed to fetch dashboard stats")
    }
    return response.json()
  },

  getCustomers: async () => {
    const response = await fetch(`${API_BASE_URL}/admin/customers`, {
      method: "GET",
      credentials: "include",
    });

    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || "Failed to fetch customers");
    }
    return response.json();
  },

  updateCustomerDetails: async (customerId, data) => {
    const response = await fetch(`${API_BASE_URL}/admin/customers/${customerId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(data),
    });
    const responseData = await response.json();
    if (!response.ok) {
      throw new Error(responseData.error || "Failed to update customer details");
    }
    return responseData;
  },

  getSubscribers: async () => {
    const response = await fetch(`${API_BASE_URL}/admin/subscribers`, {
      method: "GET",
      credentials: "include",
    })

    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.error || "Failed to fetch subscribers")
    }
    return response.json()
  },
  updateReservation: async (id, status) => {
    const response = await fetch(`${API_BASE_URL}/admin/reservations/${id}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ status }),
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.error || "Failed to update reservation")
    }
    return data
  },


  addReservation: async (reservationData) => {
    const response = await fetch(`${API_BASE_URL}/reservations/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(reservationData),
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.error || "Failed to add reservation")
    }
    return data
  },
  deleteReservation: async (id) => {
    const response = await fetch(`${API_BASE_URL}/admin/reservations/${id}`, {
      method: "DELETE",
      credentials: "include",
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.error || "Failed to delete reservation")
    }
    return data
  },

  getRooms: async (locationId) => {
    const response = await fetch(`${API_BASE_URL}/admin/rooms?location_id=${locationId}`, {
      method: "GET",
      credentials: "include",
    })
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.error || "Failed to fetch rooms")
    }
    return response.json()
  },

  getBlocks: async (locationId) => {
    const params = new URLSearchParams()
    if (locationId) params.append("location_id", locationId)

    const response = await fetch(`${API_BASE_URL}/admin/blocks?${params.toString()}`, {
      method: "GET",
      credentials: "include",
    })
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.error || "Failed to fetch blocks")
    }
    return response.json()
  },

  createBlock: async (blockData) => {
    const response = await fetch(`${API_BASE_URL}/admin/blocks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(blockData),
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.error || "Failed to create block")
    }
    return data
  },

  deleteBlock: async (blockId) => {
    const response = await fetch(`${API_BASE_URL}/admin/blocks/${blockId}`, {
      method: "DELETE",
      credentials: "include",
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.error || "Failed to delete block")
    }
    return data
  },

  updateReservationDetails: async (reservationId, data) => {
    const response = await fetch(`${API_BASE_URL}/admin/reservations/${reservationId}/details`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(data),
    })
    const resData = await response.json()
    if (!response.ok) {
      throw new Error(resData.error || "Failed to update reservation details")
    }
    return resData
  },

  updateReservationRoom: async (reservationId, roomId) => {
    const response = await fetch(`${API_BASE_URL}/admin/reservations/${reservationId}/room`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ room_id: roomId }),
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.error || "Failed to update room assignment")
    }
    return data
  },

  createAdminReservation: async (reservationData) => {
    const response = await fetch(`${API_BASE_URL}/admin/reservations/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(reservationData),
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.error || "Failed to create reservation")
    }
    return data
  },

  getAuditLog: async (limit = 50) => {
    const response = await fetch(`${API_BASE_URL}/admin/audit-log?limit=${limit}`, {
      method: "GET",
      credentials: "include",
    })
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.error || "Failed to fetch audit log")
    }
    return response.json()
  },
}

// Newsletter API services
export const newsletterService = {
  subscribe: async (email, name) => {
    try {
      const response = await fetch(`${API_BASE_URL}/newsletter/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, name }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || "Failed to subscribe")
      }

      return await response.json()
    } catch (error) {
      console.error("Newsletter subscription error:", error)
      throw error
    }
  },
}
