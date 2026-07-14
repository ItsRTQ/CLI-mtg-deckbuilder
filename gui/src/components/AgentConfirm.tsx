import { useEffect, useState } from "react";
import { api } from "../api/client";

interface ProviderInfo {
  name: string;
  installed: boolean;
  version?: string | null;
  supports_build: boolean;
  selected: boolean;
}

// Confirmation gate shown before ANY agent job (build / explain): tells the user
// exactly WHICH AI provider is about to run, so nobody burns the wrong quota by
// mistake. Confirm is disabled if the active provider can't actually build.
export default function AgentConfirm({
  action,
  onConfirm,
  onClose,
}: {
  action: string;               // e.g. 'Build "Krenko, Mob Boss" · budget $50'
  onConfirm: () => void;
  onClose: () => void;
}) {
  const [provider, setProvider] = useState<ProviderInfo | null | undefined>(undefined);

  useEffect(() => {
    api<ProviderInfo[]>("/api/providers")
      .then((ps) => setProvider(ps.find((p) => p.selected) ?? null))
      .catch(() => setProvider(null));
  }, []);

  const ok = !!provider && provider.installed && provider.supports_build;

  return (
    <div className="modal-overlay confirm-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Run your AI agent?</h2>
        <p>{action}</p>
        {provider === undefined && <p className="muted">checking provider…</p>}
        {provider === null && (
          <p className="error">
            No AI provider selected — pick one in Settings first.
          </p>
        )}
        {provider && (
          <p className="provider-line">
            Provider: <strong>{provider.name}</strong>
            {provider.version && <span className="muted"> · {provider.version}</span>}
            {!ok && (
              <span className="error">
                {" "}— can't build (not installed or detection-only); switch in Settings.
              </span>
            )}
          </p>
        )}
        <p className="muted">
          This uses the provider's quota and can take several minutes. You can
          watch it in the top-right banner and stop it from Results.
        </p>
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button className="ghost" onClick={onClose}>Cancel</button>
          <button disabled={!ok} onClick={onConfirm}>
            {provider ? `▶ Run with ${provider.name}` : "▶ Run"}
          </button>
        </div>
      </div>
    </div>
  );
}
