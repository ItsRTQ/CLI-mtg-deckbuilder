import { useEffect, useState } from "react";
import { api } from "../api/client";

interface DirList {
  path: string;
  parent: string | null;
  dirs: string[];
  writable: boolean;
}

// Browsers can't expose real filesystem paths from a native picker — but this app's
// server RUNS on the user's machine, so it browses folders server-side instead.
export default function FolderPicker({
  initialPath,
  onSelect,
  onClose,
}: {
  initialPath?: string | null;
  onSelect: (path: string) => void;
  onClose: () => void;
}) {
  const [listing, setListing] = useState<DirList | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load(path?: string | null) {
    setError(null);
    try {
      const q = path ? `?path=${encodeURIComponent(path)}` : "";
      setListing(await api<DirList>(`/api/settings/browse${q}`));
    } catch (e: any) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load(initialPath);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Choose a folder</h2>
        {error && <p className="error">{error}</p>}
        {listing && (
          <>
            <p className="path-crumb"><code>{listing.path}</code></p>
            {!listing.writable && (
              <p className="error">⚠ this folder is not writable</p>
            )}
            <div className="dir-list">
              {listing.parent && (
                <div className="dir-entry" onClick={() => load(listing.parent)}>
                  ⬑ ..
                </div>
              )}
              {listing.dirs.map((d) => (
                <div
                  key={d}
                  className="dir-entry"
                  onClick={() => load(`${listing.path}/${d}`)}
                >
                  📁 {d}
                </div>
              ))}
              {listing.dirs.length === 0 && (
                <p className="muted" style={{ padding: "0.5rem" }}>no subfolders</p>
              )}
            </div>
            <div className="row" style={{ marginTop: "0.9rem", justifyContent: "flex-end" }}>
              <button className="ghost" onClick={onClose}>Cancel</button>
              <button
                disabled={!listing.writable}
                onClick={() => onSelect(listing.path)}
              >
                Use this folder
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
