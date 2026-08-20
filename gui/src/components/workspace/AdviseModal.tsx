import { useCallback, useEffect, useRef, useState } from "react";
import { BuildJob, CardResult } from "../../api/mock";
import { CardZoom } from "../CardTile";
import { api } from "../../api/client";
import { cancelJob, getJob } from "../../api/builds";
import { AdviseResult, GapFill, startAdvise } from "../../api/decks";
import { useDeckWorkspace } from "../../state/DeckWorkspaceContext";
import { loadWorkspacePrefs, saveWorkspacePrefs } from "../../state/workspacePrefs";

// Tier-2 agent advice: a BATCH job (minutes, not live) — the agent reads the
// draft, judges what it's shaping into, and returns verified candidate cards.
// The job runs server-side: closing the modal doesn't kill it, and the last
// job per deck is remembered (workspacePrefs.adviseJob) so reopening resumes.

const TERMINAL = ["succeeded", "failed", "timeout", "cancelled"];
const PRIORITY_ORDER = { high: 0, medium: 1, low: 2 } as const;

interface ProviderInfo {
  name: string;
  installed: boolean;
  supports_build: boolean;
  selected: boolean;
}

export default function AdviseModal({ onClose }: { onClose: () => void }) {
  const { deck, addCard, membershipFor, pendingNames, requestSearch } =
    useDeckWorkspace();
  const [jobId, setJobId] = useState<string | null>(() => {
    const saved = loadWorkspacePrefs().adviseJob;
    return saved && saved.deck === deck?.name ? saved.jobId : null;
  });
  const [job, setJob] = useState<BuildJob | null>(null);
  const [result, setResult] = useState<AdviseResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [notes, setNotes] = useState("");
  const [provider, setProvider] = useState<ProviderInfo | null | undefined>();
  const [zoom, setZoom] = useState<CardResult | null>(null);
  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  // Which agent will run this? (selected provider, else the default pick) —
  // the user should know WHO they're about to launch before clicking Run.
  useEffect(() => {
    let stop = false;
    api<ProviderInfo[]>("/api/providers")
      .then((ps) => {
        if (stop) return;
        const usable = ps.filter((p) => p.installed && p.supports_build);
        setProvider(usable.find((p) => p.selected) ?? usable[0] ?? null);
      })
      .catch(() => !stop && setProvider(null));
    return () => { stop = true; };
  }, []);

  const stopPolling = useCallback(() => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  }, []);

  // Poll the job while it runs; a terminal status settles the modal.
  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    async function tick() {
      try {
        const j = await getJob(jobId!);
        if (stop) return;
        setJob(j);
        if (TERMINAL.includes(j.status)) {
          stopPolling();
          if (j.status === "succeeded" && j.result) {
            setResult(j.result as unknown as AdviseResult);
          } else if (j.status !== "succeeded") {
            // dead job (cancelled/failed/timeout): surface why, forget it, and
            // return to the start view so a new run is one click away
            setError(j.error?.message ?? `job ${j.status}`);
            setJobId(null);
            setJob(null);
            saveWorkspacePrefs({ adviseJob: null });
          }
        }
      } catch (e: any) {
        if (stop) return;
        stopPolling();
        if (e?.status === 404) {
          // stale job: the registry is in-memory, a backend restart forgot it
          setJobId(null);
          setJob(null);
          saveWorkspacePrefs({ adviseJob: null });
          setError("That analysis job no longer exists (the backend was "
            + "restarted) — run a new one.");
        } else {
          setError(e.message);
        }
      }
    }
    tick();
    timer.current = setInterval(tick, 3000);
    return () => { stop = true; stopPolling(); };
  }, [jobId, stopPolling]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (zoomRef.current) setZoom(null);   // zoom closes first, modal second
      else onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!deck) return null;

  async function run() {
    setStarting(true);
    setError(null);
    setResult(null);
    setJob(null);
    try {
      const res = await startAdvise(deck!.name, { notes: notes.trim() || null });
      setJobId(res.job_id);
      saveWorkspacePrefs({ adviseJob: { deck: deck!.name, jobId: res.job_id } });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setStarting(false);
    }
  }

  async function cancel() {
    if (!jobId) return;
    try {
      await cancelJob(jobId);   // the poll reports the resulting state
    } catch (e: any) {
      if (e?.status === 404) {  // stale job (backend restarted) — forget it
        setJobId(null);
        setJob(null);
        saveWorkspacePrefs({ adviseJob: null });
      }
    }
  }

  function moreLikeThis(fill: GapFill) {
    requestSearch({
      tags: fill.tags?.length ? fill.tags : undefined,
      query: fill.query ?? undefined,
      type: fill.type ?? undefined,
      colors: fill.colors || deck?.color_identity.join(""),
    });
    onClose();
  }

  const running = !!jobId && !!job && !TERMINAL.includes(job.status);
  const waiting = !!jobId && !job;
  const recs = result
    ? [...result.recommendations].sort(
        (a, b) => (PRIORITY_ORDER[a.priority] ?? 3) - (PRIORITY_ORDER[b.priority] ?? 3))
    : [];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal wide" role="dialog" aria-modal="true"
           aria-label="Agent advice" onClick={(e) => e.stopPropagation()}>
        <h2>Agent advice — {deck.commander ?? deck.name}</h2>
        {error && <p className="error" style={{ whiteSpace: "pre-wrap" }}>{error}</p>}

        {!jobId && !result && (
          <>
            <p className="muted">
              A headless agent reads your draft (it's fine that it's incomplete),
              judges what it's shaping into, and returns prioritized directions
              with verified candidate cards. This runs in the background and
              takes a few minutes — you can close this window and keep building.
            </p>
            <label htmlFor="advise-notes">Anything the agent should know? <span className="muted">(optional)</span></label>
            <textarea id="advise-notes" rows={2} value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="e.g. going for a lifegain theme, keep it under $100…" />
            {provider === null && (
              <p className="error">
                No build-capable agent provider is installed/selected — configure
                one in Settings before running an analysis.
              </p>
            )}
            {provider && (
              <p className="muted" style={{ fontSize: "0.82rem" }}>
                Will run with your <strong>{provider.name}</strong> agent
                {provider.selected ? "" : " (default pick — none selected)"} —
                change it in Settings.
              </p>
            )}
            <div className="row" style={{ marginTop: "0.6rem" }}>
              <button onClick={run} disabled={starting || provider === null}>
                {starting ? "starting…" : "▶ Run agent analysis"}
              </button>
            </div>
          </>
        )}

        {(running || waiting) && (
          <div className="advise-running">
            <p><span className="spinner" aria-hidden="true" /> {job?.phase ?? "starting…"}
              {job ? ` — ${Math.floor(job.elapsed_seconds / 60)}m ${job.elapsed_seconds % 60}s` : ""}</p>
            {job?.log_tail && job.log_tail.length > 0 && (
              <pre className="advise-log">{job.log_tail.slice(-6).join("\n")}</pre>
            )}
            <div className="row">
              <button className="ghost" onClick={cancel}>■ Cancel job</button>
              <span className="muted" style={{ fontSize: "0.8rem" }}>
                closing this window won't stop it
              </span>
            </div>
          </div>
        )}

        {result && (
          <div className="gaps-body">
            {result.summary && <p className="advise-summary">{result.summary}</p>}
            {recs.map((r) => (
              <div key={r.title} className="advise-rec">
                <div className="advise-rec-head">
                  <span className={`prio prio-${r.priority}`}>{r.priority}</span>
                  <strong>{r.title}</strong>
                  {r.fill && (
                    <button className="ghost" style={{ marginLeft: "auto" }}
                            onClick={() => moreLikeThis(r.fill!)}>
                      More like this →
                    </button>
                  )}
                </div>
                <p className="muted advise-reason">{r.reason}</p>
                {r.cards.map((c) => {
                  const m = membershipFor({ name: c.name });
                  const inDeck = m.state === "in" || m.state === "limit";
                  const blocked = c.valid === false || m.state === "illegal";
                  const pending = pendingNames.has(c.name.toLowerCase());
                  return (
                    <div key={c.name} className="gap-row">
                      <div className="gap-info">
                        <button className="card-name-link"
                                title={`Preview ${c.name}`}
                                onClick={() => setZoom({
                                  name: c.name,
                                  image_url: c.image_url ?? null,
                                  usd_price: c.price_usd,
                                })}>
                          {c.name}
                        </button>
                        {c.price_usd != null && (
                          <span className="muted"> ${c.price_usd.toFixed(2)}</span>
                        )}
                        <span> — {c.why}</span>
                        {c.valid === false && (
                          <span className="error"> ({c.issue})</span>
                        )}
                      </div>
                      <button disabled={blocked || inDeck || pending}
                              title={c.valid === false ? c.issue
                                : inDeck ? "Already in the deck"
                                : m.state === "illegal" ? "Outside the deck's color identity"
                                : `Add ${c.name} to the deck`}
                              onClick={() => addCard(c.name)}>
                        {inDeck ? "✓ In deck" : "+ Add"}
                      </button>
                    </div>
                  );
                })}
              </div>
            ))}
            <div className="row" style={{ marginTop: "0.6rem" }}>
              <button className="ghost"
                      onClick={() => { setResult(null); setJobId(null); setJob(null); }}>
                ↻ Run again
              </button>
            </div>
          </div>
        )}

        <div className="row" style={{ justifyContent: "flex-end", marginTop: "0.8rem" }}>
          <button onClick={onClose}>Close</button>
        </div>
        {/* inside .modal so the zoom's close-click can't bubble to the
            overlay and close this modal too */}
        {zoom && <CardZoom card={zoom} onClose={() => setZoom(null)} />}
      </div>
    </div>
  );
}
