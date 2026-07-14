// Thin fetch wrapper that unwraps the project's JSON error contract:
// every API error body is {"error": {"type": ..., "message": ...}} (possibly
// nested under FastAPI's "detail").
export class ApiError extends Error {
  type: string;
  status: number;
  body: unknown;
  constructor(status: number, type: string, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.type = type;
    this.body = body;
  }
}

function unwrapError(status: number, body: any): ApiError {
  const err = body?.error ?? body?.detail?.error ?? null;
  if (err?.message) return new ApiError(status, err.type ?? "unknown", err.message, body);
  return new ApiError(status, "http", `HTTP ${status}`, body);
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  let body: any = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) throw unwrapError(res.status, body);
  return body as T;
}
