import { useState } from "react";
import { CardResult } from "../../api/mock";
import { DeckCard, SECTIONS } from "../../api/decks";
import { CardZoom } from "../CardTile";
import { useDeckWorkspace } from "../../state/DeckWorkspaceContext";
import QtyStepper from "./QtyStepper";

// Full card-image view: the Collection mini-grid pattern + always-on remove/
// stepper controls (the workspace IS edit mode).
export default function DeckViewGrid() {
  const { deck, removeCard, pendingNames } = useDeckWorkspace();
  const [zoom, setZoom] = useState<CardResult | null>(null);
  if (!deck) return null;

  const isBasic = (c: DeckCard) =>
    (c.type_line ?? "").toLowerCase().includes("basic");

  return (
    <div>
      {SECTIONS.map(([key, label]) => {
        const cards = deck.cards.filter((c) => c.section === key);
        if (cards.length === 0) return null;
        const n = cards.reduce((s, c) => s + c.quantity, 0);
        return (
          <div key={key} className="deck-section">
            <h4 className="deck-section-title">
              {label} <span className="muted">({n})</span>
            </h4>
            <div className="mini-grid">
              {cards.map((c) => {
                const pending = pendingNames.has(c.name.toLowerCase());
                return (
                  <div key={c.name}
                       className={`mini-card${pending ? " mini-pending" : ""}`}
                       title={`${c.name}\n${c.type_line ?? ""}${
                         key !== "commander" ? "\nDrag onto the search pane to remove" : ""}`}
                       draggable={key !== "commander" && !pending}
                       onDragStart={(e) => {
                         e.dataTransfer.setData("application/x-mtg-deck-card", c.name);
                         e.dataTransfer.effectAllowed = "move";
                       }}
                       onClick={() => setZoom(c)}>
                    {c.image_url ? (
                      <img src={c.image_url} alt={c.name}
                           loading="lazy" decoding="async" />
                    ) : (
                      <div className="mini-card-fallback">{c.name}</div>
                    )}
                    {c.quantity > 1 && (
                      <span className="qty-badge">×{c.quantity}</span>
                    )}
                    {key !== "commander" && (
                      <button className="mini-remove" disabled={pending}
                              title={`Remove ${c.name}`}
                              aria-label={`Remove ${c.name} from deck`}
                              onClick={(e) => {
                                e.stopPropagation();
                                removeCard(c.name);
                              }}>
                        ✕
                      </button>
                    )}
                    {key !== "commander" && isBasic(c) && (
                      <span className="mini-stepper">
                        <QtyStepper name={c.name} quantity={c.quantity} />
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
      {zoom && <CardZoom card={zoom} onClose={() => setZoom(null)} />}
    </div>
  );
}
