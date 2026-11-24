/**
 * AI Agent API service for the EFP concierge.
 *
 * Manages two browser-backed identifiers:
 *   - efp_guest_id: stable anonymous UUID in localStorage (persists across
 *     visits → long-term guest memory)
 *   - efp_thread_id: per-conversation UUID in sessionStorage. It resets when
 *     the tab closes, together with the visible messages in sessionStorage,
 *     so a new browser session never silently continues an old thread.
 *
 * The old localStorage thread id is intentionally ignored. Only the guest id
 * is shared between tabs/visits; the conversation itself is not.
 *
 * If efp_guest_id is empty, memory_retrieve/memory_store no-op on the backend,
 * so this MUST always send a non-empty guest_identifier.
 */

const GUEST_ID_KEY = "efp_guest_id";
const THREAD_ID_KEY = "efp_thread_id";

/**
 * Generate a UUID v4 (RFC 4122).
 * @returns {string} A UUID string.
 */
function generateUUID() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older browsers.
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Get the stable guest identifier from localStorage, creating one if absent.
 * @returns {string} UUID string.
 */
export function getGuestId() {
  let id = localStorage.getItem(GUEST_ID_KEY);
  if (!id) {
    id = generateUUID();
    localStorage.setItem(GUEST_ID_KEY, id);
  }
  return id;
}

/**
 * Get the current thread ID from sessionStorage.
 * @returns {string} UUID string or empty if no active conversation.
 */
export function getThreadId() {
  return sessionStorage.getItem(THREAD_ID_KEY) || "";
}

/**
 * Start a new conversation — generates a fresh thread ID for this tab.
 * @returns {string} The new thread ID.
 */
export function newThreadId() {
  const id = generateUUID();
  sessionStorage.setItem(THREAD_ID_KEY, id);
  return id;
}

/**
 * Clear the current thread ID (e.g., "New conversation" or retry).
 */
export function clearThreadId() {
  sessionStorage.removeItem(THREAD_ID_KEY);
}

/**
 * Resume a paused graph after a HITL booking confirmation interrupt.
 * Non-streaming version — returns the full result.
 * @param {string} threadId - The thread ID of the paused conversation.
 * @param {boolean} confirmed - Whether the user confirmed the booking.
 * @returns {Promise<object>} The agent's response after resuming.
 */
export async function resumeBooking(threadId, confirmed) {
  const response = await fetch("/api/ai/resume", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      thread_id: threadId,
      confirmed,
    }),
  });
  if (!response.ok) {
    throw new Error(`Resume returned HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Resume a paused graph via the streaming endpoint.
 * @param {string} threadId - The thread ID of the paused conversation.
 * @param {boolean} confirmed - Whether the user confirmed the booking.
 * @param {object} callbacks - SSE event callbacks (same as streamChat).
 * @param {AbortSignal} [signal] - AbortController signal.
 * @returns {Promise<void>}
 */
export async function streamResume(threadId, confirmed, callbacks, signal) {
  const { streamAgent } = await import("../utils/sseParser");
  return streamAgent(
    "/api/ai/resume/stream",
    {
      thread_id: threadId,
      confirmed,
    },
    callbacks,
    signal,
  );
}

/**
 * Send a non-streaming chat request to the agent.
 * @param {string} question - The guest's question.
 * @returns {Promise<object>} The agent's response.
 */
export async function sendChat(question) {
  const response = await fetch("/api/ai/graph", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      guest_identifier: getGuestId(),
      thread_id: getThreadId(),
    }),
  });
  if (!response.ok) {
    throw new Error(`Agent returned HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Send a streaming chat request to the agent.
 * Returns the streamAgent function from sseParser, pre-configured with
 * the guest_id and thread_id.
 *
 * @param {string} question - The guest's question.
 * @param {object} callbacks - SSE event callbacks (see sseParser.streamAgent).
 * @param {AbortSignal} [signal] - AbortController signal for cancellation.
 * @returns {Promise<void>}
 */
export async function streamChat(question, callbacks, signal) {
  const { streamAgent } = await import("../utils/sseParser");
  return streamAgent(
    "/api/ai/graph/stream",
    {
      question,
      guest_identifier: getGuestId(),
      thread_id: getThreadId(),
    },
    callbacks,
    signal,
  );
}