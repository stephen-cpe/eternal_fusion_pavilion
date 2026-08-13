import axios from "axios";

const API_BASE_URL = "/api";

// A single configured axios instance shared by all services. Credentials are
// sent on every request so the Flask session cookie is honored.
const http = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

// Normalize errors so every caller can `throw new Error(data.error)` exactly as
// before, regardless of whether the failure was a non-2xx HTTP response or a
// network/transport error.
http.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const serverMessage =
      error.response?.data?.error ||
      error.response?.data?.message ||
      error.message ||
      "Request failed";
    return Promise.reject(new Error(serverMessage));
  },
);

// Helper: build a query string from a filters object, dropping falsy values.
function buildParams(filters) {
  const params = {};
  for (const [k, v] of Object.entries(filters)) {
    if (v) params[k] = v;
  }
  return params;
}

export const reservationService = {
  getLocations: () => http.get("/reservations/locations").then((r) => r.data),

  getAvailability: (locationId, date) =>
    http
      .get("/reservations/availability", { params: { location_id: locationId, date } })
      .then((r) => r.data),

  createReservation: (reservationData) =>
    http.post("/reservations/", reservationData).then((r) => r.data),
};

export const adminService = {
  login: (username, password) =>
    http.post("/admin/login", { username, password }).then((r) => r.data),

  logout: () => http.post("/admin/logout").then((r) => r.data),

  getReservations: (filters = {}) =>
    http
      .get("/admin/reservations", { params: buildParams(filters) })
      .then((r) => r.data),

  getProfile: () => http.get("/admin/profile").then((r) => r.data),

  updateName: (fullName) =>
    http.put("/admin/profile/name", { fullName }).then((r) => r.data),

  updatePassword: (passwords) =>
    http.put("/admin/profile/password", passwords).then((r) => r.data),

  getDashboardStats: (locationId, date) =>
    http
      .get("/admin/dashboard/stats", { params: { location_id: locationId, date } })
      .then((r) => r.data),

  getCustomers: () => http.get("/admin/customers").then((r) => r.data),

  updateCustomerDetails: (customerId, data) =>
    http.put(`/admin/customers/${customerId}`, data).then((r) => r.data),

  getSubscribers: () => http.get("/admin/subscribers").then((r) => r.data),

  updateReservation: (id, status) =>
    http.put(`/admin/reservations/${id}/status`, { status }).then((r) => r.data),

  addReservation: (reservationData) =>
    http.post("/reservations/", reservationData).then((r) => r.data),

  deleteReservation: (id) =>
    http.delete(`/admin/reservations/${id}`).then((r) => r.data),

  getRooms: (locationId) =>
    http
      .get("/admin/rooms", { params: { location_id: locationId } })
      .then((r) => r.data),

  getBlocks: (locationId) =>
    http
      .get("/admin/blocks", { params: locationId ? { location_id: locationId } : {} })
      .then((r) => r.data),

  createBlock: (blockData) => http.post("/admin/blocks", blockData).then((r) => r.data),

  deleteBlock: (blockId) => http.delete(`/admin/blocks/${blockId}`).then((r) => r.data),

  updateReservationDetails: (reservationId, data) =>
    http.put(`/admin/reservations/${reservationId}/details`, data).then((r) => r.data),

  updateReservationRoom: (reservationId, roomId) =>
    http.put(`/admin/reservations/${reservationId}/room`, { room_id: roomId }).then((r) => r.data),

  createAdminReservation: (reservationData) =>
    http.post("/admin/reservations/create", reservationData).then((r) => r.data),

  getAuditLog: (limit = 50) =>
    http
      .get("/admin/audit-log", { params: { limit } })
      .then((r) => r.data),
};

export const newsletterService = {
  subscribe: (email, name) =>
    http.post("/newsletter/", { email, name }).then((r) => r.data),
};