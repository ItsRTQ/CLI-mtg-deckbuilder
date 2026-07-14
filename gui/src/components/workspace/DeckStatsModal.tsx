import { useEffect, useState } from "react";
import { DeckRichStats, getDeckStats } from "../../api/decks";
import { useDeckWorkspace } from "../../state/DeckWorkspaceContext";

const CURVE_ORDER = ["0", "1", "2", "3", "4", "5", "6", "7+"];
const WUBRG = ["W", "U", "B", "R", "G"];
const COLOR_NAMES: Record<string, string> = {
  W: "White", U: "Blue", B: "Black", R: "Red", G: "Green",
};

// Deck statistics without leaving the builder. Lazy: fetches on open, and
// refetches ONLY when deckVersion changes (never during drag/hover).
export default function DeckStatsModal({ onClose }: { onClose: () => void }) {
  const { deck, deckVersion } = useDeckWorkspace();
  const [stats, setStats] = useState<DeckRichStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!deck) return;
    let stop = false;
    getDeckStats(deck.name)
      .then((s) => !stop && (setStats(s), setError(null)))
      .catch((e) => !stop && setError(e.message));
    return () => { stop = true; };
  }, [deck?.name, deckVersion]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!deck) return null;
  const nonland = stats
    ? CURVE_ORDER.reduce((s, b) => s + (stats.mana_curve[b] ?? 0), 0)
    : 0;
  // Ideal overlay = IDEAL_CURVE share × nonland count; peak covers both series
  // so an over-ideal bar and its marker stay inside the chart.
  const ideal = (b: string) =>
    stats ? (stats.ideal_curve?.[b] ?? 0) * nonland : 0;
  const peak = stats
    ? Math.max(1, ...CURVE_ORDER.map((b) =>
        Math.max(stats.mana_curve[b] ?? 0, ideal(b))))
    : 1;
  const colorRows = stats
    ? WUBRG.filter((c) =>
        (stats.color_pips[c] ?? 0) > 0 || (stats.color_cards[c] ?? 0) > 0 ||
        (stats.color_sources[c] ?? 0) > 0)
    : [];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal wide" role="dialog" aria-modal="true"
           aria-label="Deck statistics" onClick={(e) => e.stopPropagation()}>
        <h2>Statistics — {deck.commander ?? deck.name}</h2>
        {error && <p className="error" style={{ whiteSpace: "pre-wrap" }}>{error}</p>}
        {!stats && !error && <p className="muted">loading…</p>}
        {stats && (
          <>
            <div className="deck-stats">
              <span><strong>{stats.total_cards}</strong> cards</span>
              <span><strong>{stats.land_count}</strong> lands</span>
              <span><strong>${stats.total_price.toFixed(2)}</strong> known price</span>
              {stats.avg_mv != null && (
                <span><strong>{stats.avg_mv}</strong> avg mv</span>
              )}
              {stats.median_mv != null && (
                <span><strong>{stats.median_mv}</strong> median mv</span>
              )}
              {stats.mana_curve_score != null && (
                <span><strong>{stats.mana_curve_score}</strong>/10 curve score</span>
              )}
              {stats.rank && (
                <span title="deck-rank: POWER/speed band from DB facts — fast mana, tutors, curve (consider-only)">
                  <strong>{stats.rank.band_name}</strong> rank {stats.rank.score}/10
                </span>
              )}
            </div>
            <h3>Mana curve <span className="muted">(nonland)</span></h3>
            <div className="curve-chart" role="img"
                 aria-label={`Mana curve: ${CURVE_ORDER
                   .map((b) => `${b}: ${stats.mana_curve[b] ?? 0}`).join(", ")}`}>
              {CURVE_ORDER.map((b) => {
                const n = stats.mana_curve[b] ?? 0;
                const ideal_n = ideal(b);
                return (
                  <div key={b} className="curve-col">
                    <span className="curve-count">{n || ""}</span>
                    <div className="curve-area">
                      <div className="curve-bar"
                           style={{ height: `${(n / peak) * 100}%` }} />
                      {nonland > 0 && (
                        <div className="curve-ideal"
                             title={`ideal ≈ ${ideal_n.toFixed(1)}`}
                             style={{ bottom: `${(ideal_n / peak) * 100}%` }} />
                      )}
                    </div>
                    <span className="muted">{b}</span>
                  </div>
                );
              })}
            </div>
            {nonland > 0 && (
              <p className="muted" style={{ margin: "0.2rem 0 0", fontSize: "0.78rem" }}>
                ─ ─ ideal curve (Commander midrange shape, scaled to {nonland} nonland cards)
              </p>
            )}
            <div className="columns" style={{ marginTop: "0.8rem" }}>
              <div>
                <h3>Cards by type</h3>
                <table className="stats-table">
                  <tbody>
                    {Object.entries(stats.card_type_counts).map(([t, n]) => (
                      <tr key={t}>
                        <td>{t}</td>
                        <td className="num">{n}</td>
                        <td className="num muted">
                          {stats.total_price_by_type[t] != null
                            ? `$${stats.total_price_by_type[t].toFixed(2)}`
                            : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {colorRows.length > 0 && (
                <div>
                  <h3>Color analysis</h3>
                  <table className="stats-table">
                    <thead>
                      <tr className="muted">
                        <th />
                        <th className="num" title="colored mana symbols in nonland casting costs">pips</th>
                        <th className="num" title="nonland cards of this color identity">cards</th>
                        <th className="num" title="permanents that produce this color (lands, rocks, dorks)">sources</th>
                      </tr>
                    </thead>
                    <tbody>
                      {colorRows.map((c) => (
                        <tr key={c}>
                          <td><span className={`color-dot ${c}`} />{COLOR_NAMES[c]}</td>
                          <td className="num">{stats.color_pips[c] ?? 0}</td>
                          <td className="num">{stats.color_cards[c] ?? 0}</td>
                          <td className="num">{stats.color_sources[c] ?? 0}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: "0.8rem" }}>
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
