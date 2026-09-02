"use client";

import { useCallback, useEffect, useState } from "react";

import {
  flushLearningAttemptOutbox,
  getPendingAttemptCount,
  OUTBOX_CHANGED_EVENT,
} from "@/src/lib/offline-attempts";

import styles from "./offline-attempt-sync.module.css";

export function OfflineAttemptSync() {
  const [pending, setPending] = useState(0);
  const [syncing, setSyncing] = useState(false);

  const refresh = useCallback(async () => {
    setPending(await getPendingAttemptCount());
  }, []);

  const sync = useCallback(async () => {
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      await refresh();
      return;
    }
    setSyncing(true);
    const status = await flushLearningAttemptOutbox();
    setPending(status.remaining);
    setSyncing(false);
  }, [refresh]);

  useEffect(() => {
    const onOnline = () => void sync();
    const onOutboxChanged = () => void refresh();

    window.addEventListener("online", onOnline);
    window.addEventListener(OUTBOX_CHANGED_EVENT, onOutboxChanged);
    void refresh().then(() => {
      if (navigator.onLine) void sync();
    });

    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener(OUTBOX_CHANGED_EVENT, onOutboxChanged);
    };
  }, [refresh, sync]);

  if (!pending) return null;

  return (
    <div className={styles.banner} role="status" aria-live="polite">
      <strong>{syncing ? "Syncing saved answer…" : "Answer saved offline"}</strong>
      <span>
        {pending} {pending === 1 ? "attempt is" : "attempts are"} safe on this device and will sync
        automatically when the connection is available.
      </span>
    </div>
  );
}
