import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BuildJob, MOCK_BUILDS, mockJobStatus } from "../api/mock";
import { JobSummary } from "../api/builds";

const TERMINAL = ["succeeded", "failed", "timeout", "cancelled"];
const RUNNING = (s: string) => !TERMINAL.includes(s);

export default function Results() {
  const [params, setParams] = useSearchParams();
  const jobId = params.get("job");
  const [job, setJob] = useState<BuildJob | null>(null);
  const [recent, setRecent] = useState<JobSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);

  // Builds run SERVER-SIDE — they do NOT stop when you switch pages. Recover the
  // job list from the server; with no ?job= in the URL, jump to the latest one.
  useEffect(() => {
    if (MOCK_BUILDS) return;
    (async () => {
      try {
        const { listJobs } = await import("../api/builds");
        const jobs = await listJobs();
        setRecent(jobs);
        if (!jobId) {
          const active = jobs.find((j) => RUNNING(j.status)) ?? jobs[0];
          if (active) setParams({ job: active.job_id }, { replace: true });
        }
      } catch (e: any) {
        setError(e.message);
      }
    })();
  }, [jobId, setParams]);

  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    async function poll() {
      try {
        let j: BuildJob;
        if (MOCK_BUILDS) {
          j = mockJobStatus(jobId!);
        } else {
          const { getJob } = await import("../api/builds");
          j = await getJob(jobId!);
        }
        if (stop) return;
        setJob(j);
        if (!TERMINAL.includes(j.status)) setTimeout(poll, 2000);
      } catch (e: any) {
        if (!stop) setError(e.message);
      }
    }
    poll();
    return () => {
      stop = true;
    };
  }, [jobId]);

  async function stopBuild() {
    if (!jobId || !job || !RUNNING(job.status) || stopping) return;
    if (!window.confirm("Stop this deck build? The agent will be killed and the job marked cancelled.")) return;
    setStopping(true);
    try {
      const { cancelJob } = await import("../api/builds");
      await cancelJob(jobId);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setStopping(false);
    }
  }

  if (!jobId) {
    return (
      <div>
        <h1>Results</h1>
        {error && <p className="error">{error}</p>}
        {recent.length === 0 ? (
          <p className="muted">No builds yet — start one from the Build Wizard.</p>
        ) : (
          <p className="muted">loading latest build…</p>
        )}
      </div>
    );
  }

  return (
    <div>
      <h1>Results {MOCK_BUILDS && <span className="muted">(mock)</span>}</h1>
      {error && <p className="error">{error}</p>}
      {job && (
        <>
          <div className="card">
            <div className="row">
              <span className={`badge ${job.status === "succeeded" ? "ok" : TERMINAL.includes(job.status) ? "bad" : ""}`}>
                {job.status}
              </span>
              <span className="muted">
                {job.phase} · {job.elapsed_seconds}s
              </span>
              {RUNNING(job.status) && (
                <button className="ghost danger" onClick={stopBuild} disabled={stopping}>
                  {stopping ? "stopping…" : "■ Stop build"}
                </button>
              )}
            </div>
            {RUNNING(job.status) && (
              <p className="muted" style={{ marginBottom: 0 }}>
                The build runs on the local server — you can switch pages or close
                this tab and come back; it keeps going. Only "Stop build" (or
                closing the `mtg gui` terminal) ends it.
              </p>
            )}
            {RUNNING(job.status) && job.log_tail && (
              <details open style={{ marginTop: "0.7rem" }}>
                <summary className="muted">live log</summary>
                <div className="log">{job.log_tail.join("\n")}</div>
              </details>
            )}
          </div>
          {job.error && (
            <div className="card">
              <h2 className="error">Build failed — {job.error.type}</h2>
              <p>{job.error.message}</p>
            </div>
          )}
          {job.result && (
            <div className="card">
              <h2>{job.result.decklist ? "Deck" : `✨ Explanation ready`}</h2>
              {job.result.deck_name && !job.result.decklist && (
                <p className="muted">
                  "{job.result.deck_name}" was annotated and explained — see it in
                  Collection → Decks.
                </p>
              )}
              {job.result.saved_to && (
                <p className="muted">
                  💾 saved to <code>{job.result.saved_to}</code>
                </p>
              )}
              {job.result.save_warning && (
                <p className="error">⚠ {job.result.save_warning}</p>
              )}
              {job.result.decklist && (
                <table>
                  <tbody>
                    {job.result.decklist.map((e) => (
                      <tr key={e.name}>
                        <td style={{ width: "3rem" }}>{e.quantity}</td>
                        <td>{e.name}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {job.result.explanation && (
                <details style={{ marginTop: "0.8rem" }} open={!job.result.decklist}>
                  <summary>Explanation</summary>
                  <div className="log">{job.result.explanation}</div>
                </details>
              )}
            </div>
          )}
          {recent.length > 1 && (
            <div className="card">
              <h2>Recent builds</h2>
              <table>
                <tbody>
                  {recent.map((r) => (
                    <tr
                      key={r.job_id}
                      className={r.job_id === jobId ? "row-selected" : "row-selectable"}
                      onClick={() => setParams({ job: r.job_id })}
                    >
                      <td>{r.commander}</td>
                      <td><span className={`badge ${r.status === "succeeded" ? "ok" : RUNNING(r.status) ? "" : "bad"}`}>{r.status}</span></td>
                      <td className="muted">{r.provider} · {r.elapsed_seconds}s</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
