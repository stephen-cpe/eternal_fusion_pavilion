/**
 * Tests for services/api.js — verify the correct URL/method/params/body are
 * emitted and that responses (success and error) are parsed correctly.
 *
 * We mock the `axios` module so `axios.create` returns a stub instance whose
 * `.get/.post/.put/.delete` methods are Vitest mocks we control per-test.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";

// --- axios mock ----------------------------------------------------------- //
// vi.hoisted runs before vi.mock's factory is evaluated, so the stub exists
// when axios.create() is called at module-load time.
const httpStub = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
  interceptors: { response: { use: vi.fn() } },
}));

vi.mock("axios", () => ({
  default: {
    create: vi.fn(() => httpStub),
  },
}));

// Import the services AFTER the mock is registered so they pick up the stub.
import {
  reservationService,
  adminService,
  newsletterService,
} from "../services/api";

// --- helpers -------------------------------------------------------------- //
function mockOk(fn, data) {
  fn.mockResolvedValueOnce({ data });
}

function mockHttpError(fn, status, body) {
  // axios rejects with an error carrying .response.{status,data}
  const err = new Error(body.error || "Request failed");
  err.response = { status, data: body };
  fn.mockRejectedValueOnce(err);
}

beforeEach(() => {
  httpStub.get.mockReset();
  httpStub.post.mockReset();
  httpStub.put.mockReset();
  httpStub.delete.mockReset();
});

// --------------------------------------------------------------------------- //
// reservationService                                                          //
// --------------------------------------------------------------------------- //
describe("reservationService", () => {
  it("getLocations GETs /reservations/locations", async () => {
    mockOk(httpStub.get, { locations: [{ id: 1, name: "Japan" }] });
    const data = await reservationService.getLocations();
    expect(httpStub.get).toHaveBeenCalledWith("/reservations/locations");
    expect(data.locations[0].name).toBe("Japan");
  });

  it("getAvailability passes location_id and date as params", async () => {
    mockOk(httpStub.get, { date: "2026-08-12", slots: [] });
    await reservationService.getAvailability(3, "2026-08-12");
    expect(httpStub.get).toHaveBeenCalledWith("/reservations/availability", {
      params: { location_id: 3, date: "2026-08-12" },
    });
  });

  it("createReservation POSTs the payload", async () => {
    mockOk(httpStub.post, { id: 1, reservationNumber: "JPN-ABC12" });
    const payload = { location_id: 1, date: "2026-08-12", party_size: 4 };
    await reservationService.createReservation(payload);
    expect(httpStub.post).toHaveBeenCalledWith("/reservations/", payload);
  });

  it("createReservation rejects with the server error message", async () => {
    mockHttpError(httpStub.post, 400, { error: "Party size out of range" });
    await expect(reservationService.createReservation({})).rejects.toThrow(
      "Party size out of range",
    );
  });
});

// --------------------------------------------------------------------------- //
// adminService                                                                //
// --------------------------------------------------------------------------- //
describe("adminService", () => {
  it("login POSTs credentials", async () => {
    mockOk(httpStub.post, { message: "ok", admin: { id: 1 } });
    await adminService.login("u", "p");
    expect(httpStub.post).toHaveBeenCalledWith("/admin/login", { username: "u", password: "p" });
  });

  it("getReservations builds params from filters (dropping falsy)", async () => {
    mockOk(httpStub.get, []);
    await adminService.getReservations({ location_id: 2, date: "2026-08-12", search: "alice" });
    expect(httpStub.get).toHaveBeenCalledWith("/admin/reservations", {
      params: { location_id: 2, date: "2026-08-12", search: "alice" },
    });
  });

  it("getReservations omits empty filters", async () => {
    mockOk(httpStub.get, []);
    await adminService.getReservations({});
    expect(httpStub.get).toHaveBeenCalledWith("/admin/reservations", { params: {} });
  });

  it("getProfile GETs /admin/profile", async () => {
    mockOk(httpStub.get, { username: "admin", fullName: "A", role: "admin" });
    await adminService.getProfile();
    expect(httpStub.get).toHaveBeenCalledWith("/admin/profile");
  });

  it("updateName PUTs { fullName }", async () => {
    mockOk(httpStub.put, { message: "ok" });
    await adminService.updateName("New Name");
    expect(httpStub.put).toHaveBeenCalledWith("/admin/profile/name", { fullName: "New Name" });
  });

  it("updatePassword PUTs the three password fields", async () => {
    mockOk(httpStub.put, { message: "ok" });
    const passwords = { currentPassword: "a", newPassword: "b", confirmPassword: "b" };
    await adminService.updatePassword(passwords);
    expect(httpStub.put).toHaveBeenCalledWith("/admin/profile/password", passwords);
  });

  it("deleteReservation uses DELETE", async () => {
    mockOk(httpStub.delete, { message: "ok" });
    await adminService.deleteReservation(42);
    expect(httpStub.delete).toHaveBeenCalledWith("/admin/reservations/42");
  });

  it("getRooms passes location_id as a param", async () => {
    mockOk(httpStub.get, [{ id: 1, code: "R1" }]);
    await adminService.getRooms(7);
    expect(httpStub.get).toHaveBeenCalledWith("/admin/rooms", { params: { location_id: 7 } });
  });

  it("createBlock POSTs block JSON", async () => {
    mockOk(httpStub.post, { id: 9, message: "ok" });
    const block = { location_id: 1, block_type: "hard" };
    await adminService.createBlock(block);
    expect(httpStub.post).toHaveBeenCalledWith("/admin/blocks", block);
  });

  it("getAuditLog passes limit as a param", async () => {
    mockOk(httpStub.get, []);
    await adminService.getAuditLog(25);
    expect(httpStub.get).toHaveBeenCalledWith("/admin/audit-log", { params: { limit: 25 } });
  });

  it("rejects with server error message on failure", async () => {
    mockHttpError(httpStub.delete, 400, { error: "In use" });
    await expect(adminService.deleteReservation(1)).rejects.toThrow("In use");
  });
});

// --------------------------------------------------------------------------- //
// newsletterService                                                           //
// --------------------------------------------------------------------------- //
describe("newsletterService", () => {
  it("subscribe POSTs email and name", async () => {
    mockOk(httpStub.post, { message: "subscribed" });
    await newsletterService.subscribe("a@b.com", "Alice");
    expect(httpStub.post).toHaveBeenCalledWith("/newsletter/", { email: "a@b.com", name: "Alice" });
  });

  it("subscribe rejects with server error on failure", async () => {
    mockHttpError(httpStub.post, 400, { error: "Invalid email" });
    await expect(newsletterService.subscribe("bad", "A")).rejects.toThrow("Invalid email");
  });
});