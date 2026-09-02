"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { api } from "@/src/lib/api";

import styles from "./catalog.module.css";

type Example = {
  external_id: string;
  de: string;
  fa: string | null;
  en: string | null;
  skill: string | null;
};

type Verb = {
  item_id: string;
  external_id: string;
  version_id: string;
  version_number: number;
  lemma: string;
  infinitive: string;
  perfect_auxiliary: string;
  participle_ii: string;
  preterite: string | null;
  separable: boolean;
  separable_prefix: string | null;
  reflexive: boolean;
  regularity: string;
  cefr: string;
  register: string;
  translations: Record<string, string[]>;
  examples: Example[];
};

export default function CatalogPage() {
  const router = useRouter();
  const [verbs, setVerbs] = useState<Verb[]>([]);
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("all");
  const [loading, setLoading] = useState(true);
  const [installing, setInstalling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const { data, response } = await api.GET("/api/v1/content/verbs");
    if (response.status === 401) {
      router.replace("/login");
      return;
    }
    if (!response.ok) {
      setError("Catalog could not be loaded.");
      return;
    }
    setVerbs((data ?? []) as Verb[]);
    setError(null);
  }

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const { data, response } = await api.GET("/api/v1/content/verbs");
      if (cancelled) return;
      if (response.status === 401) {
        router.replace("/login");
        return;
      }
      if (!response.ok) {
        setError("Catalog could not be loaded.");
      } else {
        setVerbs((data ?? []) as Verb[]);
      }
      setLoading(false);
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("de");
    return verbs.filter((verb) => {
      const translation = [...(verb.translations.en ?? []), ...(verb.translations.fa ?? [])].join(
        " ",
      );
      const matchesQuery =
        !needle ||
        `${verb.lemma} ${verb.participle_ii} ${translation}`
          .toLocaleLowerCase("de")
          .includes(needle);
      const matchesLevel = level === "all" || verb.cefr === level;
      return matchesQuery && matchesLevel;
    });
  }, [level, query, verbs]);

  async function installStarterCatalog() {
    setInstalling(true);
    setError(null);
    const { response } = await api.POST("/api/v1/content/starter-catalog");
    if (!response.ok) {
      setError("Starter catalog could not be installed.");
      setInstalling(false);
      return;
    }
    await refresh();
    setInstalling(false);
  }

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <Link href="/dashboard" className="brand" aria-label="Back to dashboard">
          DD<span>21</span>
        </Link>
        <Link href="/dashboard" className="text-link">
          Dashboard
        </Link>
      </header>

      <section className={styles.intro}>
        <div>
          <div className="eyebrow">PHASE 2 · VERSIONED CONTENT</div>
          <h1>Verb catalog.</h1>
          <p>
            Published learning content now lives in PostgreSQL, not inside a React component.
            Every correction creates a new immutable version.
          </p>
        </div>
        <div className={styles.stat}>
          <strong>{verbs.length}</strong>
          <span>published verbs</span>
        </div>
      </section>

      {loading ? <p className={styles.state}>Loading catalog…</p> : null}
      {error ? <p className="form-error">{error}</p> : null}

      {!loading && verbs.length === 0 ? (
        <section className={styles.empty}>
          <span className="card-kicker">STARTER DATASET</span>
          <h2>Install the first 100 interview verbs.</h2>
          <p>
            The bundled CSV is validated through the same import pipeline as future authored
            content. Running this again is idempotent.
          </p>
          <button
            className="button button-accent"
            onClick={installStarterCatalog}
            disabled={installing}
          >
            {installing ? "Publishing…" : "Install 100 verbs"}
          </button>
        </section>
      ) : null}

      {verbs.length > 0 ? (
        <>
          <section className={styles.toolbar} aria-label="Catalog filters">
            <label>
              Search
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="entwickeln, API, توسعه…"
              />
            </label>
            <label>
              CEFR
              <select value={level} onChange={(event) => setLevel(event.target.value)}>
                <option value="all">All</option>
                <option value="A2">A2</option>
                <option value="B1">B1</option>
                <option value="B2">B2</option>
              </select>
            </label>
            <span className={styles.resultCount}>{filtered.length} shown</span>
          </section>

          <section className={styles.grid}>
            {filtered.map((verb) => (
              <article className={styles.card} key={verb.version_id}>
                <div className={styles.cardTop}>
                  <span className={styles.cefr}>{verb.cefr}</span>
                  <span className={styles.version}>v{verb.version_number}</span>
                </div>
                <h2>{verb.infinitive}</h2>
                <p className={styles.persian} dir="rtl">
                  {verb.translations.fa?.[0] ?? "—"}
                </p>
                <dl>
                  <div>
                    <dt>Perfekt</dt>
                    <dd>
                      {verb.perfect_auxiliary} {verb.participle_ii}
                    </dd>
                  </div>
                  <div>
                    <dt>English</dt>
                    <dd>{verb.translations.en?.[0] ?? "—"}</dd>
                  </div>
                </dl>
                {verb.examples[0] ? <blockquote>{verb.examples[0].de}</blockquote> : null}
              </article>
            ))}
          </section>
        </>
      ) : null}
    </main>
  );
}
