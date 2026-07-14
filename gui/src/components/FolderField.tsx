import { useState } from "react";
import FolderPicker from "./FolderPicker";

// A folder-path setting row: text input + server-side Browse… picker + Save.
// Picking a folder in the modal saves immediately.
export default function FolderField({
  value,
  resolved,
  placeholder,
  onSave,
  emptyHint,
}: {
  value: string;
  resolved: string | null;
  placeholder: string;
  onSave: (value: string) => Promise<void>;
  emptyHint: string;
}) {
  const [draft, setDraft] = useState(value);
  const [picking, setPicking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function save(v: string) {
    setError(null);
    setSaved(false);
    try {
      await onSave(v);
      setSaved(true);
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <>
      <div className="row">
        <div style={{ flex: 1 }}>
          <input
            value={draft}
            onChange={(e) => { setDraft(e.target.value); setSaved(false); }}
            placeholder={placeholder}
          />
        </div>
        <button className="ghost" onClick={() => setPicking(true)}>📁 Browse…</button>
        <button onClick={() => save(draft)}>Save</button>
      </div>
      {picking && (
        <FolderPicker
          initialPath={resolved}
          onClose={() => setPicking(false)}
          onSelect={(path) => {
            setPicking(false);
            setDraft(path);
            save(path);
          }}
        />
      )}
      {error && <p className="error">{error}</p>}
      {saved && <p className="muted">✓ saved</p>}
      {resolved ? (
        <p className="muted">using: <code>{resolved}</code></p>
      ) : (
        <p className="muted">{emptyHint}</p>
      )}
    </>
  );
}
