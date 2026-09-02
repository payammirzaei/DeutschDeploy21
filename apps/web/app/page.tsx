import Link from "next/link";

const pillars = [
  ["21", "focused days"],
  ["A2→B1", "interview German"],
  ["PWA", "practice anywhere"],
];

export default function Home() {
  return (
    <main className="landing">
      <nav className="topbar" aria-label="Primary navigation">
        <Link href="/" className="brand" aria-label="DeutschDeploy21 home">
          DD<span>21</span>
        </Link>
        <Link className="text-link" href="/login">
          Sign in
        </Link>
      </nav>

      <section className="hero">
        <div className="eyebrow">GERMAN · SOFTWARE · INTERVIEWS</div>
        <h1>
          Speak German.
          <br />
          Explain your work.
          <br />
          <em>Get hired.</em>
        </h1>
        <p className="hero-copy">
          A focused learning system for software professionals who do not need all of German — they need
          the German that makes technical interviews work.
        </p>
        <div className="hero-actions">
          <Link className="button button-primary" href="/login">
            Enter your workspace <span aria-hidden="true">→</span>
          </Link>
          <span className="quiet">Private alpha · Phase 1</span>
        </div>
      </section>

      <section className="metrics" aria-label="Product focus">
        {pillars.map(([value, label]) => (
          <div className="metric" key={value}>
            <strong>{value}</strong>
            <span>{label}</span>
          </div>
        ))}
      </section>
    </main>
  );
}
