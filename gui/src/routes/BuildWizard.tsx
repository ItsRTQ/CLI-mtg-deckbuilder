import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MOCK_BUILDS } from "../api/mock";
import { JobSummary } from "../api/builds";
import CommanderInput from "../components/CommanderInput";
import AgentConfirm from "../components/AgentConfirm";

const TERMINAL = ["succeeded", "failed", "timeout", "cancelled"];

// The form mirrors the BUILDER.md §5 core questions — its answers become the
// deck's build contract (budget / bracket / rank_target) + theme note.
export default function BuildWizard() {
  const nav = useNavigate();
  const [commander, setCommander] = useState("");
  const [budget, setBudget] = useState("150");
  const [bracket, setBracket] = useState("n/a");
  const [rankTarget, setRankTarget] = useState("n/a");
  const [theme, setTheme] = useState("");
  const [notes, setNotes] = useState("");
  const [useBulk, setUseBulk] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [activeBuild, setActiveBuild] = useState<JobSummary | null>(null);
  const [confirming, setConfirming] = useState(false);

  // ONE build at a time (the backend enforces it with a 409; this is the UX):
  // poll while locked so the wizard unlocks itself when the build finishes.
  useEffect(() => {
    if (MOCK_BUILDS) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    async function check() {
      try {
        const { listJobs } = await import("../api/builds");
        const jobs = await listJobs();
        const running = jobs.find((j) => !TERMINAL.includes(j.status)) ?? null;
        if (!stop) setActiveBuild(running);
        if (!stop && running) timer = setTimeout(check, 3000);
      } catch {
        if (!stop) setActiveBuild(null);
      }
    }
    check();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, []);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      if (MOCK_BUILDS) {
        nav("/results?job=mock-job-1");
        return;
      }
      const { startBuild } = await import("../api/builds");
      const jobId = await startBuild({
        commander,
        budget: budget.trim() || "n/a",
        bracket,
        rank_target: rankTarget,
        theme: theme.trim() || null,
        notes: notes.trim() || null,
        use_bulk: useBulk,
      });
      nav(`/results?job=${jobId}`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (activeBuild) {
    return (
      <div>
        <h1>Build Wizard</h1>
        <div className="card">
          <div className="row">
            <span className="spinner" />
            <strong>Your agent is busy:</strong> {activeBuild.commander}
            <span className="muted">
              {activeBuild.phase} · {activeBuild.elapsed_seconds}s
            </span>
          </div>
          <p className="muted">
            One agent job at a time (build or explain) — the wizard unlocks
            automatically when it finishes.
          </p>
          <div className="row">
            <button onClick={() => nav(`/results?job=${activeBuild.job_id}`)}>
              View progress
            </button>
            <span className="muted">…or stop it from Results if you changed your mind.</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1>Build Wizard {MOCK_BUILDS && <span className="muted">(mock)</span>}</h1>
      <div className="card">
        <label>Commander *</label>
        <CommanderInput
          value={commander}
          onChange={setCommander}
          placeholder="Start typing — suggestions are commanders only"
        />
        <div className="row">
          <div style={{ flex: 1 }}>
            <label>Budget (USD, or n/a)</label>
            <input value={budget} onChange={(e) => setBudget(e.target.value)} />
          </div>
          <div style={{ flex: 1 }}>
            <label>Bracket</label>
            <select value={bracket} onChange={(e) => setBracket(e.target.value)}>
              <option value="n/a">n/a — don't care about brackets</option>
              <option value="1-2">1-2 (casual)</option>
              <option value="3">3 (upgraded)</option>
              <option value="4-5">4-5 (high power)</option>
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <label>Target power RANK</label>
            <select value={rankTarget} onChange={(e) => setRankTarget(e.target.value)}>
              <option value="n/a">n/a — agent choice</option>
              {[1, 2, 3, 4, 5, 6, 7].map((n) => (
                <option key={n} value={String(n)}>
                  {n} {["Scrap", "Dormant", "Awakened", "Charged", "Ascendant", "Forbidden", "Mythic"][n - 1]}
                </option>
              ))}
            </select>
          </div>
        </div>
        <label>Theme / direction (optional)</label>
        <input
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
          placeholder="e.g. copy-combo, tokens, lifegain..."
        />
        <label>Extra notes for the agent (optional)</label>
        <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
        <label style={{ marginTop: "0.7rem" }}>
          <input
            type="checkbox"
            checked={useBulk}
            onChange={(e) => setUseBulk(e.target.checked)}
            style={{ width: "auto", marginRight: "0.45rem" }}
          />
          Use my collection — cards I own cost the budget $0
          <span className="muted"> (uncheck to price every card at full cost)</span>
        </label>
        {error && <p className="error">{error}</p>}
        <p style={{ marginTop: "1rem" }}>
          <button disabled={!commander.trim() || busy} onClick={() => setConfirming(true)}>
            {busy ? "starting…" : "Build with my agent"}
          </button>
        </p>
        {confirming && (
          <AgentConfirm
            action={`Build a "${commander}" deck` +
                    (budget.trim() && budget.trim() !== "n/a" ? ` · budget $${budget.trim()}` : "")}
            onClose={() => setConfirming(false)}
            onConfirm={() => {
              setConfirming(false);
              submit();
            }}
          />
        )}
        <p className="muted">
          The build runs through the provider configured in Settings — it may take
          several minutes; you can watch it live in Results.
        </p>
      </div>
    </div>
  );
}
