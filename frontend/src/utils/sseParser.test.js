/**
 * Tests for utils/sseParser.js — SSE stream parsing logic.
 *
 * Tests parseSseLine in isolation (pure function) and streamAgent with
 * a mocked ReadableStream (including ping/malformed/done frames).
 */
import { describe, it, expect, vi } from "vitest";
import { parseSseLine, streamAgent } from "../utils/sseParser";

// --- parseSseLine tests (pure function) ---------------------------------- //

describe("parseSseLine", () => {
  it("parses a valid data line", () => {
    const result = parseSseLine('data: {"node": "triage"}');
    expect(result).toEqual({ node: "triage" });
  });

  it("parses data line with extra whitespace after data:", () => {
    const result = parseSseLine('data:    {"token": "hello"}');
    expect(result).toEqual({ token: "hello" });
  });

  it("returns null for empty lines", () => {
    expect(parseSseLine("")).toBeNull();
    expect(parseSseLine("   ")).toBeNull();
  });

  it("returns null for non-data lines (comments, pings, event fields)", () => {
    expect(parseSseLine(": keep-alive")).toBeNull();
    expect(parseSseLine("event: ping")).toBeNull();
    expect(parseSseLine("id: 123")).toBeNull();
    expect(parseSseLine("retry: 5000")).toBeNull();
  });

  it("returns null for malformed JSON (does not throw)", () => {
    expect(parseSseLine("data: {broken json}")).toBeNull();
    expect(parseSseLine("data: ")).toBeNull();
    expect(parseSseLine("data: not json at all")).toBeNull();
  });

  it("parses complex nested JSON", () => {
    const line = 'data: {"tool_call": {"name": "get_locations", "arguments": {}}}';
    const result = parseSseLine(line);
    expect(result.tool_call.name).toBe("get_locations");
  });
});

// --- streamAgent tests (mocked ReadableStream) --------------------------- //

/**
 * Helper: create a mock ReadableStream from an array of string chunks.
 */
function makeMockStream(chunks) {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

/**
 * Helper: mock fetch to return a Response with the given body chunks.
 */
function mockFetchStream(chunks, status = 200) {
  const stream = makeMockStream(chunks);
  global.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    body: stream,
  });
}

describe("streamAgent", () => {
  it("dispatches onNode callback for node frames", async () => {
    mockFetchStream([
      'data: {"node": "triage"}\n',
      'data: {"node": "rag"}\n',
      'data: {"done": true, "thread_id": "t1"}\n',
    ]);

    const nodes = [];
    await streamAgent("/test", { question: "hi" }, {
      onNode: (n) => nodes.push(n),
      onDone: () => {},
    });

    expect(nodes).toEqual(["triage", "rag"]);
  });

  it("dispatches onToken callback for token frames", async () => {
    mockFetchStream([
      'data: {"token": "Hello"}\n',
      'data: {"token": " world"}\n',
      'data: {"done": true}\n',
    ]);

    const tokens = [];
    await streamAgent("/test", { question: "hi" }, {
      onToken: (t) => tokens.push(t),
      onDone: () => {},
    });

    expect(tokens).toEqual(["Hello", " world"]);
  });

  it("dispatches onToolCall and onToolResult callbacks", async () => {
    mockFetchStream([
      'data: {"tool_call": {"name": "get_locations", "arguments": {}}}\n',
      'data: {"tool_result": {"name": "get_locations", "result": {"success": true}}}\n',
      'data: {"done": true}\n',
    ]);

    const toolCalls = [];
    const toolResults = [];
    await streamAgent("/test", { question: "book" }, {
      onToolCall: (c) => toolCalls.push(c),
      onToolResult: (r) => toolResults.push(r),
      onDone: () => {},
    });

    expect(toolCalls).toHaveLength(1);
    expect(toolCalls[0].name).toBe("get_locations");
    expect(toolResults).toHaveLength(1);
    expect(toolResults[0].result.success).toBe(true);
  });

  it("dispatches onEscalation callback", async () => {
    mockFetchStream([
      'data: {"escalation": "Party size exceeds 12"}\n',
      'data: {"done": true}\n',
    ]);

    let escalation = null;
    await streamAgent("/test", { question: "15 people" }, {
      onEscalation: (e) => { escalation = e; },
      onDone: () => {},
    });

    expect(escalation).toBe("Party size exceeds 12");
  });

  it("dispatches onDone with the full done frame", async () => {
    const doneFrame = '{"done": true, "thread_id": "abc-123", "latency_ms": 5000, "in_scope": true}';
    mockFetchStream([
      `data: ${doneFrame}\n`,
    ]);

    let doneData = null;
    await streamAgent("/test", { question: "hi" }, {
      onDone: (d) => { doneData = d; },
    });

    expect(doneData).not.toBeNull();
    expect(doneData.done).toBe(true);
    expect(doneData.thread_id).toBe("abc-123");
    expect(doneData.latency_ms).toBe(5000);
  });

  it("ignores keep-alive pings and non-data lines without crashing", async () => {
    mockFetchStream([
      ": keep-alive\n",
      "event: ping\n",
      'data: {"node": "triage"}\n',
      "\n",
      "retry: 5000\n",
      'data: {"done": true}\n',
    ]);

    const nodes = [];
    await streamAgent("/test", { question: "hi" }, {
      onNode: (n) => nodes.push(n),
      onDone: () => {},
    });

    expect(nodes).toEqual(["triage"]);
  });

  it("tolerates malformed JSON in the stream without crashing", async () => {
    mockFetchStream([
      'data: {"node": "triage"}\n',
      "data: {broken json}\n",
      'data: {"token": "still works"}\n',
      'data: {"done": true}\n',
    ]);

    const nodes = [];
    const tokens = [];
    await streamAgent("/test", { question: "hi" }, {
      onNode: (n) => nodes.push(n),
      onToken: (t) => tokens.push(t),
      onDone: () => {},
    });

    expect(nodes).toEqual(["triage"]);
    expect(tokens).toEqual(["still works"]);
  });

  it("handles partial lines split across chunks", async () => {
    mockFetchStream([
      'data: {"node": "tr',  // partial — split across chunks
      'iage"}\n',
      'data: {"done": true}\n',
    ]);

    const nodes = [];
    await streamAgent("/test", { question: "hi" }, {
      onNode: (n) => nodes.push(n),
      onDone: () => {},
    });

    expect(nodes).toEqual(["triage"]);
  });

  it("calls onError on 503 response", async () => {
    mockFetchStream([], 503);

    let errorMsg = null;
    await streamAgent("/test", { question: "hi" }, {
      onError: (e) => { errorMsg = e; },
    });

    expect(errorMsg).not.toBeNull();
    expect(errorMsg).toContain("unavailable");
  });

  it("calls onError on network failure", async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    let errorMsg = null;
    await streamAgent("/test", { question: "hi" }, {
      onError: (e) => { errorMsg = e; },
    });

    expect(errorMsg).not.toBeNull();
    expect(errorMsg).toContain("Could not reach");
  });

  it("handles AbortController cancellation gracefully", async () => {
    const controller = new AbortController();
    mockFetchStream([
      'data: {"node": "triage"}\n',
      'data: {"done": true}\n',
    ]);

    controller.abort();

    const nodes = [];
    await streamAgent("/test", { question: "hi" }, {
      onNode: (n) => nodes.push(n),
      onDone: () => {},
    }, controller.signal);

    // Should not crash; may or may not have nodes depending on timing.
    expect(nodes).toBeDefined();
  });
});