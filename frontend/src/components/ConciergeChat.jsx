/**
 * ConciergeChat — floating AI concierge chat widget for EFP.
 *
 * Features:
 * - Floating button (bottom-right), opens a slide-in chat panel
 * - SSE streaming via streamChat (token-by-token answer rendering)
 * - Tool-call status badges ("Checking availability...", etc.)
 * - Escalation notice (distinct visual for "our team will follow up")
 * - Booking confirmation card (reservation number, room, date/time)
 * - Graceful degradation (503 → "concierge unavailable" + link to reservations)
 * - Multi-turn continuity (thread_id in sessionStorage, resets with the tab)
 * - "New conversation" button clears visible messages and starts a new thread
 * - Long-term memory (guest_id in localStorage)
 * - Live status line while the agent works (with elapsed seconds)
 * - Accessibility: aria-label, aria-live status, Escape to close, focus management
 * - Mobile: panel expands to near-fullscreen on small screens
 * - AbortController: cancels stream on unmount/navigate/close, plus a
 *   4-minute no-frame watchdog that surfaces the retry state
 */
import React, { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link } from "react-router-dom";
import { streamChat, getGuestId, getThreadId, newThreadId, clearThreadId,
  streamResume } from "../services/ai_api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// If no SSE frame arrives for this long, abort and show the retry state.
const STREAM_INACTIVITY_TIMEOUT_MS = 4 * 60 * 1000;
// Append elapsed seconds to the status after this many seconds.
const STATUS_ELAPSED_AFTER_SECONDS = 5;

// Tool name → human-readable status label.
const TOOL_LABELS = {
  get_locations: "Looking up our locations...",
  check_availability: "Checking availability...",
  create_reservation: "Preparing your reservation...",
};

// Map tool names to shorter labels for status badges.
function toolStatusLabel(name) {
  return TOOL_LABELS[name] || `Working on it...`;
}

