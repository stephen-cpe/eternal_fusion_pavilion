/**
 * SSE stream parser for the EFP AI agent.
 *
 * Reads a fetch() ReadableStream, parses "data: {...}" lines into JS
 * objects, and invokes callbacks for each event. Handles:
 * - Keep-alive pings (ignored)
 * - Non-"data:" lines (ignored)
 * - Malformed JSON (logged + skipped, stream continues)
 * - AbortController for cancellation
 *
 * Usage:
 *   import { streamAgent } from "../utils/sseParser";
 *   const controller = new AbortController();
 *   await streamAgent("/api/ai/graph/stream", body, {
 *     onNode: (node) => ...,
 *     onToken: (token) => ...,
 *     onToolCall: (call) => ...,
 *     onToolResult: (result) => ...,
 *     onDone: (final) => ...,
 *     onError: (err) => ...,
 *   }, controller.signal);
 */

/**
 * Parse a single SSE line into a data object, or null if not a data line.
 * @param {string} line - A single line from the SSE stream.
 * @returns {object|null} Parsed JSON object, or null if not a data line / malformed.
 */
export function parseSseLine(line) {
  // Skip empty lines (event boundaries).
  if (!line || line.trim() === "") return null;
  // Skip non-data lines (comments, keep-alive pings, event/id fields).
  if (!line.startsWith("data:")) return null;
  // Extract the payload after "data:".
  const payload = line.slice(5).trim();
  if (!payload) return null;
  // Parse JSON; tolerate malformed without crashing.
  try {
    return JSON.parse(payload);
  } catch {
    // Malformed JSON — skip silently, stream continues.
    return null;
  }
}

/**
 * Stream the agent endpoint and dispatch events via callbacks.
 *
 * @param {string} url - The endpoint URL (e.g., "/api/ai/graph/stream").
 * @param {object} body - Request body {question, guest_identifier, thread_id}.
 * @param {object} callbacks - Event callbacks.
 * @param {function} [callbacks.onNode] - Called with node name string.
 * @param {function} [callbacks.onToken] - Called with token string.
 * @param {function} [callbacks.onToolCall] - Called with {name, arguments}.
 * @param {function} [callbacks.onToolResult] - Called with {name, arguments, result}.
 * @param {function} [callbacks.onEscalation] - Called with reason string.
 * @param {function} [callbacks.onMemories] - Called with memories array.
 * @param {function} [callbacks.onStoredMemories] - Called with stored memories array.
 * @param {function} [callbacks.onDone] - Called with the final done frame object.
 * @param {function} [callbacks.onError] - Called with error string.
 * @param {AbortSignal} [signal] - AbortController signal for cancellation.
 * @returns {Promise<void>}
 */
export async function streamAgent(url, body, callbacks, signal) {
  const {
    onNode,
    onToken,
    onToolCall,
    onToolResult,
    onEscalation,
    onMemories,
    onStoredMemories,
    onDone,
    onError,
  } = callbacks;

  let response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (err.name === "AbortError") return;
    if (onError) onError("Could not reach the concierge service.");
    return;
  }

  if (!response.ok) {
    if (response.status === 503) {
      if (onError) onError("The concierge is momentarily unavailable. You can still book via our reservations page.");
    } else {
      if (onError) onError(`The concierge returned an error (HTTP ${response.status}).`);
    }
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process complete lines (terminated by \n).
      const lines = buffer.split("\n");
      // Keep the last (possibly incomplete) line in the buffer.
      buffer = lines.pop() || "";

      for (const line of lines) {
        const data = parseSseLine(line);
        if (!data) continue;

        // Dispatch based on frame type.
        if (data.node && onNode) {
          onNode(data.node);
        }
        if (data.token && onToken) {
          onToken(data.token);
        }
        if (data.tool_call && onToolCall) {
          onToolCall(data.tool_call);
        }
        if (data.tool_result && onToolResult) {
          onToolResult(data.tool_result);
        }
        if (data.escalation && onEscalation) {
          onEscalation(data.escalation);
        }
        if (data.memories && onMemories) {
          onMemories(data.memories);
        }
        if (data.stored_memories && onStoredMemories) {
          onStoredMemories(data.stored_memories);
        }
        if (data.done && onDone) {
          onDone(data);
        }
        if (data.error && onError) {
          onError(data.error);
        }
      }
    }
  } catch (err) {
    if (err.name === "AbortError") return;
    if (onError) onError("The stream was interrupted. Please try again.");
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // already released
    }
  }
}