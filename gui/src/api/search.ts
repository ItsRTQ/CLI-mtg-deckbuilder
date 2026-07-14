import { api } from "./client";
import { CardResult } from "./mock";

export interface SearchFilters {
  commandersOnly?: boolean;
  colors?: string;       // "WUG"
  type?: string;         // creature / instant / ...
  oracle?: string;       // oracle text contains
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
  if (filters.oracle?.trim()) params.set("oracle", filters.oracle.trim());
  if (filters.mvGte?.trim()) params.set("mv_gte", filters.mvGte.trim());
  if (filters.mvLte?.trim()) params.set("mv_lte", filters.mvLte.trim());
  if (filters.maxPrice?.trim()) params.set("max_price", filters.maxPrice.trim());
  if (filters.rarity) params.set("rarity", filters.rarity);
  params.set("limit", String(PAGE_SIZE));
  params.set("offset", String(page * PAGE_SIZE));
  return api<SearchPage>(`/api/cards/search?${params}`);
}

export async function resolveCard(name: string): Promise<CardResult> {
  return api<CardResult>(`/api/cards/${encodeURIComponent(name)}`);
}
