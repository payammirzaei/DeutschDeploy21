import "fake-indexeddb/auto";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  flushLearningAttemptOutbox,
  getPendingAttemptCount,
  submitLearningAttemptSafely,
} from "./offline-attempts";

const DB_NAME = "dd21-offline";

async function deleteDatabase(): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const request = indexedDB.deleteDatabase(DB_NAME);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error ?? new Error("Could not reset IndexedDB"));
    request.onblocked = () => reject(new Error("IndexedDB reset was blocked"));
  });
}

describe("offline learning attempt outbox", () => {
  beforeEach(async () => {
    vi.unstubAllGlobals();
    await deleteDatabase();
  });

  afterEach(async () => {
    vi.unstubAllGlobals();
    await deleteDatabase();
  });

  it("replays a queued attempt with the original idempotency key", async () => {
    const idempotencyKeys: string[] = [];
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementationOnce(async (_input, init) => {
        const key = new Headers(init?.headers).get("Idempotency-Key");
        expect(key).toBeTruthy();
        idempotencyKeys.push(key as string);
        throw new TypeError("simulated network interruption");
      })
      .mockImplementationOnce(async (_input, init) => {
        const key = new Headers(init?.headers).get("Idempotency-Key");
        expect(key).toBeTruthy();
        idempotencyKeys.push(key as string);
        return new Response(
          JSON.stringify({ attempt_id: "attempt-1", evaluation_id: "evaluation-1" }),
          {
            status: 200,
            headers: { "content-type": "application/json" },
          },
        );
      });

    vi.stubGlobal("navigator", { onLine: true });
    vi.stubGlobal("fetch", fetchMock);

    const initial = await submitLearningAttemptSafely(
      "instance-1",
      { text: "Ich lerne Deutsch.", duration_ms: 900 },
    );

    expect(initial).toEqual({ status: "queued" });
    expect(await getPendingAttemptCount()).toBe(1);

    const flushed = await flushLearningAttemptOutbox();

    expect(flushed).toEqual({ synced: 1, remaining: 0 });
    expect(idempotencyKeys).toHaveLength(2);
    expect(idempotencyKeys[0]).toBe(idempotencyKeys[1]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("retries an existing queued attempt on the next submit", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementationOnce(async () => {
        throw new TypeError("offline");
      })
      .mockImplementationOnce(async () => {
        return new Response(
          JSON.stringify({ attempt_id: "attempt-2", correct: true, score: 100 }),
          {
            status: 200,
            headers: { "content-type": "application/json" },
          },
        );
      });

    vi.stubGlobal("navigator", { onLine: true });
    vi.stubGlobal("fetch", fetchMock);

    const first = await submitLearningAttemptSafely("instance-2", { text: "nutzen" });
    expect(first).toEqual({ status: "queued" });

    const second = await submitLearningAttemptSafely("instance-2", { text: "nutzen" });
    expect(second).toEqual({
      status: "submitted",
      data: { attempt_id: "attempt-2", correct: true, score: 100 },
    });
    expect(await getPendingAttemptCount()).toBe(0);
  });

  it("creates an idempotency key when crypto.randomUUID is unavailable", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ attempt_id: "attempt-3", correct: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    vi.stubGlobal("navigator", { onLine: true });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", {
      getRandomValues: (bytes: Uint8Array) => {
        for (let i = 0; i < bytes.length; i += 1) bytes[i] = (i * 17 + 3) % 256;
        return bytes;
      },
    });

    const { createIdempotencyKey } = await import("./offline-attempts");

    expect(createIdempotencyKey()).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );

    const result = await submitLearningAttemptSafely("instance-3", { text: "nutzen" });
    expect(result.status).toBe("submitted");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const key = new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("Idempotency-Key");
    expect(key).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
  });
});
