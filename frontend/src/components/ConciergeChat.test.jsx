/**
 * Tests for components/ConciergeChat.jsx — render + interaction tests.
 *
 * Mocks the ai_api service so no network calls are made.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// Mock the ai_api module.
vi.mock("../services/ai_api", () => ({
  streamChat: vi.fn(),
  getGuestId: vi.fn(() => "test-guest-uuid"),
  getThreadId: vi.fn(() => "test-thread-uuid"),
  newThreadId: vi.fn(() => "test-thread-uuid"),
  clearThreadId: vi.fn(),
  streamResume: vi.fn(),
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

// Mock react-markdown so tests don't need the full markdown renderer.
vi.mock("react-markdown", () => ({
  default: ({ children }) => <div data-testid="markdown">{children}</div>,
}));

vi.mock("remark-gfm", () => ({
  default: () => ({}),
}));

import ConciergeChat from "../components/ConciergeChat";
import { streamChat, streamResume, clearThreadId, newThreadId } from "../services/ai_api";

function renderChat() {
  return render(
    <MemoryRouter>
      <ConciergeChat />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  try { sessionStorage.clear(); } catch { /* ignore */ }
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

  it("renders HITL confirmation card when interrupted", async () => {
    streamChat.mockImplementation(async (question, callbacks) => {
      callbacks.onDone({
        done: true,
        interrupted: true,
        thread_id: "interrupt-thread-1",
        interrupt_data: {
          type: "booking_confirmation",
          details: { location_id: 1, date: "2026-08-29", time: "19:00", party_size: 4, name: "John", email: "john@example.com" },
          message: "Please confirm your reservation:\n- Location ID: 1\n- Date: 2026-08-29\n- Time: 19:00\n- Party size: 4\n- Name: John\n- Email: john@example.com\nShall I confirm this booking?",
        },
      });
    });

    renderChat();
    fireEvent.click(screen.getByLabelText(/open concierge/i));

    const input = screen.getByLabelText(/type your message/i);
    fireEvent.change(input, { target: { value: "book a table for 4" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText(/Booking Confirmation Required/i)).toBeDefined();
    });
    expect(screen.getByText(/Confirm Booking/i)).toBeDefined();
    expect(screen.getByText(/Cancel/i)).toBeDefined();
  });

  it("calls streamResume when user confirms", async () => {
    streamResume.mockImplementation(async (threadId, confirmed, callbacks) => {
      callbacks.onToken("Your reservation is confirmed!");
      callbacks.onDone({ done: true });
    });

    streamChat.mockImplementation(async (question, callbacks) => {
      callbacks.onDone({
        done: true,
        interrupted: true,
        thread_id: "confirm-thread",
        interrupt_data: {
          type: "booking_confirmation",
          details: {},
          message: "Confirm?",
        },
      });
    });

    renderChat();
    fireEvent.click(screen.getByLabelText(/open concierge/i));

    const input = screen.getByLabelText(/type your message/i);
    fireEvent.change(input, { target: { value: "book it" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText(/Confirm Booking/i)).toBeDefined();
    });

    fireEvent.click(screen.getByText(/Confirm Booking/i));

    await waitFor(() => {
      expect(streamResume).toHaveBeenCalled();
      expect(streamResume.mock.calls[0][0]).toBe("confirm-thread");
      expect(streamResume.mock.calls[0][1]).toBe(true);
    });
  });

  it("shows 'Sending…' before the first SSE frame with aria-live", async () => {
    let resolveStream;
    streamChat.mockImplementation(() => new Promise((resolve) => { resolveStream = resolve; }));

    renderChat();
    fireEvent.click(screen.getByLabelText(/open concierge/i));

    const input = screen.getByLabelText(/type your message/i);
    fireEvent.change(input, { target: { value: "hello" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      const status = screen.getByText("Sending…");
      expect(status).toBeDefined();
      expect(status.getAttribute("aria-live")).toBe("polite");
    });

    if (resolveStream) resolveStream();
  });

  it("shows 'Thinking…' after node frames and 'Writing the reply…' after agent", async () => {
    let resolveStream;
    streamChat.mockImplementation(async (question, callbacks) => {
      callbacks.onNode("rag");
      callbacks.onNode("tools");
      await new Promise((resolve) => { resolveStream = resolve; });
    });

    renderChat();
    fireEvent.click(screen.getByLabelText(/open concierge/i));

    const input = screen.getByLabelText(/type your message/i);
    fireEvent.change(input, { target: { value: "what desserts?" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText("Thinking…")).toBeDefined();
    });

    // A later agent frame with no tool calls moves to the writing label.
    await act(async () => {
      streamChat.mock.calls[0][1].onNode("agent");
    });
    expect(screen.getByText("Writing the reply…")).toBeDefined();

    if (resolveStream) resolveStream();
  });

  it("appends elapsed seconds to the status after 5 seconds", async () => {
    vi.useFakeTimers();
    try {
      let resolveStream;
      streamChat.mockImplementation((question, callbacks) => {
        callbacks.onNode("rag");
        return new Promise((resolve) => { resolveStream = resolve; });
      });

      renderChat();
      fireEvent.click(screen.getByLabelText(/open concierge/i));

      const input = screen.getByLabelText(/type your message/i);
      fireEvent.change(input, { target: { value: "hello" } });
      fireEvent.keyDown(input, { key: "Enter" });

      await act(async () => { vi.advanceTimersByTime(0); });
      expect(screen.getByText("Thinking…")).toBeDefined();

      await act(async () => { vi.advanceTimersByTime(5000); });
      expect(screen.getByText("Thinking… 5s")).toBeDefined();

      await act(async () => { if (resolveStream) resolveStream(); });
    } finally {
      vi.useRealTimers();
    }
  });

  it("aborts and shows the retry error after 4 minutes without frames", async () => {
    vi.useFakeTimers();
    try {
      let resolveStream;
      let capturedSignal;
      streamChat.mockImplementation((question, callbacks, signal) => {
        capturedSignal = signal;
        return new Promise((resolve) => { resolveStream = resolve; });
      });

      renderChat();
      fireEvent.click(screen.getByLabelText(/open concierge/i));

      const input = screen.getByLabelText(/type your message/i);
      fireEvent.change(input, { target: { value: "hello" } });
      fireEvent.keyDown(input, { key: "Enter" });

      await act(async () => { vi.advanceTimersByTime(4 * 60 * 1000); });

      expect(capturedSignal.aborted).toBe(true);
      expect(screen.getByText(/taking too long to respond/i)).toBeDefined();
      expect(screen.getByRole("button", { name: /try again/i })).toBeDefined();

      await act(async () => { if (resolveStream) resolveStream(); });
    } finally {
      vi.useRealTimers();
    }
  });

  it("starts a new conversation from the header", async () => {
    streamChat.mockImplementation(async (question, callbacks) => {
      callbacks.onToken("Hello there");
      callbacks.onDone({ done: true, thread_id: "t1" });
    });

    renderChat();
    fireEvent.click(screen.getByLabelText(/open concierge/i));

    const input = screen.getByLabelText(/type your message/i);
    fireEvent.change(input, { target: { value: "hi" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText(/Hello there/i)).toBeDefined();
    });

    fireEvent.click(screen.getByLabelText(/start a new conversation/i));

    expect(screen.queryByText(/Hello there/i)).toBeNull();
    expect(clearThreadId).toHaveBeenCalled();
    expect(newThreadId).toHaveBeenCalled();
  });
});