import { useEffect, useState } from "react";
import { marked } from "marked";
import { api } from "../api/client";
import { CardResult } from "../api/mock";
import { CardTile, CardZoom } from "../components/CardTile";
import CommanderInput from "../components/CommanderInput";
import AgentConfirm from "../components/AgentConfirm";
import { manaHtml } from "../components/ManaCost";
import { DeckDetail, Decks, SECTIONS } from "../api/decks";

interface Bulk {
  source: string;
  count: number;
  known_value: number;
  unknown_count: number;
  cards: CardResult[];
  always_free: string[];
}

const CHUNK = 30; // images rendered per "show more" click (big bulks stay light)

export default function Collection() {
  const [bulk, setBulk] = useState<Bulk | null>(null);
  const [decks, setDecks] = useState<Decks | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [shownCount, setShownCount] = useState(CHUNK);
  // deck = the open deck's name when the zoom came from a deck panel — the
  // chosen print then saves to THAT deck only (global prefs = the fallback).
  const [zoom, setZoom] = useState<{ card: CardResult; deck: string | null } | null>(null);
  const [decksOpen, setDecksOpen] = useState(false);
  const [openDeck, setOpenDeck] = useState<DeckDetail | null>(null);
  const [deckLoading, setDeckLoading] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [importCommander, setImportCommander] = useState("");
  const [importText, setImportText] = useState("");
  const [importBusy, setImportBusy] = useState(false);
  const [importMsg, setImportMsg] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [bulkImportOpen, setBulkImportOpen] = useState(false);
  const [bulkImportText, setBulkImportText] = useState("");
  const [bulkImportBusy, setBulkImportBusy] = useState(false);
  const [bulkImportMsg, setBulkImportMsg] = useState<string | null>(null);
  const [bulkImportError, setBulkImportError] = useState<string | null>(null);
  // deck creation (the "+ New deck" side panel)
  const [newDeckOpen, setNewDeckOpen] = useState(false);
  const [newCommander, setNewCommander] = useState("");
  const [newText, setNewText] = useState("");
  const [newBusy, setNewBusy] = useState(false);
  const [newError, setNewError] = useState<string | null>(null);
  // deck editing (inside the open deck panel)
  const [editMode, setEditMode] = useState(false);
  const [editText, setEditText] = useState<string | null>(null); // null = card mode
  const [addName, setAddName] = useState("");
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  useEffect(() => {
    api<Bulk>("/api/bulk").then(setBulk).catch((e) => setError(e.message));
    api<Decks>("/api/decks").then(setDecks).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    setShownCount(CHUNK); // new filter -> restart the visible window
  }, [filter]);

  function resetEditState() {
    setEditMode(false);
    setEditText(null);
    setEditError(null);
    setAddName("");
  }

  async function toggleDeck(name: string) {
    setImportOpen(false);  // the side panel is either a deck, the importer or the creator
    setNewDeckOpen(false);
    setCopied(false);
    setExplainOpen(false);
    setExMsg(null);
    resetEditState();
    if (openDeck?.name === name || deckLoading === name) {
      setOpenDeck(null);
      setDeckLoading(null);
      return;
    }
    // the panel opens IMMEDIATELY with a loader (the width transition runs while
    // we fetch), and the heavy card grid mounts on the next frame — no jank
    setOpenDeck(null);
    setDeckLoading(name);
    try {
      const detail = await api<DeckDetail>(`/api/decks/${encodeURIComponent(name)}`);
      requestAnimationFrame(() => {
        setOpenDeck(detail);
        setDeckLoading(null);
      });
    } catch (e: any) {
      setError(e.message);
      setDeckLoading(null);
    }
  }

  function openImporter() {
    setOpenDeck(null);       // takes over the side panel
    setDeckLoading(null);
    setNewDeckOpen(false);
    setImportMsg(null);
    setImportError(null);
    resetEditState();
    setImportOpen(true);
  }

  function openNewDeck() {
    setOpenDeck(null);       // takes over the side panel
    setDeckLoading(null);
    setImportOpen(false);
    setNewError(null);
    resetEditState();
    setNewDeckOpen(true);
  }

  // Every mutation re-fetches with the name from the RESPONSE — edits recompute
  // the cost/tier/rank tokens and may rename the deck's folder.
  async function refreshDeck(newName: string) {
    setDecks(await api<Decks>("/api/decks"));
    setOpenDeck(await api<DeckDetail>(`/api/decks/${encodeURIComponent(newName)}`));
  }

  async function createDeck() {
    setNewBusy(true);
    setNewError(null);
    try {
      const res = await api<{ build_name: string }>("/api/decks", {
        method: "POST",
        body: JSON.stringify({ commander: newCommander, decklist: newText }),
      });
      setNewDeckOpen(false);
      setNewCommander("");
      setNewText("");
      setDecks(await api<Decks>("/api/decks"));
      await toggleDeck(res.build_name);   // open the fresh deck right away
    } catch (e: any) {
      setNewError(e.message);
    } finally {
      setNewBusy(false);
    }
  }

  async function patchCards(payload: { add?: string[]; remove?: string[] }) {
    if (!openDeck) return;
    setEditBusy(true);
    setEditError(null);
    try {
      const res = await api<{ name: string }>(
        `/api/decks/${encodeURIComponent(openDeck.name)}/cards`,
        { method: "PATCH", body: JSON.stringify(payload) });
      setAddName("");
      await refreshDeck(res.name);
    } catch (e: any) {
      setEditError(e.message);
    } finally {
      setEditBusy(false);
    }
  }

  async function saveTextEdit() {
    if (!openDeck || editText == null) return;
    setEditBusy(true);
    setEditError(null);
    try {
      const res = await api<{ name: string; skipped: string[] }>(
        `/api/decks/${encodeURIComponent(openDeck.name)}/list`,
        { method: "PUT", body: JSON.stringify({ decklist: editText }) });
      setEditText(null);
      await refreshDeck(res.name);
      if (res.skipped.length) {
        setEditError(`skipped (not found): ${res.skipped.join(", ")}`);
      }
    } catch (e: any) {
      setEditError(e.message);
    } finally {
      setEditBusy(false);
    }
  }

  async function copyDecklist() {
    if (!openDeck) return;
    try {
      await navigator.clipboard.writeText(openDeck.decklist);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (e: any) {
      setError(`copy failed: ${e.message}`);
    }
  }

  const [explainOpen, setExplainOpen] = useState(false);
  const [exTheme, setExTheme] = useState("");
  const [exCombos, setExCombos] = useState("");
  const [exNotes, setExNotes] = useState("");
  const [exMsg, setExMsg] = useState<string | null>(null);
  const [exBusy, setExBusy] = useState(false);
  const [exConfirm, setExConfirm] = useState(false);

  // ONE agent job at a time (build OR explain) — the backend 409s anyway; this
  // keeps the UI honest before the click.
  async function agentBusyMessage(): Promise<string | null> {
    const { agentBusyMessage: busy } = await import("../api/builds");
    return busy();
  }

  async function runExplain() {
    if (!openDeck) return;
    setExBusy(true);
    setExMsg(null);
    const busy = await agentBusyMessage();
    if (busy) {
      setExMsg(`✗ ${busy}`);
      setExBusy(false);
      return;
    }
    try {
      const res = await api<{ job_id: string }>(
        `/api/decks/${encodeURIComponent(openDeck.name)}/explain`, {
          method: "POST",
          body: JSON.stringify({
            theme: exTheme.trim() || null,
            combos: exCombos.trim() || null,
            notes: exNotes.trim() || null,
          }),
        });
      setExMsg(`✓ agent started (job ${res.job_id}) — watch the top-right banner; ` +
               "reopen this deck when it finishes.");
      setExplainOpen(false);
      setExTheme(""); setExCombos(""); setExNotes("");
    } catch (e: any) {
      setExMsg(`✗ ${e.message}`);
    } finally {
      setExBusy(false);
    }
  }

  async function deleteDeck() {
    if (!openDeck) return;
    if (!window.confirm(
      `Delete "${openDeck.commander ?? openDeck.name}" from your decks?\n` +
      "This removes the deck folder (decklist + explanation) permanently.")) return;
    try {
      await api(`/api/decks/${encodeURIComponent(openDeck.name)}`, { method: "DELETE" });
      setOpenDeck(null);
      setDecks(await api<Decks>("/api/decks"));
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function runBulkImport() {
    setBulkImportBusy(true);
    setBulkImportMsg(null);
    setBulkImportError(null);
    try {
      const res = await api<{ added: string[]; already_owned: string[]; skipped: string[]; count: number }>(
        "/api/bulk/import", {
          method: "POST",
          body: JSON.stringify({ text: bulkImportText }),
        });
      setBulkImportMsg(`✓ added ${res.added.length} card(s) — collection now ${res.count}`
        + (res.already_owned.length ? ` · ${res.already_owned.length} already owned` : "")
        + (res.skipped.length ? ` · skipped ${res.skipped.length}: ${res.skipped.slice(0, 6).join(", ")}${res.skipped.length > 6 ? "…" : ""}` : ""));
      setBulkImportText("");
      setBulk(await api<Bulk>("/api/bulk"));   // refresh the grid
    } catch (e: any) {
      setBulkImportError(e.message);
    } finally {
      setBulkImportBusy(false);
    }
  }

  async function runImport() {
    setImportBusy(true);
    setImportMsg(null);
    setImportError(null);
    try {
      const res = await api<{ build_name: string; imported: number; skipped: string[] }>(
        "/api/decks/import", {
          method: "POST",
          body: JSON.stringify({ commander: importCommander, decklist: importText }),
        });
      setImportMsg(`✓ imported ${res.imported} entries as "${res.build_name}"`
        + (res.skipped.length ? ` — skipped ${res.skipped.length}: ${res.skipped.slice(0, 6).join(", ")}` : ""));
      setImportCommander("");
      setImportText("");
      setDecks(await api<Decks>("/api/decks"));   // refresh the banners
    } catch (e: any) {
      setImportError(e.message);
    } finally {
      setImportBusy(false);
    }
  }

  const filtered = bulk?.cards.filter(
    (c) => !filter.trim() || c.name.toLowerCase().includes(filter.toLowerCase()),
  ) ?? [];
  const visible = filtered.slice(0, shownCount);

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1>Collection</h1>
        <button onClick={() => setDecksOpen(true)}>
          🃏 Decks{decks ? ` (${decks.decks.length})` : ""}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>Your bulk (owned cards)</h2>
          <button className="ghost" onClick={() => {
            setBulkImportMsg(null);
            setBulkImportError(null);
            setBulkImportOpen(!bulkImportOpen);
          }}
                  title="Paste a plain-text card list to add it to your collection">
            ⬇ Import list
          </button>
        </div>
        {bulkImportOpen && (
          <div className="advanced">
            <p className="muted" style={{ marginTop: 0 }}>
              Paste a plain-text list (one card per line — "1 Sol Ring",
              "Sol Ring" and Moxfield export lines all work; set/collector tags
              are stripped). Quantities are ignored: the collection tracks
              ownership, all copies of an owned card are free. Unknown names
              are skipped and reported, never invented.
            </p>
            <textarea rows={10} value={bulkImportText}
                      onChange={(e) => setBulkImportText(e.target.value)}
                      placeholder={"1 Sol Ring\nArcane Signet (C21) 263 *F*\nRhystic Study\n..."} />
            {bulkImportError && <p className="error">{bulkImportError}</p>}
            {bulkImportMsg && <p className="muted">{bulkImportMsg}</p>}
            <p style={{ marginBottom: 0 }}>
              <button disabled={!bulkImportText.trim() || bulkImportBusy}
                      onClick={runBulkImport}>
                {bulkImportBusy ? "importing…" : "Add to my collection"}
              </button>
            </p>
          </div>
        )}
        {!bulk ? (
          <p className="muted">loading…</p>
        ) : (
          <>
            <p className="muted">
              {bulk.count} cards · known value ${bulk.known_value.toFixed(2)}
              {bulk.unknown_count > 0 && ` (${bulk.unknown_count} unpriced)`}
              — owned cards cost $0 in every build. Always free:{" "}
              {bulk.always_free.join(", ")}.
              <br />
              source: <code>{bulk.source}</code>
            </p>
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="filter…"
            />
            {bulk.count === 0 ? (
              <p className="muted" style={{ marginTop: "0.6rem" }}>
                Collection is empty — paste a list with "⬇ Import list" above,
                drag cards here from the Home search, use{" "}
                <code>mtg bulk-add</code>, or point Settings → Card collection
                folder at your list.
              </p>
            ) : (
              <>
                <div className="card-grid" style={{ marginTop: "0.8rem" }}>
                  {visible.map((c) => (
                    <CardTile key={c.name} card={c} onZoom={() => setZoom({ card: c, deck: null })} />
                  ))}
                </div>
                {filtered.length > shownCount && (
                  <p style={{ textAlign: "center", marginBottom: 0 }}>
                    <button className="ghost"
                            onClick={() => setShownCount(shownCount + CHUNK)}>
                      show more ({filtered.length - shownCount} left)
                    </button>
                  </p>
                )}
              </>
            )}
          </>
        )}
      </div>
      {zoom && (
        <CardZoom
          card={zoom.card}
          onClose={() => setZoom(null)}
          // Collection/deck context: the chosen printing PERSISTS — to the open
          // DECK when zoomed from a deck panel, globally (gui_prints) otherwise.
          onSavePrint={async (p) => {
            const body = JSON.stringify({
              set: p.set, collector_number: p.collector_number,
              rarity: p.rarity, image_url: p.thumb,
            });
            try {
              if (zoom.deck) {
                await api(`/api/decks/${encodeURIComponent(zoom.deck)}` +
                          `/prints/${encodeURIComponent(zoom.card.name)}`,
                          { method: "PUT", body });
                // deck prefs never touch the bulk grid — refresh the deck only
                if (openDeck) {
                  setOpenDeck(await api<DeckDetail>(
                    `/api/decks/${encodeURIComponent(openDeck.name)}`));
                }
              } else {
                await api(`/api/prints/${encodeURIComponent(zoom.card.name)}`,
                          { method: "PUT", body });
                // refresh the grids so the new art shows everywhere the global
                // fallback applies (decks without their own pref included)
                setBulk(await api<Bulk>("/api/bulk"));
                if (openDeck) {
                  setOpenDeck(await api<DeckDetail>(
                    `/api/decks/${encodeURIComponent(openDeck.name)}`));
                }
              }
            } catch {
              /* persisting is best-effort — the zoom keeps cycling regardless */
            }
          }}
        />
      )}
      {decksOpen && (
        <div className="modal-overlay" onClick={() => setDecksOpen(false)}>
          <div className={`modal wide${openDeck || deckLoading || importOpen || newDeckOpen ? " expanded" : ""}`}
               onClick={(e) => e.stopPropagation()}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h2 style={{ margin: 0 }}>Your decks</h2>
              <button className="banner-close" onClick={() => setDecksOpen(false)}>✕</button>
            </div>
            {!decks ? (
              <p className="muted">loading…</p>
            ) : decks.dir === null ? (
              <p className="muted">
                Library saving is OFF — set a Build save folder in Settings.
              </p>
            ) : (
              <div className="decks-body">
                <div className="decks-list">
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <p className="muted" style={{ margin: 0 }}>
                      {decks.decks.length} deck(s) in <code>{decks.dir}</code>
                    </p>
                    <span className="row" style={{ gap: "0.4rem" }}>
                      <button className="ghost" onClick={openNewDeck}
                              title="Create a deck by hand (pick a commander, add cards)">
                        + New deck
                      </button>
                      <button className="ghost" onClick={openImporter}
                              title="Paste a decklist (e.g. a Moxfield export) into your library">
                        ⬇ Import
                      </button>
                    </span>
                  </div>
                  {decks.decks.length === 0 && (
                    <p className="muted">
                      No decks yet in <code>{decks.dir}</code> — build one, import
                      one, or start one by hand with "+ New deck".
                    </p>
                  )}
                  <div className="deck-banners">
                    {decks.decks.map((d) => (
                      <div
                        key={d.name}
                        className={`deck-banner rank-${(d.rank ?? "none").toLowerCase()}${openDeck?.name === d.name || deckLoading === d.name ? " selected" : ""}`}
                        style={d.art_url
                          ? { backgroundImage: `url(${d.art_url})` }
                          : undefined}
                        onClick={() => toggleDeck(d.name)}
                        title={d.name}
                      >
                        <div className="deck-banner-scrim">
                          {d.tier && <span className="deck-tier">{d.tier}</span>}
                          <span className="deck-commander">
                            {d.commander ?? d.name}
                          </span>
                          <span className="deck-meta">
                            {d.rank && <span className="deck-rank">{d.rank}</span>}
                            {d.cost_usd != null && <span>${d.cost_usd}</span>}
                            {d.card_count != null && (
                              <span className="muted">{d.card_count} cards</span>
                            )}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                {deckLoading && (
                  <div className="deck-panel deck-panel-loading">
                    <span className="spinner" />
                    <span className="muted">loading deck…</span>
                  </div>
                )}
                {importOpen && (
                  <div className="deck-panel">
                    <h3 style={{ marginTop: 0 }}>Import a deck</h3>
                    <p className="muted">
                      Paste a plain-text decklist (one card per line, Moxfield
                      export format works — set/collector tags are stripped).
                      Unknown names are skipped and reported, never invented.
                    </p>
                    <label>Commander *</label>
                    <CommanderInput value={importCommander}
                                    onChange={setImportCommander}
                                    placeholder="Start typing — suggestions are commanders only" />
                    <label>Decklist</label>
                    <textarea rows={14} value={importText}
                              onChange={(e) => setImportText(e.target.value)}
                              placeholder={"1 Sol Ring\n1 Arcane Signet\n32 Mountain\n..."} />
                    {importError && <p className="error">{importError}</p>}
                    {importMsg && <p className="muted">{importMsg}</p>}
                    <p>
                      <button disabled={!importCommander.trim() || !importText.trim() || importBusy}
                              onClick={runImport}>
                        {importBusy ? "importing…" : "Import to my decks"}
                      </button>
                    </p>
                  </div>
                )}
                {newDeckOpen && (
                  <div className="deck-panel">
                    <h3 style={{ marginTop: 0 }}>New deck</h3>
                    <p className="muted">
                      Pick a commander and start empty (add cards with ✏️ Edit
                      afterwards), or paste a starting list right away. Every
                      card is validated on entry — color identity, singleton,
                      deck size.
                    </p>
                    <label>Commander *</label>
                    <CommanderInput value={newCommander}
                                    onChange={setNewCommander}
                                    placeholder="Start typing — suggestions are commanders only" />
                    <label>Starting list (optional)</label>
                    <textarea rows={10} value={newText}
                              onChange={(e) => setNewText(e.target.value)}
                              placeholder={"empty = fresh deck\n\n1 Sol Ring\n32 Mountain\n..."} />
                    {newError && <p className="error" style={{ whiteSpace: "pre-wrap" }}>{newError}</p>}
                    <p>
                      <button disabled={!newCommander.trim() || newBusy}
                              onClick={createDeck}>
                        {newBusy ? "creating…" : "Create deck"}
                      </button>
                    </p>
                  </div>
                )}
                {openDeck && !deckLoading && (
                  <div className="deck-panel">
                    <div className="row" style={{ justifyContent: "space-between" }}>
                      <h3 style={{ margin: 0 }}>{openDeck.commander ?? openDeck.name}</h3>
                      <span className="row" style={{ gap: "0.4rem" }}>
                        <button className="ghost" disabled={editText != null}
                                onClick={() => {
                                  setEditMode(!editMode);
                                  setEditText(null);
                                  setEditError(null);
                                }}
                                title="Add/remove cards — every change is validated (color identity, singleton, size)">
                          {editMode ? "✓ Done" : "✏️ Edit"}
                        </button>
                        <button className="ghost" onClick={copyDecklist}
                                title="Copy the plain-text decklist (paste into Moxfield etc.)">
                          {copied ? "✓ copied" : "📋 Copy"}
                        </button>
                        <button className="ghost danger" style={{ marginLeft: 0 }}
                                onClick={deleteDeck} title="Delete this deck from your library">
                          🗑 Delete
                        </button>
                      </span>
                    </div>
                    {editText != null ? (
                      <div>
                        <p className="muted">
                          One card per line ("2 Mountain" for basics). Saving
                          replaces the whole list — annotations survive for
                          cards that stay; unknown names are skipped and
                          reported, never invented.
                        </p>
                        <textarea rows={18} value={editText}
                                  onChange={(e) => setEditText(e.target.value)} />
                        {editError && (
                          <p className="error" style={{ whiteSpace: "pre-wrap" }}>{editError}</p>
                        )}
                        <p>
                          <button disabled={editBusy || !editText.trim()}
                                  onClick={saveTextEdit}>
                            {editBusy ? "saving…" : "Save list"}
                          </button>{" "}
                          <button className="ghost"
                                  onClick={() => { setEditText(null); setEditError(null); }}>
                            Cancel
                          </button>
                        </p>
                      </div>
                    ) : (
                    <>
                    {editMode && (
                      <div style={{ margin: "0.6rem 0" }}>
                        <div className="row" style={{ gap: "0.4rem", alignItems: "stretch" }}>
                          <div style={{ flex: 1 }}>
                            <CommanderInput commandersOnly={false}
                                            value={addName} onChange={setAddName}
                                            placeholder="Add a card — type to search the DB" />
                          </div>
                          <button disabled={!addName.trim() || editBusy}
                                  onClick={() => patchCards({ add: [addName.trim()] })}>
                            {editBusy ? "…" : "+ Add"}
                          </button>
                          <button className="ghost"
                                  onClick={() => { setEditText(openDeck.decklist); setEditError(null); }}
                                  title="Edit the whole list as plain text (also the recovery path for decks that refuse incremental edits)">
                            Edit as text
                          </button>
                        </div>
                      </div>
                    )}
                    {editError && (
                      <p className="error" style={{ whiteSpace: "pre-wrap" }}>{editError}</p>
                    )}
                    {SECTIONS.map(([key, label]) => {
                      const cards = openDeck.cards.filter((c) => c.section === key);
                      if (cards.length === 0) return null;
                      const n = cards.reduce((s, c) => s + c.quantity, 0);
                      return (
                        <div key={key} className="deck-section">
                          <h4 className="deck-section-title">
                            {label} <span className="muted">({n})</span>
                          </h4>
                          <div className="mini-grid">
                            {cards.map((c) => (
                              <div key={c.name} className="mini-card"
                                   title={`${c.name}\n${c.type_line ?? ""}`}
                                   onClick={() => setZoom({ card: c, deck: openDeck.name })}>
                                {c.image_url ? (
                                  <img src={c.image_url} alt={c.name}
                                       loading="lazy" decoding="async" />
                                ) : (
                                  <div className="mini-card-fallback">{c.name}</div>
                                )}
                                {c.quantity > 1 && (
                                  <span className="qty-badge">×{c.quantity}</span>
                                )}
                                {editMode && key !== "commander" && (
                                  <button className="mini-remove" disabled={editBusy}
                                          title={`Remove ${c.name}${c.quantity > 1 ? " (removes 1 copy)" : ""}`}
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            patchCards({ remove: [c.name] });
                                          }}>
                                    ✕
                                  </button>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                    <div className="deck-stats">
                      <span><strong>{openDeck.stats.total_cards}</strong> cards</span>
                      <span><strong>${openDeck.stats.known_price.toFixed(2)}</strong> known price</span>
                      {openDeck.stats.avg_mv_nonland != null && (
                        <span><strong>{openDeck.stats.avg_mv_nonland}</strong> avg MV (nonland)</span>
                      )}
                      {SECTIONS.filter(([k]) => openDeck.stats.section_counts[k])
                        .map(([k, label]) => (
                          <span key={k} className="muted">
                            {label.toLowerCase()}: {openDeck.stats.section_counts[k]}
                          </span>
                        ))}
                    </div>
                    <details style={{ marginTop: "0.6rem" }}>
                      <summary className="muted">explanation</summary>
                      {openDeck.explanation ? (
                        <div
                          className="prose"
                          // local, user-authored markdown (the build's own explanation
                          // file); {R}-style tokens become inline mana symbols
                          dangerouslySetInnerHTML={{
                            __html: manaHtml(marked.parse(openDeck.explanation) as string),
                          }}
                        />
                      ) : (
                        <div style={{ marginTop: "0.5rem" }}>
                          <p className="muted" style={{ marginTop: 0 }}>
                            This deck has no explanation yet — your AI agent can
                            study it, annotate it (purposes + combos) and write one.
                          </p>
                          {exMsg && <p className="muted">{exMsg}</p>}
                          {!explainOpen ? (
                            <button onClick={async () => {
                              setExMsg(null);
                              const busy = await agentBusyMessage();
                              if (busy) {
                                setExMsg(`✗ ${busy}`);
                                return;
                              }
                              setExplainOpen(true);
                            }}>
                              ✨ Explain
                            </button>
                          ) : (
                            <div className="advanced">
                              <p className="muted" style={{ marginTop: 0 }}>
                                A few optional questions — your answers give the
                                agent context, so it verifies instead of guessing.
                                Uses your provider's quota (~2-5 min).
                              </p>
                              <label>What's the deck's plan / theme?</label>
                              <input value={exTheme} onChange={(e) => setExTheme(e.target.value)}
                                     placeholder='e.g. "goblin swarm, win with Impact Tremors" (empty = let it figure it out)' />
                              <label>Known combos (separate cards with ;)</label>
                              <input value={exCombos} onChange={(e) => setExCombos(e.target.value)}
                                     placeholder='e.g. "Kiki-Jiki + Zealous Conscripts"' />
                              <label>Anything else the agent should know?</label>
                              <input value={exNotes} onChange={(e) => setExNotes(e.target.value)}
                                     placeholder="pet cards, meta, what to highlight..." />
                              <p style={{ marginBottom: 0 }}>
                                <button disabled={exBusy} onClick={() => setExConfirm(true)}>
                                  {exBusy ? "starting…" : "✨ Run agent"}
                                </button>
                              </p>
                              {exConfirm && (
                                <AgentConfirm
                                  action={`Annotate & explain "${openDeck.commander ?? openDeck.name}"`}
                                  onClose={() => setExConfirm(false)}
                                  onConfirm={() => {
                                    setExConfirm(false);
                                    runExplain();
                                  }}
                                />
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </details>
                    </>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
