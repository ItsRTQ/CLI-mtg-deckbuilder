import { useEffect, useState } from "react";
import { CardResult } from "../api/mock";
import { CardTile, CardZoom, Membership } from "./CardTile";
import { PAGE_SIZE, SearchFilters, SearchPage } from "../api/search";

const COLORS = ["W", "U", "B", "R", "G"] as const;
const TYPES = ["", "creature", "instant", "sorcery", "artifact", "enchantment",
               "planeswalker", "land"] as const;

interface CardSearchProps {
  /** Present = embedded in the workspace: tiles get a "+" add button. */
  onAdd?: (card: CardResult) => void;
  /** Deck-membership lookup for the overlay states (in ×N / limit / illegal). */
  membership?: (card: CardResult) => Membership;
  /** Dragstart/dragend relay so the deck pane can preview drop validity. */
  onDragCard?: (card: CardResult | null) => void;
}

// The card/commander search — on Home (prop-less) and embedded in the
// workspace search pane (all props optional; absent = today's behavior).
export default function CardSearch({ onAdd, membership, onDragCard }: CardSearchProps = {}) {
  const [q, setQ] = useState("");
  // default OFF: the toggle lives inside Advanced now — a hidden ON filter would
  // silently empty searches like "Lightning Bolt"
  const [commandersOnly, setCommandersOnly] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [colors, setColors] = useState<string[]>([]);
  const [type, setType] = useState("");
  const [oracle, setOracle] = useState("");
  const [mvGte, setMvGte] = useState("");
  const [mvLte, setMvLte] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [rarity, setRarity] = useState("");
  const [page, setPage] = useState(0);
  const [results, setResults] = useState<CardResult[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [zoom, setZoom] = useState<CardResult | null>(null);

  const filters: SearchFilters = {
    commandersOnly,
    colors: colors.join("") || undefined,
    type: type || undefined,
    oracle: oracle || undefined,
    mvGte, mvLte, maxPrice,
    rarity: rarity || undefined,
  };
  const hasAnyFilter =
    q.trim() || colors.length || type || oracle.trim() || mvGte || mvLte ||
    maxPrice || rarity;

  // new query/filters -> back to page 0
  useEffect(() => {
    setPage(0);
  }, [q, commandersOnly, colors.join(""), type, oracle, mvGte, mvLte, maxPrice, rarity]);

  useEffect(() => {
    if (!hasAnyFilter) {
      setResults([]);
      setSearched(false);
      return;
    }
    const t = setTimeout(async () => {
      setBusy(true);
      setError(null);
      try {
        const { search } = await import("../api/search");
        const pageRes: SearchPage = await search(q, filters, page);
        setResults(pageRes.results);
        setHasMore(pageRes.has_more);
        setSearched(true);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setBusy(false);
      }
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, commandersOnly, colors.join(""), type, oracle, mvGte, mvLte, maxPrice, rarity, page]);

  function toggleColor(c: string) {
    setColors((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]));
  }

  return (
    <div className="card">
      <h2>Card search</h2>
      <div className="row">
        <div style={{ flex: 1 }}>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder='e.g. "Kiki-Jiki" or oracle:proliferate'
          />
        </div>
        <button className="ghost" onClick={() => setAdvanced(!advanced)}>
          {advanced ? "Advanced ▴" : "Advanced ▾"}
        </button>
      </div>
      {advanced && (
        <div className="advanced">
          <div className="row">
            <label style={{ whiteSpace: "nowrap" }}>
              <input
                type="checkbox"
                checked={commandersOnly}
                onChange={(e) => setCommandersOnly(e.target.checked)}
                style={{ width: "auto", marginRight: "0.4rem" }}
              />
              commanders only
            </label>
            <div>
              <label>Color identity</label>
              <div className="row" style={{ gap: "0.35rem" }}>
                {COLORS.map((c) => (
                  <button
                    key={c}
                    className={`pip pip-${c} ${colors.includes(c) ? "on" : ""}`}
                    onClick={() => toggleColor(c)}
                    title={c}
                  >
                    <img src={`/mana/${c}.svg`} alt={c} />
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label>Type</label>
              <select value={type} onChange={(e) => setType(e.target.value)}
                      disabled={commandersOnly} title={commandersOnly ? "commanders only = legendary creatures" : ""}>
                {TYPES.map((t) => (
                  <option key={t} value={t}>{t || "any"}</option>
                ))}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: "10rem" }}>
              <label>Oracle text contains</label>
              <input value={oracle} onChange={(e) => setOracle(e.target.value)}
                     placeholder='e.g. "create a token"' />
            </div>
            <div style={{ width: "5.5rem" }}>
              <label>MV ≥</label>
              <input value={mvGte} onChange={(e) => setMvGte(e.target.value)}
                     inputMode="numeric" placeholder="0" />
            </div>
            <div style={{ width: "5.5rem" }}>
              <label>MV ≤</label>
              <input value={mvLte} onChange={(e) => setMvLte(e.target.value)}
                     inputMode="numeric" placeholder="16" />
            </div>
            <div style={{ width: "7rem" }}>
              <label>Max price $</label>
              <input value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)}
                     inputMode="decimal" placeholder="any" />
            </div>
            <div>
              <label>Rarity</label>
              <select value={rarity} onChange={(e) => setRarity(e.target.value)}>
                <option value="">any</option>
                <option value="common">common</option>
                <option value="uncommon">uncommon</option>
                <option value="rare">rare</option>
                <option value="mythic">mythic</option>
              </select>
            </div>
          </div>
        </div>
      )}
      {busy && <p className="muted">searching…</p>}
      {error && <p className="error">{error}</p>}
      {results.length > 0 && (
        <div className="results-wrap">
          {searched && (page > 0 || hasMore) && (
            <button className="pager-btn left" title="Previous page"
                    disabled={page === 0 || busy}
                    onClick={() => setPage(page - 1)}>
              ‹
            </button>
          )}
          <div className="card-grid">
            {results.map((c) => {
              const m = membership?.(c);
              return (
                <CardTile
                  key={c.name}
                  card={c}
                  onZoom={() => setZoom(c)}
                  overlay={m}
                  onDragCard={onDragCard}
                  action={onAdd ? {
                    title: m?.state === "limit" ? "Copy limit reached"
                      : m?.state === "illegal" ? "Outside the deck's color identity"
                      : "Add to deck",
                    onClick: () => onAdd(c),
                    disabled: m?.state === "limit" || m?.state === "illegal",
                  } : undefined}
                />
              );
            })}
          </div>
          {searched && (page > 0 || hasMore) && (
            <button className="pager-btn right" title="Next page"
                    disabled={!hasMore || busy}
                    onClick={() => setPage(page + 1)}>
              ›
            </button>
          )}
        </div>
      )}
      {searched && !busy && results.length === 0 && (
        <p className="muted">
          no results{page > 0 ? " on this page" : ""}
          {page > 0 && (
            <button className="ghost" style={{ marginLeft: "0.6rem" }}
                    onClick={() => setPage(page - 1)}>← back</button>
          )}
        </p>
      )}
      {searched && (page > 0 || hasMore) && results.length > 0 && (
        <p className="muted" style={{ textAlign: "center", marginBottom: 0 }}>
          page {page + 1}
        </p>
      )}
      {searched && results.length === PAGE_SIZE && !hasMore && (
        <p className="muted" style={{ textAlign: "center" }}>end of results</p>
      )}
      {zoom && <CardZoom card={zoom} onClose={() => setZoom(null)} />}
    </div>
  );
}
