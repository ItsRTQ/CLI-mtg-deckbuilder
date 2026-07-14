import { memo, useEffect, useRef, useState } from "react";
import { CardResult } from "../api/mock";
import {
  fetchPrintings, Printing, printingPriceLabel, scanId,
} from "../api/printings";
import { applyCardLight, resetCardLight } from "../fx/cardLight";
import ManaCost, { TextWithMana } from "./ManaCost";

// Printings now live in api/printings.ts — re-export so existing imports keep
// working (CardTile stays the visual module).
export type { Printing } from "../api/printings";

// Shared card visuals: grid tile (3D wobble + click-to-zoom + draggable) and the
// zoom modal. Used by the Home search, the Collection bulk grid and the
// workspace search pane (which adds deck-membership overlays + an add action).

export type MembershipState = "none" | "in" | "limit" | "illegal";
export interface Membership {
  state: MembershipState;
  quantity: number;        // copies in the deck (basics can exceed 1)
  pending?: boolean;       // a mutation for this card is in flight
}

interface CardTileProps {
  card: CardResult;
  onZoom: () => void;
  /** Deck-membership visual state (workspace search pane). */
  overlay?: Membership;
  /** Renders a small "+" button — the mandatory click/keyboard add path. */
  action?: { title: string; onClick: () => void; disabled?: boolean };
  /** Relays dragstart/dragend so a drop target can preview validity
   * (dataTransfer is unreadable during dragover). */
  onDragCard?: (card: CardResult | null) => void;
}

const OVERLAY_TITLE: Record<MembershipState, string> = {
  none: "",
  in: "In deck",
  limit: "Copy limit reached (singleton)",
  illegal: "Outside the deck's color identity",
};

function CardTileImpl({ card, onZoom, overlay, action, onDragCard }: CardTileProps) {
  const [broken, setBroken] = useState(false);
  const tiltRef = useRef<HTMLDivElement>(null);
  const price = card.usd_price != null ? `$${card.usd_price.toFixed(2)}` : "$?";
  const ov = overlay && overlay.state !== "none" ? overlay : null;
  const stateTitle = ov
    ? `${OVERLAY_TITLE[ov.state]}${ov.state === "in" && ov.quantity > 1 ? ` ×${ov.quantity}` : ""} · `
    : "";

  // 3D wobble following the cursor (styles set directly on the node — no React
  // re-render per mousemove). The pointer orients the CARD; fx/cardLight.ts
  // derives where the fixed virtual light reflects from that orientation.
  function onMove(e: React.MouseEvent) {
    const el = tiltRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width - 0.5) * 2;   // -1..1
    const py = ((e.clientY - r.top) / r.height - 0.5) * 2;
    applyCardLight(el, px, py, { maxTilt: 8, perspective: 650, scale: 1.07 });
  }
  function onLeave() {
    if (tiltRef.current) resetCardLight(tiltRef.current);
  }

  return (
    <figure className={`mtg-card ${card.rarity ? `fx-${card.rarity.toLowerCase()}` : ""}`
              + (ov ? (ov.state === "illegal" ? " deck-illegal" : " in-deck") : "")}
            title={`${stateTitle}Click to enlarge · drag onto the deck or Collection to add`}
            onClick={onZoom} onMouseMove={onMove} onMouseLeave={onLeave}
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData("application/x-mtg-card", card.name);
              e.dataTransfer.setData("text/plain", card.name);
              e.dataTransfer.effectAllowed = "copy";
              onLeave(); // reset the tilt so the drag ghost isn't skewed
              onDragCard?.(card);
            }}
            onDragEnd={() => onDragCard?.(null)}>
      <div className="tilt" ref={tiltRef}>
        {card.image_url && !broken ? (
          <img src={card.image_url} alt={card.name} loading="lazy"
               onError={() => setBroken(true)} />
        ) : (
          <div className="mtg-card-fallback">
            <strong>{card.name}</strong>
            <ManaCost cost={card.mana_cost} />
            <span className="muted">{card.type_line ?? ""}</span>
          </div>
        )}
        {ov && (
          <span
            className={`tile-chip tile-chip-${ov.state}`}
            aria-label={OVERLAY_TITLE[ov.state]}
          >
            {ov.state === "illegal" ? "🚫"
              : ov.state === "limit" ? "✓ 1/1"
              : ov.quantity > 1 ? `✓ ×${ov.quantity}` : "✓"}
          </span>
        )}
      </div>
      <figcaption>
        <span className="mtg-card-name">{card.name}</span>
        <span className="muted">{price}</span>
        {action && (
          <button
            className="tile-add"
            title={action.title}
            aria-label={`${action.title}: ${card.name}`}
            disabled={action.disabled || ov?.pending}
            onClick={(e) => {
              e.stopPropagation();
              action.onClick();
            }}
          >
            {ov?.pending ? "…" : "+"}
          </button>
        )}
      </figcaption>
    </figure>
  );
}

// Memoized: deck mutations restyle only the tiles whose membership changed.
// The compare deliberately IGNORES handler identity (onZoom/onDragCard/
// action.onClick) — handlers must not close over state that can change while
// `card` and `overlay` stay the same.
export const CardTile = memo(CardTileImpl, (a, b) =>
  a.card === b.card &&
  a.overlay?.state === b.overlay?.state &&
  a.overlay?.quantity === b.overlay?.quantity &&
  a.overlay?.pending === b.overlay?.pending &&
  !!a.action === !!b.action &&
  a.action?.disabled === b.action?.disabled &&
  a.action?.title === b.action?.title);

// Scryfall serves the same scan in several sizes — swap the path segment for the
// high-res version (fall back to the normal one if it 404s).
export function largeImageUrl(url: string): string {
  return url.replace("/normal/", "/large/");
}

