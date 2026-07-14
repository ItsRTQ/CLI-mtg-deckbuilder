import { useRef, useState } from "react";
import { loadWorkspacePrefs, saveWorkspacePrefs } from "../../state/workspacePrefs";
import { useDeckWorkspace } from "../../state/DeckWorkspaceContext";
import { deckViewById } from "./deckViews";
import DeckMenu from "./DeckMenu";
import ImportModal from "./ImportModal";
import DeckStatsModal from "./DeckStatsModal";

// The Deck Builder container: header (commander, name, count, menu), one
// general drop zone (sections are type-derived — the server sections the card
// on refetch), and the active deck view.
export default function DeckPanel() {
  const {
    deck, addCard, dragCard, membershipFor, error, clearError,
  } = useDeckWorkspace();
  const [viewId, setViewId] = useState(() => loadWorkspacePrefs().deckView);
  const [importOpen, setImportOpen] = useState(false);
  const [statsOpen, setStatsOpen] = useState(false);
  const [dropState, setDropState] = useState<"" | "drop-ok" | "drop-bad">("");
  const depth = useRef(0);                 // dragenter/leave nest across children

  if (!deck) return null;
  const View = deckViewById(viewId).Component;

  function pickView(id: string) {
    setViewId(id);
    saveWorkspacePrefs({ deckView: id });
  }

  const dragBlocked = dragCard
    ? ["limit", "illegal"].includes(membershipFor(dragCard).state)
    : false;

  function onDragOver(e: React.DragEvent) {
    if (!e.dataTransfer.types.includes("application/x-mtg-card")) return;
    if (dragBlocked) {
      e.dataTransfer.dropEffect = "none";  // browser shows no-drop
      return;
    }
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  }
  function onDragEnter(e: React.DragEvent) {
    if (!e.dataTransfer.types.includes("application/x-mtg-card")) return;
    depth.current += 1;
    setDropState(dragBlocked ? "drop-bad" : "drop-ok");
  }
  function onDragLeave() {
    depth.current = Math.max(0, depth.current - 1);
    if (depth.current === 0) setDropState("");
  }
  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    depth.current = 0;
    setDropState("");
    const name = e.dataTransfer.getData("application/x-mtg-card")
      || e.dataTransfer.getData("text/plain");
    if (name) addCard(name);
  }

  return (
    <div className={`deck-panel-ws ${dropState}`}
         onDragOver={onDragOver} onDragEnter={onDragEnter}
         onDragLeave={onDragLeave} onDrop={onDrop}>
      <div className="ws-deck-header">
        <div className="ws-deck-title">
          <strong>{deck.commander ?? deck.name}</strong>
          <span className="muted"> · {deck.stats.total_cards} cards
            · ${deck.stats.known_price.toFixed(2)}</span>
        </div>
        <div className="ws-deck-controls">
          <DeckMenu
            viewId={viewId}
            onPickView={pickView}
            onImport={() => setImportOpen(true)}
            onStats={() => setStatsOpen(true)}
          />
        </div>
      </div>
      {error && (
        <p className="error" style={{ whiteSpace: "pre-wrap" }}>
          {error}
          <button className="ghost" style={{ marginLeft: "0.6rem" }}
                  onClick={clearError}>dismiss</button>
        </p>
      )}
      {dropState === "drop-ok" && dragCard && (
        <p className="muted drop-hint">Drop to add {dragCard.name}</p>
      )}
      <View />
      {importOpen && <ImportModal onClose={() => setImportOpen(false)} />}
      {statsOpen && <DeckStatsModal onClose={() => setStatsOpen(false)} />}
    </div>
  );
}
