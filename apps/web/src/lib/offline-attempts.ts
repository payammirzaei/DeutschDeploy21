const DB_NAME = "dd21-offline";
const DB_VERSION = 1;
const STORE_NAME = "learning-attempts";

export const ATTEMPT_SYNCED_EVENT = "dd21:attempt-synced";
export const OUTBOX_CHANGED_EVENT = "dd21:outbox-changed";

type AttemptBody = Record<string, unknown>;

type QueuedAttempt = {
  url: string;
  idempotencyKey: string;
  body: AttemptBody;
  createdAt: number;
};

export type AttemptSyncDetail<T = unknown> = {
  url: string;
  data: T;
};

export type SafeAttemptResult<T> =
  | { status: "submitted"; data: T }
  | { status: "queued" }
  | { status: "error"; httpStatus: number | null };

export type OutboxStatus = {
  synced: number;
  remaining: number;
};

let activeFlush: Promise<OutboxStatus> | null = null;

export function learningAttemptUrl(instanceId: string): string {
  return `/api/v1/learning/instances/${encodeURIComponent(instanceId)}/attempts`;
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (!("indexedDB" in globalThis)) {
      reject(new Error("IndexedDB is unavailable"));
      return;
    }

    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME, { keyPath: "url" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("Could not open offline outbox"));
  });
}

async function getQueuedAttempt(url: string): Promise<QueuedAttempt | null> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, "readonly");
    const request = transaction.objectStore(STORE_NAME).get(url);
    request.onsuccess = () => resolve((request.result as QueuedAttempt | undefined) ?? null);
    request.onerror = () => reject(request.error ?? new Error("Could not read offline attempt"));
    transaction.oncomplete = () => database.close();
  });
}

async function listQueuedAttempts(): Promise<QueuedAttempt[]> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, "readonly");
    const request = transaction.objectStore(STORE_NAME).getAll();
    request.onsuccess = () => resolve((request.result as QueuedAttempt[]) ?? []);
    request.onerror = () => reject(request.error ?? new Error("Could not list offline attempts"));
    transaction.oncomplete = () => database.close();
  });
}

async function putQueuedAttempt(attempt: QueuedAttempt): Promise<void> {
  const database = await openDatabase();
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, "readwrite");
    transaction.objectStore(STORE_NAME).put(attempt);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error ?? new Error("Could not save offline attempt"));
    transaction.onabort = () => reject(transaction.error ?? new Error("Offline attempt save aborted"));
  });
  database.close();
  emitOutboxChanged();
}

async function deleteQueuedAttempt(url: string): Promise<void> {
  const database = await openDatabase();
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, "readwrite");
    transaction.objectStore(STORE_NAME).delete(url);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error ?? new Error("Could not clear offline attempt"));
    transaction.onabort = () => reject(transaction.error ?? new Error("Offline attempt clear aborted"));
  });
  database.close();
  emitOutboxChanged();
}

const ATTEMPT_TIMEOUT_MS = 15_000;

/**
 * Idempotency keys must work on plain HTTP LAN / Tailscale hosts.
 * `crypto.randomUUID()` is secure-context-only in many browsers, so those
 * origins throw before the attempt is ever sent.
 */
export function createIdempotencyKey(): string {
  const webCrypto = typeof globalThis.crypto !== "undefined" ? globalThis.crypto : undefined;
  if (webCrypto && typeof webCrypto.randomUUID === "function") {
    try {
      return webCrypto.randomUUID();
    } catch {
      // Non-secure contexts can expose the method but still reject.
    }
  }
  if (webCrypto && typeof webCrypto.getRandomValues === "function") {
    const bytes = new Uint8Array(16);
    webCrypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }
  return `local-${Date.now().toString(16)}-${Math.random().toString(16).slice(2, 10)}`;
}

function abortSignalWithTimeout(ms: number): AbortSignal {
  if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
    try {
      return AbortSignal.timeout(ms);
    } catch {
      // fall through
    }
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  // Avoid keeping the timer alive if the request finishes early in Node tests.
  const signal = controller.signal;
  signal.addEventListener(
    "abort",
    () => {
      clearTimeout(timer);
    },
    { once: true },
  );
  return signal;
}

