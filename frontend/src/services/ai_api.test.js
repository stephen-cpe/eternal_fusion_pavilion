/**
 * Tests for services/ai_api.js — guest ID / thread ID management + API calls.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";

// Mock localStorage before importing the module.
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: vi.fn((key) => store[key] || null),
    setItem: vi.fn((key, value) => { store[key] = String(value); }),
    removeItem: vi.fn((key) => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
  };
})();

Object.defineProperty(globalThis, "localStorage", {
  value: localStorageMock,
  writable: true,
});

// Import after mocks are set up.
import {
  getGuestId,
  getThreadId,
  newThreadId,
  clearThreadId,
  sendChat,
} from "../services/ai_api";

beforeEach(() => {
  localStorageMock.clear();
  localStorageMock.getItem.mockClear();
  localStorageMock.setItem.mockClear();
  localStorageMock.removeItem.mockClear();
});

describe("getGuestId", () => {
  it("creates a UUID if none exists in localStorage", () => {
    const id = getGuestId();
    expect(id).toBeTruthy();
    expect(id.length).toBeGreaterThan(10);
    expect(localStorageMock.setItem).toHaveBeenCalledWith("efp_guest_id", id);
  });

  it("returns the existing UUID from localStorage", () => {
    localStorageMock.setItem("efp_guest_id", "existing-uuid-123");
    localStorageMock.getItem.mockReturnValueOnce("existing-uuid-123");
    const id = getGuestId();
    expect(id).toBe("existing-uuid-123");
  });
});

describe("getThreadId", () => {
  it("returns empty string when no thread ID exists", () => {
    const id = getThreadId();
    expect(id).toBe("");
  });

  it("returns the stored thread ID", () => {
    localStorageMock.setItem("efp_thread_id", "thread-abc");
    localStorageMock.getItem.mockReturnValueOnce("thread-abc");
    const id = getThreadId();
    expect(id).toBe("thread-abc");
  });
});

describe("newThreadId", () => {
  it("generates and stores a new UUID", () => {
    const id = newThreadId();
    expect(id).toBeTruthy();
    expect(id.length).toBeGreaterThan(10);
    expect(localStorageMock.setItem).toHaveBeenCalledWith("efp_thread_id", id);
  });

  it("generates different UUIDs on successive calls", () => {
    const id1 = newThreadId();
    const id2 = newThreadId();
    expect(id1).not.toBe(id2);
  });
});

describe("clearThreadId", () => {
  it("removes the thread ID from localStorage", () => {
    clearThreadId();
    expect(localStorageMock.removeItem).toHaveBeenCalledWith("efp_thread_id");
  });
});

describe("sendChat", () => {
  it("sends a POST with question, guest_identifier, and thread_id", async () => {
    const mockResponse = {
      ok: true,
      json: vi.fn().mockResolvedValue({ answer: "The wagyu is $165.", thread_id: "t1" }),
    };
    global.fetch = vi.fn().mockResolvedValue(mockResponse);

    localStorageMock.setItem("efp_guest_id", "guest-123");
    localStorageMock.setItem("efp_thread_id", "thread-456");
    localStorageMock.getItem.mockImplementation((key) => {
      if (key === "efp_guest_id") return "guest-123";
      if (key === "efp_thread_id") return "thread-456";
      return null;
    });

    const result = await sendChat("How much is the wagyu?");

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/ai/graph",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: expect.stringContaining("How much is the wagyu?"),
      }),
    );

    // Verify the body includes guest_identifier and thread_id.
    const callBody = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(callBody.guest_identifier).toBe("guest-123");
    expect(callBody.thread_id).toBe("thread-456");

    expect(result.answer).toBe("The wagyu is $165.");
  });

  it("throws on non-OK response", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 503 });
    localStorageMock.getItem.mockReturnValue("guest-1");

    await expect(sendChat("test")).rejects.toThrow("HTTP 503");
  });
});