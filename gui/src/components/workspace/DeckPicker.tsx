import { useEffect, useState } from "react";
import { DeckSummary, listDecks } from "../../api/decks";
import CommanderInput from "../CommanderInput";
import { useDeckWorkspace } from "../../state/DeckWorkspaceContext";

// Empty state of the deck pane: open an existing library deck or create a
// fresh one (commander only — cards come from the search pane).
export default function DeckPicker() {
  const { openDeck, createNewDeck, loading, error } = useDeckWorkspace();
  const [decks, setDecks] = useState<DeckSummary[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [commander, setCommander] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    listDecks()
      .then((d) => setDecks(d.decks))
      .catch((e) => setListError(e.message));
  }, []);

  return (
    <div className="deck-picker">
      <h3>Open a deck</h3>
      {listError && <p className="error">{listError}</p>}
      {error && <p className="error">{error}</p>}
      {decks === null && !listError && <p className="muted">loading decks…</p>}
      {decks !== null && decks.length === 0 && (
        <p className="muted">No saved decks yet — create one below.</p>
      )}
      {decks !== null && decks.length > 0 && (
        <ul className="picker-list">
          {decks.map((d) => (
            <li key={d.name}>
              <button className="picker-row" disabled={loading}
                      onClick={() => openDeck(d.name)}>
                <strong>{d.commander ?? d.name}</strong>
                <span className="muted">
                  {d.card_count != null ? `${d.card_count} cards` : ""}
                  {d.rank ? ` · ${d.rank}` : ""}
                  {d.cost_usd != null ? ` · $${d.cost_usd}` : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <h3 style={{ marginTop: "1rem" }}>New deck</h3>
      <div className="row">
        <div style={{ flex: 1 }}>
          <CommanderInput value={commander} onChange={setCommander}
                          placeholder="Commander name…" />
        </div>
        <button disabled={!commander.trim() || creating || loading}
                onClick={async () => {
                  setCreating(true);
                  await createNewDeck(commander.trim());
                  setCreating(false);
                }}>
          {creating ? "…" : "Create"}
        </button>
      </div>
    </div>
  );
}
