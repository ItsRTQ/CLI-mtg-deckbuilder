import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import CardSearch from "../components/CardSearch";

interface ProjectStatus {
  project_root: string;
  database_path: string;
  database_exists: boolean;
  raw_cards_path: string;
  raw_cards_exists: boolean;
}

interface DataJob {
  running: boolean;
  mode: string | null;
  phase: string | null;
  elapsed_seconds: number;
  error: string | null;
  finished: boolean;
}

export default function Home() {
  const [status, setStatus] = useState<ProjectStatus | null>(null);
  const [job, setJob] = useState<DataJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout>>();

  function loadStatus() {
    api<ProjectStatus>("/api/status").then(setStatus).catch((e) => setError(e.message));
  }

  async function pollJob() {
    try {
      const j = await api<DataJob>("/api/data/refresh");
      setJob(j);
      if (j.running) {
        pollTimer.current = setTimeout(pollJob, 2000);
      } else if (j.finished) {
        loadStatus(); // DB state changed — refresh the panel
      }
    } catch {
      /* server hiccup — stop polling */
    }
  }

  useEffect(() => {
    loadStatus();
    pollJob(); // picks up a refresh already running (e.g. after a reload)
    return () => clearTimeout(pollTimer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [confirming, setConfirming] = useState(false);

  async function startRefresh() {
    setConfirming(false);
    setError(null);
    try {
      await api<DataJob>("/api/data/refresh", { method: "POST" });
      pollJob();
    } catch (e: any) {
      setError(e.message);
    }
  }

  const busy = job?.running ?? false;
  const reload = status?.database_exists ?? false;

  return (
    <div>
      <h1>Home</h1>
      <div className="card">
        <p style={{ margin: 0 }}>
          Build Commander decks with <strong>your own AI agent</strong> — this GUI
          preps the build, your configured agent runs it through the <code>mtg</code> tool.
          {" "}<span className="muted">
            1. Card database below · 2. Provider in Settings · 3. Find a commander ·
            4. Build Wizard.
          </span>
        </p>
      </div>
      <div className="card">
          <h2>Card database</h2>
          {error && <p className="error">{error}</p>}
          {!status && !error && <p className="muted">loading…</p>}
          {status && (
            <>
              <table>
                <tbody>
                  <tr>
                    <td>Database</td>
                    <td>
                      <span className={`badge ${status.database_exists ? "ok" : "bad"}`}>
                        {status.database_exists ? "present" : "MISSING"}
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td>Raw Scryfall data</td>
                    <td>
                      <span className={`badge ${status.raw_cards_exists ? "ok" : "bad"}`}>
                        {status.raw_cards_exists ? "present" : "missing"}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
              <p className="muted" style={{ wordBreak: "break-all" }}>
                {status.database_path}
              </p>
              <div className="row">
                <button onClick={() => setConfirming(true)} disabled={busy}>
                  {busy ? (
                    <>refreshing…</>
                  ) : reload ? (
                    <>⟳ Reload DB</>
                  ) : (
                    <>⬇ Download DB</>
                  )}
                </button>
                {busy && (
                  <span className="row" style={{ gap: "0.5rem" }}>
                    <span className="spinner" />
                    <span className="muted">
                      {job?.phase} · {job?.elapsed_seconds}s
                    </span>
                  </span>
                )}
              </div>
              {job?.error && <p className="error">refresh failed: {job.error}</p>}
              {!busy && job?.finished && !job?.error && (
                <p className="muted">✓ database refreshed</p>
              )}
            </>
          )}
      </div>
      <CardSearch />
      {confirming && status && (
        <div className="modal-overlay" onClick={() => setConfirming(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>{reload ? "⚠ Reload the card database?" : "⬇ Download the card database?"}</h2>
            {reload ? (
              <p>
                This <strong>deletes the current card data</strong>, re-downloads the
                full Scryfall bulk (<strong>~2GB</strong>) and rebuilds the local
                database from scratch.
              </p>
            ) : (
              <p>
                This downloads the full Scryfall bulk (<strong>~2GB</strong>) and
                builds the local card database.
              </p>
            )}
            <p className="muted">
              ⏳ It can take a while — from a few minutes to much longer
              <strong> depending on your internet connection</strong>. The GUI stays
              usable, but deck builds are blocked until it finishes.
            </p>
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="ghost" onClick={() => setConfirming(false)}>Cancel</button>
              <button className={reload ? "danger" : ""} onClick={startRefresh}>
                {reload ? "Yes, delete & reload" : "Yes, download"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
