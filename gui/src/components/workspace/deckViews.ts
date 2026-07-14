import type { ComponentType } from "react";
import DeckViewGrid from "./DeckViewGrid";
import DeckViewCompact from "./DeckViewCompact";

// Extensible view registry — future views (stacks, curve columns…) register
// here and automatically appear in the DeckMenu view switcher.
export interface DeckViewDef {
  id: string;
  label: string;
  Component: ComponentType;
}

export const DECK_VIEWS: DeckViewDef[] = [
  { id: "grid", label: "Card images", Component: DeckViewGrid },
  { id: "compact", label: "Compact list", Component: DeckViewCompact },
];

export function deckViewById(id: string): DeckViewDef {
  return DECK_VIEWS.find((v) => v.id === id) ?? DECK_VIEWS[0];
}
