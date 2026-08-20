import { useEffect, useRef, useState } from "react";
import CardSearch from "../components/CardSearch";
import WorkspaceShell from "../components/workspace/WorkspaceShell";
import DeckPanel from "../components/workspace/DeckPanel";
import DeckPicker from "../components/workspace/DeckPicker";
import {
  DeckWorkspaceProvider, useDeckWorkspace,
} from "../state/DeckWorkspaceContext";
import { loadWorkspacePrefs } from "../state/workspacePrefs";

// Deck-building workspace: two movable, resizable containers over ONE shared
// deck state (DeckWorkspaceContext). Both panes stay mounted in a fixed DOM
// order — layout switches never remount them.

function DeckPane() {
  const { deck, openDeck } = useDeckWorkspace();
  // restore the last open deck once per visit
  useEffect(() => {
    const last = loadWorkspacePrefs().lastDeckName;
    if (last) openDeck(last);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return deck ? <DeckPanel /> : <DeckPicker />;
}

function SearchPane() {
  const {
    deck, addCard, removeCard, membershipFor, setDragCard, searchRequest,
  } = useDeckWorkspace();
  // Deck→search drag = quick remove (the inverse of search→deck add). Deck
  // cards travel under their own MIME type so the deck's add-zone ignores them.
  const [removeReady, setRemoveReady] = useState(false);
  const depth = useRef(0);                 // dragenter/leave nest across children
  const hasDeckCard = (e: React.DragEvent) =>
    e.dataTransfer.types.includes("application/x-mtg-deck-card");

  return (
    <div className={`search-drop-ws${removeReady ? " drop-remove" : ""}`}
         onDragOver={(e) => {
           if (!hasDeckCard(e)) return;
           e.preventDefault();
           e.dataTransfer.dropEffect = "move";
         }}
         onDragEnter={(e) => {
           if (!hasDeckCard(e)) return;
           depth.current += 1;
           setRemoveReady(true);
         }}
         onDragLeave={() => {
           depth.current = Math.max(0, depth.current - 1);
           if (depth.current === 0) setRemoveReady(false);
         }}
         onDrop={(e) => {
           if (!hasDeckCard(e)) return;
           e.preventDefault();
           depth.current = 0;
           setRemoveReady(false);
           const name = e.dataTransfer.getData("application/x-mtg-deck-card");
           if (name) removeCard(name);
         }}>
      {removeReady && (
        <p className="muted drop-hint">Drop to remove from deck</p>
      )}
      <CardSearch
        onAdd={deck ? (c) => { addCard(c.name); } : undefined}
        membership={deck ? membershipFor : undefined}
        onDragCard={setDragCard}
        request={searchRequest}
        identityColors={deck?.color_identity}
      />
    </div>
  );
}

function UndoControl() {
  const { canUndo, undo } = useDeckWorkspace();
  if (!canUndo) return null;
  return (
    <button className="ghost" title="Undo the last deck change"
            onClick={() => undo()}>
      ↶ Undo
    </button>
  );
}

export default function Workspace() {
  return (
    <DeckWorkspaceProvider>
      <WorkspaceShell
        deckPane={<DeckPane />}
        searchPane={<SearchPane />}
        toolbarExtra={<UndoControl />}
      />
    </DeckWorkspaceProvider>
  );
}
