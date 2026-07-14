import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { JobSummary } from "../api/builds";
import { BuildJob } from "../api/mock";

const TERMINAL = ["succeeded", "failed", "timeout", "cancelled"];
const IDLE_POLL_MS = 5000;
const ACTIVE_POLL_MS = 2500;
const TERMINAL_LINGER_MS = 8000;

// Turn the tail of logs/build.log into ONE readable line. Claude's stream-json
// emits JSON events — extract the tool call / text; agy logs are plain text.
function readableLogLine(lines: string[] | undefined): string | null {
  if (!lines) return null;
  for (let i = lines.length - 1; i >= 0; i--) {
    const raw = lines[i].trim();
    if (!raw) continue;
    if (!raw.startsWith("{")) return raw;
    try {
      const j = JSON.parse(raw);
      if (j.type === "assistant" && Array.isArray(j.message?.content)) {
        for (let k = j.message.content.length - 1; k >= 0; k--) {
          const c = j.message.content[k];
          if (c.type === "tool_use") {
            const arg = c.input?.command ?? c.input?.file_path ?? "";
            return `${c.name}: ${arg}`.trim();
          }
          if (c.type === "text" && c.text?.trim()) return c.text.trim();
        }
      }
      if (j.type === "system") return "starting agent…";
      if (j.type === "result") return "finishing…";
    } catch {
      return raw;
    }
  }
  return null;
}

export default function BuildBanner() {
  const nav = useNavigate();
  const location = useLocation();
  const [job, setJob] = useState<BuildJob | null>(null);
  const [dismissedId, setDismissedId] = useState<string | null>(null);
  const terminalAt = useRef<number | null>(null);

  useEffect(() => {
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;

    async function tick() {
      try {
        const jobs = await api<JobSummary[]>("/api/builds");
        const running = jobs.find((j) => !TERMINAL.includes(j.status));
        const latest = running ?? jobs[0];
        if (!latest) {
          if (!stop) setJob(null);
        } else if (running || (job && job.job_id === latest.job_id)) {
          // fetch detail for phase + log line (also covers the terminal linger)
          const detail = await api<BuildJob>(`/api/builds/${latest.job_id}`);
          if (!stop) {
            if (TERMINAL.includes(detail.status)) {
              if (terminalAt.current === null) terminalAt.current = Date.now();
              if (Date.now() - terminalAt.current > TERMINAL_LINGER_MS) {
                setJob(null);
              } else {
                setJob(detail);
              }
            } else {
              terminalAt.current = null;
              setJob(detail);
            }
          }
        } else if (!stop) {
          setJob(null);
        }
      } catch {
        if (!stop) setJob(null); // server unreachable -> no banner
      }
      if (!stop) {
        timer = setTimeout(tick, job && !TERMINAL.includes(job.status)
          ? ACTIVE_POLL_MS : IDLE_POLL_MS);
      }
    }

    tick();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.job_id, job?.status]);

  if (!job) return null;
  if (dismissedId === job.job_id) return null;
  if (location.pathname === "/results") return null; // Results already shows it all

  const running = !TERMINAL.includes(job.status);
  const logLine = readableLogLine(job.log_tail);

  return (
    <div
      className={`build-banner ${running ? "" : job.status === "succeeded" ? "done-ok" : "done-bad"}`}
      onClick={() => nav(`/results?job=${job.job_id}`)}
      title="Open build results"
    >
      {running ? <span className="spinner" /> : (
        <span className="banner-icon">{job.status === "succeeded" ? "✓" : "✗"}</span>
      )}
      <div className="banner-body">
        <div className="banner-title">
          {running ? `Building… ${job.phase}` : `Build ${job.status}`}
          <span className="muted"> · {job.elapsed_seconds}s</span>
        </div>
        {running && logLine && <div className="banner-log">{logLine}</div>}
      </div>
      <button
        className="banner-close"
        onClick={(e) => {
          e.stopPropagation();
          setDismissedId(job.job_id);
        }}
        title="Hide (the build keeps running)"
      >
        ✕
      </button>
    </div>
  );
}
