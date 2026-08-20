import { useEffect, useState } from "react";
import { DeckGaps, GapFill, getDeckGaps } from "../../api/decks";
import { useDeckWorkspace } from "../../state/DeckWorkspaceContext";

// Recommendations panel: the deck-gaps audit (category targets + oracle hooks
// + the analyzer's commander plan check) rendered as actionable rows — each
// gap's "Find candidates" prefills the search pane with the gap's fill spec.
// The targets are experience-grounded GUIDANCE, not law (BUILDER §10).

const ARCHETYPES = [
  "midrange", "go_wide_aggro", "go_tall_aggro", "voltron", "aristocrats",
  "spellslinger", "value_engine", "reanimator", "blink", "lifegain",
  "graveyard_value", "artifacts", "enchantress", "stompy", "battlecruiser",
  "group_slug", "stax", "pillowfort", "theft", "mill", "tribal",
];

export default function GapsModal({ onClose }: { onClose: () => void }) {
  const { deck, deckVersion, requestSearch } = useDeckWorkspace();
  const [archetype, setArchetype] = useState("midrange");
  const [gaps, setGaps] = useState<DeckGaps | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!deck) return;
    let stop = false;
    setGaps(null);
    setError(null);
    getDeckGaps(deck.name, archetype)
      .then((g) => !stop && setGaps(g))
      .catch((e) => !stop && setError(e.message));
    return () => { stop = true; };
  }, [deck?.name, deckVersion, archetype]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!deck) return null;

  function findCandidates(fill: GapFill) {
    requestSearch({
      tags: fill.tags.length ? fill.tags : undefined,
      query: fill.query ?? undefined,
      type: fill.type ?? undefined,
      colors: fill.colors || deck?.color_identity.join(""),
    });
    onClose();
  }

  const clean = gaps && !gaps.gaps.length && !gaps.hook_gaps.length
    && !gaps.plan_gaps.length;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal wide" role="dialog" aria-modal="true"
           aria-label="Deck recommendations" onClick={(e) => e.stopPropagation()}>
        <h2>Recommendations — {deck.commander ?? deck.name}</h2>
        <div className="row" style={{ alignItems: "center", gap: "0.5rem" }}>
          <label htmlFor="gaps-archetype" className="muted">Audit as archetype</label>
          <select id="gaps-archetype" value={archetype}
                  onChange={(e) => setArchetype(e.target.value)}>
            {ARCHETYPES.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        {error && <p className="error" style={{ whiteSpace: "pre-wrap" }}>{error}</p>}
        {!gaps && !error && <p className="muted">auditing…</p>}
        {clean && (
          <p className="gaps-clean">
            ✓ No major gaps: the deck covers its category targets and the
            commander's plan.
          </p>
        )}
        {gaps && (
          <div className="gaps-body">
            {gaps.gaps.length > 0 && (
              <>
                <h3>Thin categories <span className="muted">(ranked by need)</span></h3>
                {gaps.gaps.map((g) => (
                  <div key={g.category} className="gap-row">
                    <div className="gap-info">
                      <strong>{g.display_name}</strong>
                      <span> — have {g.have}, want ≥ {g.want_at_least}</span>
                      {g.recommended_range && (
                        <span className="muted"> (range {g.recommended_range})</span>
                      )}
                    </div>
                    <button onClick={() => findCandidates(g.fill)}
                            title={`Search ${g.fill.tags.join(", ")} in ${g.fill.colors || "any colors"}`}>
                      Find candidates →
                    </button>
                  </div>
                ))}
              </>
            )}
            {gaps.hook_gap_fills.length > 0 && (
              <>
                <h3>Commander hooks</h3>
                {gaps.hook_gap_fills.map((h) => (
                  <div key={h.message} className="gap-row">
                    <div className="gap-info">{h.message}</div>
                    <button onClick={() => findCandidates(h.fill)}>
                      Find candidates →
                    </button>
                  </div>
                ))}
              </>
            )}
            {gaps.plan_gaps.length > 0 && (
              <>
                <h3>Commander plan check</h3>
                <p className="muted" style={{ margin: "0 0 0.4rem", fontSize: "0.8rem" }}>
                  The analyzer reads these plans in the commander&apos;s own text —
                  the deck is thin on cards that serve them.
                </p>
                {gaps.plan_gaps.map((g) => (
                  <div key={g.archetype} className="gap-row">
                    <div className="gap-info">
                      <strong>{g.archetype}</strong>
                      <span className="muted"> ({g.band})</span>
                      <span> — {g.have}/{g.want_at_least} cards serve it</span>
                      {g.cards.length > 0 && (
                        <div className="muted gap-counted">
                          counted: {g.cards.slice(0, 6).join(", ")}
                          {g.cards.length > 6 ? `, +${g.cards.length - 6} more` : ""}
                        </div>
                      )}
                    </div>
                    <button onClick={() => findCandidates(g.fill)}>
                      Find candidates →
                    </button>
                  </div>
                ))}
              </>
            )}
            <p className="muted" style={{ fontSize: "0.78rem", marginBottom: 0 }}>
              Targets are experience-grounded guidance, not rules — your plan
              may legitimately want fewer.
            </p>
          </div>
        )}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: "0.8rem" }}>
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
