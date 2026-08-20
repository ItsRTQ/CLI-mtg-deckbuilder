import { api } from "./client";
import { CardResult } from "./mock";

export interface SearchFilters {
  commandersOnly?: boolean;
  colors?: string;       // "WUG"
  type?: string;         // creature / instant / ...
  oracleTerms?: string[]; // oracle text fragments — AND semantics (repeatable param)
  mvGte?: string;        // numbers kept as strings from inputs
  mvLte?: string;
  maxPrice?: string;
  rarity?: string;       // common | uncommon | rare | mythic
}

export interface SearchPage {
  count: number;
  offset: number;
  has_more: boolean;
  results: CardResult[];
}

export const PAGE_SIZE = 15;

export async function search(
  q: string,
  filters: SearchFilters,
  page = 0,
): Promise<SearchPage> {
  const params = new URLSearchParams();
  const query = filters.commandersOnly ? `type:legendary ${q}`.trim() : q.trim();
  if (query) params.set("q", query);
  if (filters.commandersOnly) params.set("type", "creature");
  else if (filters.type) params.set("type", filters.type);
  if (filters.colors) params.set("colors", filters.colors);
  for (const t of filters.oracleTerms ?? []) {
    if (t.trim()) params.append("oracle", t.trim());
  }
  if (filters.mvGte?.trim()) params.set("mv_gte", filters.mvGte.trim());
  if (filters.mvLte?.trim()) params.set("mv_lte", filters.mvLte.trim());
  if (filters.maxPrice?.trim()) params.set("max_price", filters.maxPrice.trim());
  if (filters.rarity) params.set("rarity", filters.rarity);
  params.set("limit", String(PAGE_SIZE));
  params.set("offset", String(page * PAGE_SIZE));
  return api<SearchPage>(`/api/cards/search?${params}`);
}

/** Function-first search (the CLI's `search-tags`): tags' phrases UNION,
 * ranked by tag_match_count. Powers the deck-gaps "find candidates" flow. */
export async function searchTags(
  tags: string[],
  opts: { colors?: string; type?: string; mvLte?: string; maxPrice?: string },
  page = 0,
): Promise<SearchPage> {
  const params = new URLSearchParams();
  for (const t of tags) params.append("tags", t);
  if (opts.colors) params.set("colors", opts.colors);
  if (opts.type) params.set("type", opts.type);
  if (opts.mvLte?.trim()) params.set("mv_lte", opts.mvLte.trim());
  if (opts.maxPrice?.trim()) params.set("max_price", opts.maxPrice.trim());
  params.set("limit", String(PAGE_SIZE));
  params.set("offset", String(page * PAGE_SIZE));
  return api<SearchPage>(`/api/cards/search-tags?${params}`);
}

export async function resolveCard(name: string): Promise<CardResult> {
  return api<CardResult>(`/api/cards/${encodeURIComponent(name)}`);
}