async function sendAttempt<T>(attempt: QueuedAttempt): Promise<{ response: Response; data: T | null }> {
  const response = await fetch(attempt.url, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": attempt.idempotencyKey,
    },
    body: JSON.stringify(attempt.body),
    signal: abortSignalWithTimeout(ATTEMPT_TIMEOUT_MS),
  });
  const contentType = response.headers.get("content-type") ?? "";
  const data = contentType.includes("application/json") ? ((await response.json()) as T) : null;
  return { response, data };
}

function emitOutboxChanged(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(OUTBOX_CHANGED_EVENT));
  }
}

function emitAttemptSynced<T>(url: string, data: T): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent<AttemptSyncDetail<T>>(ATTEMPT_SYNCED_EVENT, { detail: { url, data } }),
    );
  }
}

export async function getPendingAttemptCount(): Promise<number> {
  try {
    return (await listQueuedAttempts()).length;
  } catch {
    return 0;
  }
}

export async function submitLearningAttemptSafely<T>(
  instanceId: string,
  body: AttemptBody,
): Promise<SafeAttemptResult<T>> {
  try {
    return await submitLearningAttemptSafelyInner<T>(instanceId, body);
  } catch {
    // Never throw into the learning UI — surface a retryable error state.
    return { status: "error", httpStatus: null };
  }
}

async function submitLearningAttemptSafelyInner<T>(
  instanceId: string,
  body: AttemptBody,
): Promise<SafeAttemptResult<T>> {
  const url = learningAttemptUrl(instanceId);

  let existing: QueuedAttempt | null = null;
  try {
    existing = await getQueuedAttempt(url);
  } catch {
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      return { status: "error", httpStatus: null };
    }
  }

  // A previously queued answer for this instance must be retried with the
  // original idempotency key — never leave the UI stuck on "Saving…".
  if (existing) {
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      return { status: "queued" };
    }
    try {
      const { response, data } = await sendAttempt<T>(existing);
      if (response.ok && data !== null) {
        await deleteQueuedAttempt(url);
        return { status: "submitted", data };
      }
      if (response.status === 401) {
        return { status: "error", httpStatus: 401 };
      }
      return { status: "queued" };
    } catch {
      return { status: "queued" };
    }
  }

  const attempt: QueuedAttempt = {
    url,
    idempotencyKey: createIdempotencyKey(),
    body,
    createdAt: Date.now(),
  };

  if (typeof navigator !== "undefined" && !navigator.onLine) {
    try {
      await putQueuedAttempt(attempt);
      return { status: "queued" };
    } catch {
      return { status: "error", httpStatus: null };
    }
  }

  try {
    const { response, data } = await sendAttempt<T>(attempt);
    if (!response.ok || data === null) {
      return { status: "error", httpStatus: response.status };
    }
    return { status: "submitted", data };
  } catch {
    try {
      await putQueuedAttempt(attempt);
      return { status: "queued" };
    } catch {
      return { status: "error", httpStatus: null };
    }
  }
}

async function flushNow(): Promise<OutboxStatus> {
  let synced = 0;
  let queued: QueuedAttempt[];
  try {
    queued = await listQueuedAttempts();
  } catch {
    return { synced: 0, remaining: 0 };
  }

  for (const attempt of queued.sort((a, b) => a.createdAt - b.createdAt)) {
    try {
      const { response, data } = await sendAttempt(attempt);
      if (response.status === 401) break;
      if (!response.ok || data === null) continue;
      await deleteQueuedAttempt(attempt.url);
      synced += 1;
      emitAttemptSynced(attempt.url, data);
    } catch {
      break;
    }
  }

  return { synced, remaining: await getPendingAttemptCount() };
}

export function flushLearningAttemptOutbox(): Promise<OutboxStatus> {
  if (activeFlush) return activeFlush;
  activeFlush = flushNow().finally(() => {
    activeFlush = null;
  });
  return activeFlush;
}
