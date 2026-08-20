// Shared deck-library API: types + section order + calls used by both the
// Collection page and the deck-building Workspace. The `section` strings come
// from the SERVER (library.py _section_of — single source: the Deck model's
// _PRIMARY_TYPE_ORDER); this list only fixes display order and labels.
import { api } from "./client";
import { CardResult } from "./mock";

export interface DeckSummary {
  name: string;
  card_count: number | null;
  has_explanation: boolean;
  commander: string | null;
  tier: string | null;
  rank: string | null;
  cost_usd: number | null;
  art_url: string | null;
}
export interface Decks {
  dir: string | null;
  decks: DeckSummary[];
}
export interface DeckCard extends CardResult {
  quantity: number;
  section: string;
}
export interface DeckStats {
  total_cards: number;
  known_price: number;
  avg_mv_nonland: number | null;
  section_counts: Record<string, number>;
}
export interface DeckDetail {
  name: string;
  decklist: string;
  explanation: string | null;
  commander: string | null;
  color_identity: string[];
  cards: DeckCard[];
  stats: DeckStats;
}
export interface DeckRichStats {
  total_cards: number;
  mana_curve: Record<string, number>;
  mana_curve_score: number | null;
  ideal_curve: Record<string, number>;
  avg_mv: number | null;
  median_mv: number | null;
  land_count: number;
  total_price: number;
  total_price_by_type: Record<string, number>;
  card_type_counts: Record<string, number>;
  color_pips: Record<string, number>;
  color_cards: Record<string, number>;
  color_sources: Record<string, number>;
  rank: { score: number; band: number; band_name: string } | null;
}
export interface DeckPreviewEntry {
  name: string;
  quantity: number;
  section: string;
  image_url: string | null;
  usd_price: number | null;
}
export interface DeckPreview {
  resolved: DeckPreviewEntry[];
  skipped: string[];
  already_in_deck: string[];
  color_violations: string[];
  projected_size: number;
  max_size: number;
}

export const SECTIONS: [string, string][] = [
  ["commander", "Commander"],
  ["creatures", "Creatures"],
  ["planeswalkers", "Planeswalkers"],
  ["battles", "Battles"],
  ["sorceries", "Sorceries"],
  ["instants", "Instants"],
  ["artifacts", "Artifacts"],
  ["enchantments", "Enchantments"],
  ["lands", "Lands"],
  ["other", "Other"],
];

const enc = encodeURIComponent;

export function listDecks(): Promise<Decks> {
  return api<Decks>("/api/decks");
}

export function getDeck(name: string): Promise<DeckDetail> {
  return api<DeckDetail>(`/api/decks/${enc(name)}`);
}

export function createDeck(commander: string, decklist?: string) {
  return api<{ build_name: string; imported: number; skipped: string[] }>(
    "/api/decks",
    { method: "POST", body: JSON.stringify({ commander, decklist }) },
  );
}

/** Atomic add/remove. Repeated names are quantity semantics for BASICS
 * (decrement/merge per occurrence) — never repeat a name more times than the
 * deck's current quantity. Response `name` is the (possibly renamed) folder. */
export function patchDeckCards(
  name: string,
  payload: { add?: string[]; remove?: string[] },
) {
  return api<{ name: string; added: string[]; removed: string[] }>(
    `/api/decks/${enc(name)}/cards`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

export function replaceDeckList(name: string, decklist: string) {
  return api<{ name: string; imported: number; skipped: string[] }>(
    `/api/decks/${enc(name)}/list`,
    { method: "PUT", body: JSON.stringify({ decklist }) },
  );
}

/** Dry-run import preview — persists nothing. */
export function previewDeckList(
  name: string,
  decklist: string,
  mode: "merge" | "replace",
) {
  return api<DeckPreview>(`/api/decks/${enc(name)}/list/preview`, {
    method: "POST",
    body: JSON.stringify({ decklist, mode }),
  });
}

export function getDeckStats(name: string): Promise<DeckRichStats> {
  return api<DeckRichStats>(`/api/decks/${enc(name)}/stats`);
}

// deck-gaps audit (single source with `mtg deck-gaps`). `fill` is the
// structured search spec the workspace turns into a prefilled card search.
export interface GapFill {
  tags: string[];
  query: string | null;
  type: string | null;
  colors: string;
}
export interface CategoryGap {
  category: string;
  display_name: string;
  have: number;
  want_at_least: number;
  recommended_range: string | null;
  need_score: number;
  fill: GapFill;
}
export interface PlanGap {
  archetype: string;
  band: string;
  have: number;
  cards: string[];
  want_at_least: number;
  fill: GapFill;
}
export interface DeckGaps {
  commander: string;
  archetype: string;
  colors: string;
  gaps: CategoryGap[];
  hook_gaps: string[];
  hook_gap_fills: { message: string; fill: GapFill }[];
  analyzer_support: { archetype: string; band: string; have?: number; cards?: string[] }[];
  plan_gaps: PlanGap[];
}

export function getDeckGaps(name: string, archetype = "midrange"): Promise<DeckGaps> {
  return api<DeckGaps>(`/api/decks/${enc(name)}/gaps?archetype=${enc(archetype)}`);
}

// Agent advisory pass (Tier 2): a batch job — start it, poll /api/builds/{id}.
// Every suggested card comes back DB-verified (valid/issue set server-side).
export interface AdviseCard {
  name: string;
  why: string;
  price_usd: number | null;
  valid?: boolean;
  issue?: string;
  image_url?: string | null;
}
export interface AdviseRecommendation {
  title: string;
  priority: "high" | "medium" | "low";
  reason: string;
  cards: AdviseCard[];
  fill: GapFill | null;
}
export interface AdviseResult {
  deck_name: string | null;
  summary: string;
  recommendations: AdviseRecommendation[];
}

export function startAdvise(
  name: string,
  opts: { theme?: string | null; budget?: string | null; notes?: string | null } = {},
): Promise<{ job_id: string }> {
  return api<{ job_id: string }>(`/api/decks/${enc(name)}/advise`, {
    method: "POST",
    body: JSON.stringify(opts),
  });
}

export function exportTcgplayerUrl(name: string) {
  return api<{ url: string; entries: number }>(
    `/api/decks/${enc(name)}/export/tcgplayer`,
  );
}

/** Open the deck on TCGplayer Mass Entry. Opens the tab synchronously (before the
 * await) so popup blockers see it inside the user gesture, then navigates it. */
export async function openTcgplayer(name: string): Promise<void> {
  const w = window.open("", "_blank");
  try {
    const { url } = await exportTcgplayerUrl(name);
    if (w) w.location.href = url;
    else window.open(url, "_blank");
  } catch (e) {
    w?.close();
    throw e;
  }
}
