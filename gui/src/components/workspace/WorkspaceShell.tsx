import { useEffect, useState } from "react";
import {
  loadWorkspacePrefs, saveWorkspacePrefs, DEFAULT_PREFS,
  WorkspaceLayout, WorkspacePrefs,
} from "../../state/workspacePrefs";
import WorkspaceSplit from "./WorkspaceSplit";

// Narrow screens drop the split for Deck|Search tabs (both panes stay mounted).
function useNarrow(): boolean {
  const [narrow, setNarrow] = useState(
    () => window.matchMedia("(max-width: 900px)").matches);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 900px)");
    const fn = (e: MediaQueryListEvent) => setNarrow(e.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);
  return narrow;
}

const LAYOUT_OPTIONS: { id: WorkspaceLayout; glyph: string; label: string }[] = [
  { id: "deck-left", glyph: "◧", label: "Deck left, search right" },
  { id: "deck-right", glyph: "◨", label: "Search left, deck right" },
  { id: "deck-top", glyph: "⬒", label: "Deck top, search bottom" },
  { id: "deck-bottom", glyph: "⬓", label: "Search top, deck bottom" },
];

interface Props {
  deckPane: React.ReactNode;
  searchPane: React.ReactNode;
  toolbarExtra?: React.ReactNode;   // undo button etc. (later phases)
}

export default function WorkspaceShell({ deckPane, searchPane, toolbarExtra }: Props) {
  const [prefs, setPrefs] = useState<WorkspacePrefs>(loadWorkspacePrefs);
  const narrow = useNarrow();

  function update(patch: Partial<WorkspacePrefs>) {
    setPrefs((p) => ({ ...p, ...patch }));
    saveWorkspacePrefs(patch);
  }

  return (
    <div className="workspace">
      <div className="ws-toolbar">
        {narrow ? (
          <div className="ws-layouts" role="tablist" aria-label="Workspace panel">
            {(["deck", "search"] as const).map((t) => (
              <button
                key={t}
                role="tab"
                className={`ghost ws-layout-btn${prefs.narrowTab === t ? " active" : ""}`}
                aria-selected={prefs.narrowTab === t}
                onClick={() => update({ narrowTab: t })}
              >
                {t === "deck" ? "Deck" : "Search"}
              </button>
            ))}
          </div>
        ) : (
          <div className="ws-layouts" role="group" aria-label="Workspace layout">
            {LAYOUT_OPTIONS.map((o) => (
              <button
                key={o.id}
                className={`ghost ws-layout-btn${prefs.layout === o.id ? " active" : ""}`}
                title={o.label}
                aria-label={o.label}
                aria-pressed={prefs.layout === o.id}
                onClick={() => update({ layout: o.id })}
              >
                {o.glyph}
              </button>
            ))}
            <button
              className="ghost ws-layout-btn"
              title="Reset layout"
              aria-label="Reset layout and split size"
              onClick={() => update({
                layout: DEFAULT_PREFS.layout,
                splitPct: DEFAULT_PREFS.splitPct,
              })}
            >
              ↺
            </button>
          </div>
        )}
        {toolbarExtra}
      </div>
      <WorkspaceSplit
        layout={prefs.layout}
        splitPct={prefs.splitPct}
        onSplitCommit={(pct) => update({ splitPct: pct })}
        deck={deckPane}
        search={searchPane}
        narrowTab={narrow ? prefs.narrowTab : null}
      />
    </div>
  );
}