export default function ConciergeChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState(() => {
    // Restore chat history from sessionStorage on mount.
    try {
      const saved = sessionStorage.getItem("efp_chat_messages");
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [toolStatus, setToolStatus] = useState(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [error, setError] = useState(null);
  const [hasError, setHasError] = useState(false);
  const [threadStarted, setThreadStarted] = useState(() => !!getThreadId());
  const [pendingConfirmation, setPendingConfirmation] = useState(null);
  const [isResuming, setIsResuming] = useState(false);

  const abortRef = useRef(null);
  const watchdogRef = useRef(null);
  const inputRef = useRef(null);
  const scrollRef = useRef(null);

  // Count elapsed seconds so a long wait never looks frozen. The status line
  // appends the count after 5 seconds.
  useEffect(() => {
    if (!isStreaming) return undefined;
    const id = setInterval(() => setElapsedSeconds((seconds) => seconds + 1), 1000);
    return () => clearInterval(id);
  }, [isStreaming]);

  // Persist messages to sessionStorage whenever they change.
  useEffect(() => {
    try {
      sessionStorage.setItem("efp_chat_messages", JSON.stringify(messages));
    } catch { /* sessionStorage may be full or unavailable */ }
  }, [messages]);

  // Auto-scroll to bottom on new messages / streaming text.
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingText, toolStatus]);

  // Focus input when panel opens.
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Cancel any in-flight stream and watchdog on unmount.
  useEffect(() => {
    return () => {
      if (abortRef.current) {
        abortRef.current.abort();
      }
      if (watchdogRef.current) {
        clearTimeout(watchdogRef.current);
      }
    };
  }, []);

  // Escape to close.
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => {
      if (e.key === "Escape") setIsOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen]);

  const handleSend = useCallback(async () => {
    const question = input.trim();
    if (!question || isStreaming || hasError || pendingConfirmation) return;

    // Ensure we have a thread_id for this chat session.
    let currentThreadId = getThreadId();
    if (!threadStarted || !currentThreadId) {
      currentThreadId = newThreadId();
      setThreadStarted(true);
    }

    // Add the guest's message to the chat.
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setInput("");
    setIsStreaming(true);
    setStreamingText("");
    setToolStatus("Sending…");
    setElapsedSeconds(0);
    setError(null);

    // Set up AbortController for this request.
    const controller = new AbortController();
    abortRef.current = controller;

    // Reset the 4-minute inactivity watchdog on every SSE frame.
    const armWatchdog = () => {
      if (watchdogRef.current) clearTimeout(watchdogRef.current);
      watchdogRef.current = setTimeout(() => {
        controller.abort();
        setIsStreaming(false);
        setStreamingText("");
        setToolStatus(null);
        setElapsedSeconds(0);
        setError("The concierge is taking too long to respond. Please try again.");
        setHasError(true);
      }, STREAM_INACTIVITY_TIMEOUT_MS);
    };
    armWatchdog();

    let fullAnswer = "";
    let toolResults = [];

    try {
      await streamChat(
        question,
        {
          onNode: (node) => {
            armWatchdog();
            if (node === "agent") {
              setToolStatus("Writing the reply…");
            } else if ([
              "memory_retrieve", "triage", "rag", "summarize", "tools",
              "escalation", "memory_store",
            ].includes(node)) {
              setToolStatus("Thinking…");
            }
          },
          onToken: (token) => {
            armWatchdog();
            fullAnswer += token;
            setStreamingText(fullAnswer);
          },
          onToolCall: (call) => {
            armWatchdog();
            setToolStatus(toolStatusLabel(call.name));
          },
          onToolResult: (result) => {
            armWatchdog();
            toolResults.push(result);
            setToolStatus("Thinking…");
          },
          onEscalation: (reason) => {
            armWatchdog();
            setMessages((prev) => [
              ...prev,
              { role: "assistant", type: "escalation", text: reason },
            ]);
          },
          onDone: (data) => {
            armWatchdog();
            if (data.interrupted && data.interrupt_data) {
              // HITL interrupt — show confirmation card.
              setPendingConfirmation({
                threadId: data.thread_id,
                details: data.interrupt_data.details || {},
                message: data.interrupt_data.message || "Please confirm your booking.",
              });
            } else {
              // Normal completion — finalize the assistant message.
              if (fullAnswer) {
                setMessages((prev) => [...prev, { role: "assistant", text: fullAnswer }]);
              }
              for (const tr of toolResults) {
                if (tr.name === "create_reservation" && tr.result?.success) {
                  setMessages((prev) => [...prev, { role: "assistant", type: "confirmation", data: tr.result }]);
                }
                if (tr.result?.requires_call) {
                  setMessages((prev) => [...prev, { role: "assistant", type: "escalation", text: tr.result.error }]);
                }
              }
            }
            setStreamingText("");
            setToolStatus(null);
          },
          onError: (errMsg) => {
            armWatchdog();
            setError(errMsg);
            setHasError(true);
          },
        },
        controller.signal,
      );
    } catch {
      // Errors handled by onError callback.
    } finally {
      if (watchdogRef.current) {
        clearTimeout(watchdogRef.current);
        watchdogRef.current = null;
      }
      setIsStreaming(false);
      setStreamingText("");
      setToolStatus(null);
      setElapsedSeconds(0);
      abortRef.current = null;
    }
  }, [input, isStreaming, hasError, threadStarted, pendingConfirmation]);

  const handleConfirmBooking = useCallback(async () => {
    if (!pendingConfirmation) return;
    setIsResuming(true);
    setStreamingText("");
    setToolStatus("Confirming your reservation...");
    let fullAnswer = "";
    let toolResults = [];
    try {
      await streamResume(
        pendingConfirmation.threadId,
        true,
        {
          onNode: () => {},
          onToken: (token) => {
            fullAnswer += token;
            setStreamingText(fullAnswer);
          },
          onToolCall: (call) => {
            setToolStatus(toolStatusLabel(call.name));
          },
          onToolResult: (result) => {
            toolResults.push(result);
            setToolStatus(null);
          },
          onEscalation: (reason) => {
            setMessages((prev) => [...prev, { role: "assistant", type: "escalation", text: reason }]);
          },
          onDone: (data) => {
            if (data && data.interrupted && data.interrupt_data) {
              // Re-interrupt during resume — show a new confirmation card.
              setPendingConfirmation({
                threadId: data.thread_id || pendingConfirmation.threadId,
                details: data.interrupt_data.details || {},
                message: data.interrupt_data.message || "Please confirm your booking.",
              });
              return;
            }
            if (fullAnswer) {
              setMessages((prev) => [...prev, { role: "assistant", text: fullAnswer }]);
            }
            for (const tr of toolResults) {
              if (tr.name === "create_reservation" && tr.result?.success) {
                setMessages((prev) => [...prev, { role: "assistant", type: "confirmation", data: tr.result }]);
              }
              if (tr.result?.requires_call) {
                setMessages((prev) => [...prev, { role: "assistant", type: "escalation", text: tr.result.error }]);
              }
            }
            setStreamingText("");
            setToolStatus(null);
          },
          onError: (errMsg) => {
            setMessages((prev) => [...prev, { role: "assistant", text: errMsg }]);
          },
        },
      );
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", text: "I couldn't complete the booking. Please try again." }]);
    } finally {
      setPendingConfirmation(null);
      setIsResuming(false);
      setStreamingText("");
      setToolStatus(null);
    }
  }, [pendingConfirmation]);

  const handleCancelBooking = useCallback(async () => {
    if (!pendingConfirmation) return;
    setIsResuming(true);
    try {
      await streamResume(pendingConfirmation.threadId, false, {
        onNode: () => {},
        onToken: () => {},
        onDone: () => {},
        onError: () => {},
      });
      setMessages((prev) => [...prev, { role: "assistant", text: "Your reservation request has been cancelled. Let me know if you'd like to try a different time or location." }]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", text: "The booking was cancelled." }]);
    } finally {
      setPendingConfirmation(null);
      setIsResuming(false);
    }
  }, [pendingConfirmation]);

  const handleNewConversation = useCallback(() => {
    if (abortRef.current) abortRef.current.abort();
    if (watchdogRef.current) {
      clearTimeout(watchdogRef.current);
      watchdogRef.current = null;
    }
    clearThreadId();
    newThreadId();
    setThreadStarted(true);
    setMessages([]);
    setInput("");
    setStreamingText("");
    setToolStatus(null);
    setElapsedSeconds(0);
    setError(null);
    setHasError(false);
    setPendingConfirmation(null);
    setIsStreaming(false);
    setIsResuming(false);
    try { sessionStorage.removeItem("efp_chat_messages"); } catch { /* ignore */ }
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleRetry = () => {
    setHasError(false);
    setError(null);
    setMessages([]);
    setStreamingText("");
    setThreadStarted(false);
    clearThreadId();
    try { sessionStorage.removeItem("efp_chat_messages"); } catch { /* ignore */ }
  };

  const toggleOpen = () => {
    setIsOpen((prev) => !prev);
  };

  const showStatus = !streamingText && (isStreaming || isResuming);
  const baseStatus = toolStatus || (isResuming ? "Confirming your reservation..." : "Thinking…");
  const statusText = elapsedSeconds >= STATUS_ELAPSED_AFTER_SECONDS
    ? `${baseStatus} ${elapsedSeconds}s`
    : baseStatus;

  return (
    <>
      {/* Floating button */}
      <motion.button
        onClick={toggleOpen}
        aria-label={isOpen ? "Close concierge chat" : "Open concierge chat"}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-icon-blue text-white shadow-lg hover:bg-golden-brown transition-colors duration-300 flex items-center justify-center"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        {isOpen ? (
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        ) : (
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        )}
      </motion.button>

      {/* Chat panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-24 right-6 z-50 w-[calc(100vw-3rem)] sm:w-96 h-[60vh] sm:h-[500px] bg-background rounded-lg shadow-2xl border border-border flex flex-col overflow-hidden"
            role="dialog"
            aria-label="EFP Concierge chat"
          >
            {/* Header */}
            <div className="bg-icon-blue text-white px-4 py-3 flex items-center justify-between flex-shrink-0">
              <div>
                <h3 className="font-semibold text-sm text-white">EFP Concierge</h3>
                <p className="text-xs text-white/80">Your culinary sanctuary guide</p>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={handleNewConversation}
                  aria-label="Start a new conversation"
                  className="text-xs text-white/80 hover:text-white transition-colors whitespace-nowrap"
                >
                  New conversation
                </button>
                <button
                  onClick={() => setIsOpen(false)}
                  aria-label="Close chat"
                  className="text-white/80 hover:text-white transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Messages area */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3 bg-card/30">
              {messages.length === 0 && !hasError && (
                <div className="text-center text-muted-foreground text-sm mt-8">
                  <p className="mb-2">Welcome to Eternal Fusion Pavilion.</p>
                  <p>Ask me about our menu, founders, locations, or reservations.</p>
                </div>
              )}

              {messages.map((msg, i) => (
                <MessageBubble key={i} msg={msg} />
              ))}

              {/* Status line — visible from send until answer text arrives. */}
              {showStatus && (
                <div
                  aria-live="polite"
                  className="flex items-center gap-2 text-xs text-muted-foreground"
                >
                  <span className="inline-block w-2 h-2 rounded-full bg-icon-blue animate-pulse" />
                  {statusText}
                </div>
              )}

              {/* Streaming text */}
              {streamingText && (
                <div className="bg-background rounded-lg p-3 text-sm text-foreground shadow-sm border border-border max-w-[85%]">
                  {streamingText}
                </div>
              )}

              {/* HITL booking confirmation card */}
              {pendingConfirmation && (
                <div className="bg-golden-brown/10 border border-golden-brown/40 rounded-lg p-3 text-sm max-w-[85%]">
                  <p className="font-semibold text-golden-brown mb-2">Booking Confirmation Required</p>
                  <p className="text-foreground whitespace-pre-wrap mb-3">{pendingConfirmation.message}</p>
                  <div className="flex gap-2">
                    <button
                      onClick={handleConfirmBooking}
                      disabled={isResuming}
                      aria-label="Confirm booking"
                      className="btn text-xs px-3 py-1.5"
                    >
                      {isResuming ? "Processing..." : "Confirm Booking"}
                    </button>
                    <button
                      onClick={handleCancelBooking}
                      disabled={isResuming}
                      aria-label="Cancel booking"
                      className="btn-outline text-xs px-3 py-1.5"
                    >
                      {isResuming ? "..." : "Cancel"}
                    </button>
                  </div>
                </div>
              )}

              {/* Error state */}
              {hasError && (
                <div className="text-center py-8 px-4">
                  <p className="text-muted-foreground text-sm mb-4">{error}</p>
                  <div className="flex flex-col gap-2 items-center">
                    <button onClick={handleRetry} className="btn text-sm">
                      Try Again
                    </button>
                    <Link to="/reservations" className="text-icon-blue text-sm hover:underline">
                      Go to Reservations
                    </Link>
                  </div>
                </div>
              )}
            </div>

            {/* Input area */}
            {!hasError && (
              <div className="flex-shrink-0 border-t border-border p-3 bg-background">
                <div className="flex gap-2">
                  <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask about our menu, hours, or book a table..."
                    disabled={isStreaming}
                    aria-label="Type your message"
                    className="flex-1 px-3 py-2 text-sm rounded-md border border-border bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-icon-blue disabled:opacity-50"
                  />
                  <button
                    onClick={handleSend}
                    disabled={!input.trim() || isStreaming}
                    aria-label="Send message"
                    className="btn text-sm px-3 py-2 min-w-[3rem]"
                  >
                    {isStreaming ? (
                      <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

/**
 * Message bubble — renders different styles based on role and type.
 */
function MessageBubble({ msg }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="bg-icon-blue text-white rounded-lg p-3 text-sm max-w-[85%] shadow-sm">
          {msg.text}
        </div>
      </div>
    );
  }

  // Escalation notice — distinct visual style.
  if (msg.type === "escalation") {
    return (
      <div className="flex justify-start">
        <div className="bg-golden-brown/10 border border-golden-brown/30 rounded-lg p-3 text-sm text-foreground max-w-[85%]">
          <div className="flex items-start gap-2">
            <svg className="w-5 h-5 text-golden-brown flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <p className="font-medium text-golden-brown mb-1">Our team will follow up with you</p>
              <p className="text-muted-foreground">{msg.text}</p>
              <p className="text-xs text-muted-foreground mt-2">
                Thank you for your patience. We'll reach out personally to assist.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Booking confirmation card.
  if (msg.type === "confirmation" && msg.data) {
    const d = msg.data;
    return (
      <div className="flex justify-start">
        <div className="bg-success-muted border border-success/30 rounded-lg p-3 text-sm max-w-[85%]">
          <div className="flex items-center gap-2 mb-2">
            <svg className="w-5 h-5 text-success flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="font-semibold text-success-muted-foreground">Reservation Confirmed</p>
          </div>
          {d.reservation_number && (
            <p className="text-xs text-muted-foreground mb-1">
              Confirmation #: <span className="font-mono font-semibold text-foreground">{d.reservation_number}</span>
            </p>
          )}
          {d.room && (
            <p className="text-xs text-muted-foreground mb-1">
              Room: {d.room.name} ({d.room.code})
            </p>
          )}
          {d.message && <p className="text-xs text-foreground mt-2">{d.message}</p>}
        </div>
      </div>
    );
  }

  // Regular assistant message — render as markdown (bold, italic, lists, links).
  return (
    <div className="flex justify-start">
      <div className="bg-background rounded-lg p-3 text-sm text-foreground max-w-[85%] shadow-sm border border-border">
        <div className="chat-markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {msg.text}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}