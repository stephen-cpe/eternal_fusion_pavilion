/**
 * Tests for components/ConciergeChat.jsx — render + interaction tests.
 *
 * Mocks the ai_api service so no network calls are made.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// Mock the ai_api module.
vi.mock("../services/ai_api", () => ({
  streamChat: vi.fn(),
  getGuestId: vi.fn(() => "test-guest-uuid"),
  newThreadId: vi.fn(() => "test-thread-uuid"),
  clearThreadId: vi.fn(),
  getThreadId: vi.fn(() => ""),
}));

// Mock framer-motion to avoid animation timing issues in tests.
vi.mock("framer-motion", () => ({
  motion: {
    button: ({ children, onClick, ...props }) => (
      <button onClick={onClick} {...props}>{children}</button>
    ),
    div: ({ children, ...props }) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

import ConciergeChat from "../components/ConciergeChat";
import { streamChat } from "../services/ai_api";

function renderChat() {
  return render(
    <MemoryRouter>
      <ConciergeChat />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ConciergeChat", () => {
  it("renders the floating button by default", () => {
    renderChat();
    const button = screen.getByLabelText(/open concierge/i);
    expect(button).toBeDefined();
  });

  it("opens the chat panel when the button is clicked", () => {
    renderChat();
    const button = screen.getByLabelText(/open concierge/i);
    fireEvent.click(button);

    // Panel should be visible with a header.
    expect(screen.getByText("EFP Concierge")).toBeDefined();
    // Welcome message should be shown.
    expect(screen.getByText(/Welcome to Eternal Fusion Pavilion/i)).toBeDefined();
  });

  it("renders input field when open", () => {
    renderChat();
    fireEvent.click(screen.getByLabelText(/open concierge/i));

    const input = screen.getByLabelText(/type your message/i);
    expect(input).toBeDefined();
  });

  it("closes the panel when the close button is clicked", () => {
    renderChat();
    // Open
    fireEvent.click(screen.getByLabelText(/open concierge/i));
    expect(screen.getByText("EFP Concierge")).toBeDefined();

    // Close via the close button in the header.
    const closeBtn = screen.getByLabelText(/close chat/i);
    fireEvent.click(closeBtn);

    // The open button should be visible again.
    expect(screen.getByLabelText(/open concierge/i)).toBeDefined();
  });

  it("sends a message when Enter is pressed", async () => {
    streamChat.mockResolvedValue(undefined);

    renderChat();
    fireEvent.click(screen.getByLabelText(/open concierge/i));

    const input = screen.getByLabelText(/type your message/i);
    fireEvent.change(input, { target: { value: "How much is the wagyu?" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(streamChat).toHaveBeenCalledTimes(1);
    });

    // Verify the question was passed.
    const callArgs = streamChat.mock.calls[0];
    expect(callArgs[0]).toBe("How much is the wagyu?");
  });

  it("does not send empty messages", () => {
    renderChat();
    fireEvent.click(screen.getByLabelText(/open concierge/i));

    const input = screen.getByLabelText(/type your message/i);
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(streamChat).not.toHaveBeenCalled();
  });

  it("renders error state when streamChat calls onError", async () => {
    streamChat.mockImplementation(async (question, callbacks) => {
      callbacks.onError("The concierge is unavailable.");
    });

    renderChat();
    fireEvent.click(screen.getByLabelText(/open concierge/i));

    const input = screen.getByLabelText(/type your message/i);
    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText(/concierge is unavailable/i)).toBeDefined();
    });

    // Should show a link to the reservations page.
    expect(screen.getByText(/go to reservations/i)).toBeDefined();
  });

  it("renders streaming tokens as they arrive", async () => {
    streamChat.mockImplementation(async (question, callbacks) => {
      callbacks.onToken("Hello ");
      callbacks.onToken("there!");
      callbacks.onDone({ done: true, thread_id: "t1" });
    });

    renderChat();
    fireEvent.click(screen.getByLabelText(/open concierge/i));

    const input = screen.getByLabelText(/type your message/i);
    fireEvent.change(input, { target: { value: "hi" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText(/Hello there!/i)).toBeDefined();
    });
  });

  it("renders tool status badge during tool calls", async () => {
    let resolveDone;
    streamChat.mockImplementation(async (question, callbacks) => {
      callbacks.onToolCall({ name: "check_availability", arguments: {} });
      // Don't call onDone yet — keep toolStatus visible.
      return new Promise((resolve) => { resolveDone = resolve; });
    });

    renderChat();
    fireEvent.click(screen.getByLabelText(/open concierge/i));

    const input = screen.getByLabelText(/type your message/i);
    fireEvent.change(input, { target: { value: "book a table" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText(/checking availability/i)).toBeDefined();
    });

    if (resolveDone) resolveDone();
  });

  it("renders escalation notice when onEscalation is called", async () => {
    streamChat.mockImplementation(async (question, callbacks) => {
      callbacks.onEscalation("Party size exceeds 12.");
      callbacks.onDone({ done: true });
    });

    renderChat();
    fireEvent.click(screen.getByLabelText(/open concierge/i));

    const input = screen.getByLabelText(/type your message/i);
    fireEvent.change(input, { target: { value: "15 people" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText(/our team will follow up/i)).toBeDefined();
    });
  });

  it("renders booking confirmation card on successful reservation", async () => {
    streamChat.mockImplementation(async (question, callbacks) => {
      callbacks.onToolResult({
        name: "create_reservation",
        result: {
          success: true,
          reservation_number: "JPN-X1234",
          room: { name: "Sakura Pavilion", code: "JPN-SP" },
          message: "Reservation confirmed!",
        },
      });
      callbacks.onToken("Your reservation is confirmed!");
      callbacks.onDone({ done: true });
    });

    renderChat();
    fireEvent.click(screen.getByLabelText(/open concierge/i));

    const input = screen.getByLabelText(/type your message/i);
    fireEvent.change(input, { target: { value: "book it" } });
    fireEvent.keyDown(input, { key: "Enter" });

    // Wait for the confirmation card to appear.
    await waitFor(() => {
      expect(screen.getByText("Reservation Confirmed")).toBeDefined();
    }, { timeout: 3000 });
    expect(screen.getByText(/JPN-X1234/)).toBeDefined();
  });
});