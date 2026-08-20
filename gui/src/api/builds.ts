import { api } from "./client";
import { BuildJob } from "./mock";

export interface BuildRequest {
  commander: string;
  partner?: string | null;
  budget?: string | null;
  budget_mode?: string;
  budget_overage_pct?: number | null;
  bracket?: string | null;
  rank_target?: string | null;
  theme?: string | null;
  notes?: string | null;
  use_bulk?: boolean;
  provider?: string | null;
}

// Real build endpoints (used once MOCK_BUILDS is off — Task 8).
export async function startBuild(req: BuildRequest): Promise<string> {
  const res = await api<{ job_id: string }>("/api/builds", {
    method: "POST",
    body: JSON.stringify(req),
  });
  return res.job_id;
}

export async function getJob(jobId: string): Promise<BuildJob> {
  return api<BuildJob>(`/api/builds/${encodeURIComponent(jobId)}`);
}

export async function cancelJob(jobId: string): Promise<void> {
  await api(`/api/builds/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
}

export interface JobSummary {
  job_id: string;
  status: string;
  phase: string;
  elapsed_seconds: number;
  provider: string;
  commander: string;
  kind: string;                     // "build" | "explain" | "advise"
}

// Builds run SERVER-SIDE: this recovers them after a route change or reload.
export async function listJobs(): Promise<JobSummary[]> {
  return api<JobSummary[]>("/api/builds");
}

/** Human message when an agent job that OWNS deck folders (build/explain) is
 * running, else null. Deck edits must pause then: the job renames the folders.
 * ADVISE jobs are exempt — they read a COPY of the deck, so editing is safe. */
export async function agentBusyMessage(): Promise<string | null> {
  try {
    const running = (await listJobs()).find(
      (j) => j.kind !== "advise"
        && !["succeeded", "failed", "timeout", "cancelled"].includes(j.status));
    return running
      ? `your agent is busy with "${running.commander}" (${running.phase}) — wait or stop it from Results`
      : null;
  } catch {
    return null;
  }
}
