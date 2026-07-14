import { useEffect, useState } from "react";
import { api } from "../api/client";
import FolderField from "../components/FolderField";

interface ProviderInfo {
  name: string;
  installed: boolean;
  version?: string | null;
  detail?: string | null;
  supports_build: boolean;
  selected: boolean;
}

interface GuiSettings {
  builds_save_dir: string | null;
  builds_save_dir_resolved: string | null;
  user_bulk_dir: string | null;
  user_bulk_dir_resolved: string;
}

export default function Settings() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [settings, setSettings] = useState<GuiSettings | null>(null);

  useEffect(() => {
    api<ProviderInfo[]>("/api/providers").then(setProviders).catch((e) => setError(e.message));
    api<GuiSettings>("/api/settings").then(setSettings).catch((e) => setError(e.message));
  }, []);

  async function saveSetting(key: "builds_save_dir" | "user_bulk_dir", value: string) {
    const s = await api<GuiSettings>("/api/settings", {
      method: "POST",
      body: JSON.stringify({ [key]: value }),
    });
    setSettings(s);
  }

  const selectable = (p: ProviderInfo) => p.installed;
  const active = providers.find((p) => p.selected);

  async function select(p: ProviderInfo) {
    if (!selectable(p) || p.selected || saving) return;
    setError(null);
    setSaving(p.name);
    try {
      setProviders(await api<ProviderInfo[]>("/api/providers/select", {
        method: "POST",
        body: JSON.stringify({ name: p.name }),
      }));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(null);
    }
  }

  return (
    <div>
      <h1>Settings</h1>
      <div className="card">
        <h2>Build save folder</h2>
        <p className="muted">
          Where finished decks get saved as a named folder
          (<code>Commander-TIER-RANK-COST</code> with decklist + explanation).
          Relative paths resolve against the project; leave EMPTY to keep builds
          only in their <code>output/gui-builds/</code> workspace.
        </p>
        {settings && (
          <FolderField
            key={`bsd-${settings.builds_save_dir ?? ""}`}
            value={settings.builds_save_dir ?? ""}
            resolved={settings.builds_save_dir_resolved}
            placeholder="e.g. final-builds  ·  ~/Decks  ·  /mnt/d/mtg-decks"
            onSave={(v) => saveSetting("builds_save_dir", v)}
            emptyHint="library saving is OFF — builds stay in their workspace only"
          />
        )}
      </div>
      <div className="card">
        <h2>Card collection folder (user bulk)</h2>
        <p className="muted">
          Folder containing your <code>collection.txt</code> — the cards you OWN.
          Owned cards cost <strong>$0</strong> in every build's budget (maintained
          with <code>mtg bulk-add</code> or edited by hand). Leave EMPTY to use the
          project's <code>user-bulk/</code>.
        </p>
        {settings && (
          <FolderField
            key={`ubd-${settings.user_bulk_dir ?? ""}`}
            value={settings.user_bulk_dir ?? ""}
            resolved={settings.user_bulk_dir_resolved}
            placeholder="e.g. ~/mtg-collection  ·  /mnt/d/mtg/bulk"
            onSave={(v) => saveSetting("user_bulk_dir", v)}
            emptyHint=""
          />
        )}
      </div>
      <div className="card">
        <h2>AI agent provider</h2>
        <p className="muted">
          Deck builds run through YOUR agent — click a row to make it the active
          provider. Greyed-out rows are CLIs that aren't installed.
        </p>
        {error && <p className="error">{error}</p>}
        {active && !active.supports_build && (
          <p className="error">
            ⚠ "{active.name}" is detection-only in this version — builds will be
            refused until you switch to a build-capable provider (claude-code).
          </p>
        )}
        <table className="providers">
          <thead>
            <tr>
              <th></th>
              <th>Provider</th>
              <th>Status</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {providers.map((p) => (
              <tr
                key={p.name}
                className={
                  p.selected ? "row-selected" : selectable(p) ? "row-selectable" : "row-disabled"
                }
                onClick={() => select(p)}
                title={
                  selectable(p)
                    ? p.selected
                      ? "Active provider"
                      : `Click to switch to ${p.name}`
                    : "Not installed"
                }
              >
                <td>
                  <input
                    type="radio"
                    name="provider"
                    disabled={!selectable(p)}
                    checked={p.selected}
                    readOnly
                  />
                </td>
                <td>
                  {p.name}
                  {p.selected && <span className="badge ok" style={{ marginLeft: "0.5rem" }}>active</span>}
                  {!p.supports_build && p.installed && (
                    <span className="badge" style={{ marginLeft: "0.5rem" }}>can't build yet</span>
                  )}
                  {saving === p.name && <span className="muted" style={{ marginLeft: "0.5rem" }}>saving…</span>}
                </td>
                <td>
                  <span className={`badge ${p.installed ? "ok" : "bad"}`}>
                    {p.installed ? `installed ${p.version ?? ""}` : "not found"}
                  </span>
                </td>
                <td className="muted">{p.detail ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
