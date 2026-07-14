import { useEffect, useRef, useState } from "react";
import { DeckPreview, previewDeckList } from "../../api/decks";
import { useDeckWorkspace } from "../../state/DeckWorkspaceContext";

// Plain-text import with a DRY-RUN preview: nothing touches the deck until
// Apply. Merge (default) PATCHes only the clean additions; Replace PUTs the
// pasted text (server validates the whole list). Both are undoable.
export default function ImportModal({ onClose }: { onClose: () => void }) {
  const { deck, mergeCards, replaceList } = useDeckWorkspace();
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"merge" | "replace">("merge");
  const [preview, setPreview] = useState<DeckPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [applied, setApplied] = useState<string | null>(null);
  const boxRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    boxRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!deck) return null;

  async function runPreview(m = mode) {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setPreview(await previewDeckList(deck!.name, text, m));
    } catch (e: any) {
      setPreview(null);
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    if (!preview) return;
    setBusy(true);
    setError(null);
    try {
      if (mode === "merge") {
        const skip = new Set(
          [...preview.already_in_deck, ...preview.color_violations]);
        const clean = preview.resolved.filter((e) => !skip.has(e.name));
        // repeated resolved rows (same name twice in the paste) already got
        // their duplicates flagged into already_in_deck — dedupe survivors
        const seen = new Set<string>();
        const entries = clean.filter((e) => {
          const k = e.name.toLowerCase();
          if (seen.has(k)) return false;
          seen.add(k);
          return true;
        });
        if (!entries.length) {
          setError("Nothing new to add — everything is already in the deck or flagged.");
          return;
        }
        const ok = await mergeCards(entries);
        if (ok) setApplied(`Merged ${entries.length} entries.`);
      } else {
        const res = await replaceList(text);
        if (res) {
          setApplied(`List replaced.${res.skipped.length
            ? ` Skipped: ${res.skipped.join(", ")}` : ""}`);
        }
      }
    } finally {
      setBusy(false);
    }
  }

  const replaceBlocked = mode === "replace" && !!preview
    && preview.color_violations.length > 0;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal wide" role="dialog" aria-modal="true"
           aria-label="Import cards from text"
           onClick={(e) => e.stopPropagation()}>
        <h2>Import from text</h2>
        {applied ? (
          <>
            <p>{applied} <span className="muted">(↶ Undo is in the toolbar)</span></p>
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button onClick={onClose}>Done</button>
            </div>
          </>
        ) : (
          <>
            <textarea ref={boxRef} rows={8} value={text}
                      placeholder={"1 Sol Ring\n1 Arcane Signet\n8 Mountain\n(Moxfield exports work too)"}
                      onChange={(e) => { setText(e.target.value); setPreview(null); }} />
            <div className="row" style={{ alignItems: "center", flexWrap: "wrap" }}>
              <label style={{ whiteSpace: "nowrap" }}>
                <input type="radio" name="import-mode" checked={mode === "merge"}
                       onChange={() => { setMode("merge"); setPreview(null); }}
                       style={{ width: "auto", marginRight: "0.3rem" }} />
                Merge into deck
              </label>
              <label style={{ whiteSpace: "nowrap" }}>
                <input type="radio" name="import-mode" checked={mode === "replace"}
                       onChange={() => { setMode("replace"); setPreview(null); }}
                       style={{ width: "auto", marginRight: "0.3rem" }} />
                Replace whole list
              </label>
              <button disabled={!text.trim() || busy} onClick={() => runPreview()}>
                {busy ? "…" : "Preview"}
              </button>
              <button className="ghost" onClick={onClose}>Cancel</button>
            </div>
            {error && <p className="error" style={{ whiteSpace: "pre-wrap" }}>{error}</p>}
            {preview && (
              <div className="import-preview">
                <p>
                  <strong>{preview.resolved.length}</strong> lines resolve ·
                  projected size <strong>{preview.projected_size}</strong>/{preview.max_size}
                  {preview.projected_size > preview.max_size && (
                    <span className="error"> — over the limit</span>
                  )}
                </p>
                {preview.skipped.length > 0 && (
                  <details open>
                    <summary className="warn">
                      Unknown ({preview.skipped.length}) — will be skipped
                    </summary>
                    <p className="muted">{preview.skipped.join(", ")}</p>
                  </details>
                )}
                {preview.already_in_deck.length > 0 && (
                  <details>
                    <summary className="muted">
                      Already in deck / duplicates ({preview.already_in_deck.length})
                      {mode === "merge" ? " — excluded from merge" : ""}
                    </summary>
                    <p className="muted">{preview.already_in_deck.join(", ")}</p>
                  </details>
                )}
                {preview.color_violations.length > 0 && (
                  <details open>
                    <summary className="error">
                      Outside color identity ({preview.color_violations.length})
                      {mode === "merge" ? " — excluded from merge" : " — blocks replace"}
                    </summary>
                    <p className="muted">{preview.color_violations.join(", ")}</p>
                  </details>
                )}
                <div className="row" style={{ justifyContent: "flex-end" }}>
                  <button disabled={busy || replaceBlocked} onClick={apply}
                          title={replaceBlocked
                            ? "Fix the color-identity violations first"
                            : ""}>
                    {busy ? "…" : mode === "merge" ? "Apply merge" : "Apply replace"}
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