// CSS class list for a printing's finish/treatment (see the fx system in styles.css)
export function treatmentClasses(p: Printing | null, fallbackRarity?: string | null): string {
  const cls: string[] = [];
  const r = (p?.rarity ?? fallbackRarity ?? "").toLowerCase();
  if (r) cls.push(`fx-${r}`);
  if (!p) return cls.join(" ");
  const promos = p.promo_types ?? [];
  const fins = p.finishes ?? [];
  const foilOnly = fins.includes("foil") && !fins.includes("nonfoil");
  if (promos.includes("surgefoil")) cls.push("fx-foil", "fx-surge");
  else if (promos.includes("galaxyfoil")) cls.push("fx-foil", "fx-galaxy");
  else if (promos.includes("confettifoil")) cls.push("fx-foil", "fx-confetti");
  else if (promos.includes("texturedfoil")) cls.push("fx-foil", "fx-textured");
  else if (fins.includes("etched") && !fins.includes("nonfoil")) cls.push("fx-etched");
  else if (foilOnly) cls.push("fx-foil");
  else cls.push("fx-nonfoil");
  const isFoilish = cls.some((c) => c === "fx-foil" || c === "fx-etched");
  if (isFoilish) {
    if (p.border_color === "borderless") cls.push("fx-borderless");
    if ((p.frame_effects ?? []).includes("showcase")) cls.push("fx-showcase");
    if (p.frame === "1997") cls.push("fx-retro");
  }
  return cls.join(" ");
}

export function CardZoom({ card, onClose, onSavePrint }: {
  card: CardResult;
  onClose: () => void;
  onSavePrint?: (p: Printing) => void;   // present = the chosen print persists
}) {
  const [useNormal, setUseNormal] = useState(false);
  const tiltRef = useRef<HTMLDivElement>(null);
  const [prints, setPrints] = useState<Printing[] | null>(null);
  const [idx, setIdx] = useState(-1);    // -1 = still showing the card's own art

  useEffect(() => {
    let stop = false;
    fetchPrintings(card.name)
      .then((ps) => {
        if (stop) return;
        setPrints(ps);
        const cur = scanId(card.image_url);
        const at = cur ? ps.findIndex((p) => scanId(p.image) === cur) : -1;
        if (at >= 0) setIdx(at);
      })
      .catch(() => !stop && setPrints([]));
    return () => {
      stop = true;
    };
  }, [card.name, card.image_url]);

  const current = prints && idx >= 0 ? prints[idx] : null;
  // Card's own art → the DB price as always; a cycled printing → ITS price
  // (with the "n/a — found $X" fallback to the regular DB price).
  const price = current
    ? printingPriceLabel(current, card.usd_price)
    : card.usd_price != null ? `$${card.usd_price.toFixed(2)}` : "$?";
  const src = current
    ? current.image
    : card.image_url
      ? (useNormal ? card.image_url : largeImageUrl(card.image_url))
      : null;

  // Print switching: the side arrows step forward/backward (wrapping); from the
  // card's own art (-1), back lands on the LAST printing.
  function stepPrint(dir: 1 | -1) {
    if (!prints || prints.length < 2) return;
    const next = (Math.max(idx, 0) + dir + prints.length) % prints.length;
    setIdx(next);
    onSavePrint?.(prints[next]);
  }

  // same lighting model as the grid tiles, gentler angle (the card is huge)
  function onMove(e: React.MouseEvent) {
    const el = tiltRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width - 0.5) * 2;   // -1..1
    const py = ((e.clientY - r.top) / r.height - 0.5) * 2;
    applyCardLight(el, px, py, { maxTilt: 5, perspective: 1200 });
  }
  function onLeave() {
    if (tiltRef.current) resetCardLight(tiltRef.current);
  }

  return (
    // zoom-overlay: above every other modal (a card zoom can be opened FROM the
    // decks modal — same z-index would paint it behind)
    <div className="modal-overlay zoom-overlay" onClick={onClose}>
      <div className={`zoom-card ${treatmentClasses(current, card.rarity)}`}
           onClick={(e) => e.stopPropagation()}>
        <div className="zoom-stage">
          <div className="tilt" ref={tiltRef} onMouseMove={onMove} onMouseLeave={onLeave}>
            {src ? (
              <img src={src} alt={card.name} onClick={onClose}
                   onError={() => (useNormal || current ? onClose() : setUseNormal(true))} />
            ) : (
              <div className="mtg-card-fallback" style={{ width: "min(420px, 80vw)" }}>
                <strong>{card.name}</strong>
                <ManaCost cost={card.mana_cost} />
                <span className="muted">{card.type_line ?? ""}</span>
                <span><TextWithMana text={card.oracle_text} /></span>
              </div>
            )}
          </div>
          {prints && prints.length > 1 && (
            <>
              <button className="zoom-nav prev" title="Previous printing"
                      onClick={() => stepPrint(-1)}>‹</button>
              <button className="zoom-nav next" title="Next printing"
                      onClick={() => stepPrint(1)}>›</button>
            </>
          )}
        </div>
        <div className="zoom-caption">
          <strong>{card.name}</strong>
          {card.mana_cost && <span><ManaCost cost={card.mana_cost} /></span>}
          <span className="muted">{card.type_line ?? ""}</span>
          <span>{price}</span>
          {prints && prints.length > 1 && (
            <span className="muted">
              {current?.set ? `${current.set} #${current.collector_number} · ` : ""}
              {current?.rarity && (
                <span className={`rarity-tag rarity-${current.rarity}`}>
                  {current.rarity}
                </span>
              )}
              {current?.rarity ? " · " : ""}
              print {Math.max(idx, 0) + 1}/{prints.length} — ‹ › to switch
              {onSavePrint ? " (saved)" : ""}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
