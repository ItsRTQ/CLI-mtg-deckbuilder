import { useEffect, useMemo, useRef, useState } from "react";
import { CardResult } from "../../api/mock";
import { DeckCard } from "../../api/decks";
import { CardZoom } from "../CardTile";
import { useDeckWorkspace } from "../../state/DeckWorkspaceContext";

// Goldfish opening hands from the current deck. The library is a snapshot of
// the deck at open time (commander excluded — it lives in the command zone),
// quantities expanded. London mulligan with the multiplayer free first
// mulligan (CR 103.5c): every mulligan redraws 7, then max(0, N-1) cards of
// the player's choice go to the BOTTOM of the library.

function shuffled<T>(src: T[]): T[] {
  const a = src.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export default function TestHandModal({ onClose }: { onClose: () => void }) {
  const { deck } = useDeckWorkspace();
  const pool = useMemo(() => {
    const out: DeckCard[] = [];
    for (const c of deck?.cards ?? []) {
      if (c.section === "commander") continue;
      for (let i = 0; i < c.quantity; i++) out.push(c);
    }
    return out;
  }, [deck]);

  const [hand, setHand] = useState<DeckCard[]>([]);
  const [library, setLibrary] = useState<DeckCard[]>([]);
  const [mulligans, setMulligans] = useState(0);
  const [toBottom, setToBottom] = useState(0);
  const [turnDraws, setTurnDraws] = useState(0);
  const [zoom, setZoom] = useState<CardResult | null>(null);
  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;

  function deal(mulls: number) {
    const lib = shuffled(pool);
    setHand(lib.slice(0, 7));
    setLibrary(lib.slice(7));
    setMulligans(mulls);
    // first mulligan is free (multiplayer CR 103.5c); clamp for tiny decks
    setToBottom(Math.min(Math.max(0, mulls - 1), Math.min(7, lib.length)));
    setTurnDraws(0);
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => deal(0), [pool]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (zoomRef.current) setZoom(null);
      else onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!deck) return null;

  const bottoming = toBottom > 0;
  const landsInHand = hand.filter((c) =>
    (c.type_line ?? "").toLowerCase().includes("land")).length;

  function bottomCard(at: number) {
    const card = hand[at];
    setLibrary((l) => [...l, card]);
    setHand((h) => h.filter((_, i) => i !== at));
    setToBottom((n) => n - 1);
  }

  function drawOne() {
    const [top, ...rest] = library;
    if (!top) return;
    setHand((h) => [...h, top]);
    setLibrary(rest);
    setTurnDraws((n) => n + 1);
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal wide" role="dialog" aria-modal="true"
           aria-label="Test hand" onClick={(e) => e.stopPropagation()}>
        <h2>Test hand — {deck.commander ?? deck.name}</h2>
        <div className="deck-stats">
          <span><strong>{hand.length}</strong> in hand</span>
          <span><strong>{landsInHand}</strong> land{landsInHand === 1 ? "" : "s"}</span>
          <span><strong>{library.length}</strong> in library</span>
          {mulligans > 0 && (
            <span><strong>{mulligans}</strong> mulligan{mulligans > 1 ? "s" : ""}</span>
          )}
          {turnDraws > 0 && <span><strong>+{turnDraws}</strong> drawn</span>}
        </div>
        {bottoming && (
          <p className="testhand-hint">
            Click {toBottom} card{toBottom > 1 ? "s" : ""} to put on the
            bottom of your library.
          </p>
        )}
        <div className={`mini-grid testhand-grid${bottoming ? " putting-back" : ""}`}>
          {hand.map((c, i) => (
            <div key={`${c.name}-${i}`} className="mini-card"
                 title={bottoming
                   ? `Put ${c.name} on the bottom`
                   : `${c.name}\n${c.type_line ?? ""}`}
                 onClick={() => (bottoming ? bottomCard(i) : setZoom(c))}>
              {c.image_url ? (
                <img src={c.image_url} alt={c.name}
                     loading="lazy" decoding="async" />
              ) : (
                <div className="mini-card-fallback">{c.name}</div>
              )}
            </div>
          ))}
          {hand.length === 0 && (
            <p className="muted">Deck is empty — nothing to draw.</p>
          )}
        </div>
        <div className="row testhand-actions">
          <button onClick={() => deal(mulligans + 1)}
                  disabled={pool.length === 0}
                  title="Redraw 7, then put back one card per mulligan past the first (free) one">
            ↻ Mulligan{mulligans > 0 ? ` (keep ${Math.max(0, 7 - mulligans)})` : " (free)"}
          </button>
          <button onClick={drawOne} disabled={bottoming || library.length === 0}
                  title="Draw the top card of the library (simulate a turn)">
            ➕ Draw
          </button>
          <button className="ghost" onClick={() => deal(0)}
                  disabled={pool.length === 0}>
            ⟲ New hand
          </button>
          <span style={{ flex: 1 }} />
          <button onClick={onClose}>Close</button>
        </div>
        {/* inside .modal so the zoom's close-click can't bubble to the
            overlay and close this modal too */}
        {zoom && <CardZoom card={zoom} onClose={() => setZoom(null)} />}
      </div>
    </div>
  );
}
