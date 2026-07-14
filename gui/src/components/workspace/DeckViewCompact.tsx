import { useState } from "react";
import { CardResult } from "../../api/mock";
import { DeckCard, SECTIONS } from "../../api/decks";
import { CardZoom } from "../CardTile";
import ManaCost from "../ManaCost";
import { useDeckWorkspace } from "../../state/DeckWorkspaceContext";
import QtyStepper from "./QtyStepper";

// Compact list view: qty · name · mana cost · price · controls. Optimized for
// scanning density; click a row to zoom/research.
export default function DeckViewCompact() {
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
            <ul className="deck-rows">
              {cards.map((c) => {
                const pending = pendingNames.has(c.name.toLowerCase());
                return (
                  <li key={c.name}
                      className={`deck-row${pending ? " mini-pending" : ""}`}
                      title={key !== "commander"
                        ? "Drag onto the search pane to remove" : undefined}
                      draggable={key !== "commander" && !pending}
                      onDragStart={(e) => {
                        e.dataTransfer.setData("application/x-mtg-deck-card", c.name);
                        e.dataTransfer.effectAllowed = "move";
                      }}
                      onClick={() => setZoom(c)}>
                    <span className="deck-row-qty">{c.quantity}</span>
                    <span className="deck-row-name">{c.name}</span>
                    <span className="deck-row-mana">
                      <ManaCost cost={c.mana_cost} />
                    </span>
                    <span className="muted deck-row-price">
                      {c.usd_price != null ? `$${c.usd_price.toFixed(2)}` : ""}
                    </span>
                    {key !== "commander" && isBasic(c) && (
                      <QtyStepper name={c.name} quantity={c.quantity} />
                    )}
                    {key !== "commander" && (
                      <button className="row-remove" disabled={pending}
                              title={`Remove ${c.name}`}
                              aria-label={`Remove ${c.name} from deck`}
                              onClick={(e) => {
                                e.stopPropagation();
                                removeCard(c.name);
                              }}>
                        ✕
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
      {zoom && <CardZoom card={zoom} onClose={() => setZoom(null)} />}
    </div>
  );
}
