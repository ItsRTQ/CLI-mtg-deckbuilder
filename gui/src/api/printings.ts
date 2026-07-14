// Printings source — today Scryfall live, fetched only when a zoom opens.
// Single module so a future local source (e.g. a per-printing SQLite table
// behind /api/cards/{name}/printings) swaps in without touching consumers.

export interface PrintingPrices {
  usd: string | null;
  usd_foil: string | null;
  usd_etched: string | null;
}

export interface Printing {
  set: string | null;
  collector_number: string | null;
  rarity: string | null;   // per-printing: the same card can be rare in one set, mythic in another
  image: string;   // large-ish, for the zoom
  thumb: string;   // normal, for grids (what gets persisted)
  finishes: string[];       // nonfoil / foil / etched
  promo_types: string[];    // surgefoil, galaxyfoil, confettifoil, texturedfoil...
  border_color: string | null;
  frame_effects: string[];  // showcase, extendedart...
  frame: string | null;     // "1997" = retro frame
  prices: PrintingPrices;   // per-printing (the DB only knows the cheapest-print price)
}

// All printings of a card, live from the Scryfall API (CORS-enabled). Only
// called when a zoom opens; failure just means "no print switching".
export async function fetchPrintings(name: string): Promise<Printing[]> {
  const q = encodeURIComponent(`!"${name}"`);
  const res = await fetch(
    `https://api.scryfall.com/cards/search?order=released&unique=prints&q=${q}`);
  if (!res.ok) return [];
  const data = await res.json();
  return (data.data ?? [])
    .map((c: any) => {
      const uris = c.image_uris ?? c.card_faces?.[0]?.image_uris ?? {};
      return {
        set: (c.set ?? "").toUpperCase() || null,
        collector_number: c.collector_number ?? null,
        rarity: c.rarity ?? null,
        image: uris.large ?? uris.normal ?? "",
        thumb: uris.normal ?? uris.large ?? "",
        finishes: c.finishes ?? [],
        promo_types: c.promo_types ?? [],
        border_color: c.border_color ?? null,
        frame_effects: c.frame_effects ?? [],
        frame: c.frame ?? null,
        prices: {
          usd: c.prices?.usd ?? null,
          usd_foil: c.prices?.usd_foil ?? null,
          usd_etched: c.prices?.usd_etched ?? null,
        },
      };
    })
    .filter((p: Printing) => p.image);
}

// scan URLs embed the printing's uuid — lets us start the cycle on the CURRENT art
export function scanId(url?: string | null): string | null {
  const m = url?.match(/([0-9a-f]{8}-[0-9a-f-]{27,})/i);
  return m ? m[1] : null;
}

// The price label for a printing as the user cycles: its own USD, else its
// foil/etched USD, else "n/a — found $X" (X = the card's regular DB price we
// show everywhere), else plain "n/a".
export function printingPriceLabel(p: Printing, regularUsd?: number | null): string {
  if (p.prices.usd) return `$${p.prices.usd}`;
  if (p.prices.usd_foil) return `$${p.prices.usd_foil} (foil)`;
  if (p.prices.usd_etched) return `$${p.prices.usd_etched} (etched)`;
  return regularUsd != null ? `n/a — found $${regularUsd.toFixed(2)}` : "n/a";
}
