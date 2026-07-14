// Workspace UI preferences — pure client presentation state, so localStorage
// (gui_settings.json is backend-consumed config; POSTing on splitter drags
// would be API noise). Versioned key; corrupt/blocked storage → defaults.

export type WorkspaceLayout =
  | "deck-left"      // row:            Deck | Search
  | "deck-right"     // row-reverse:    Search | Deck
  | "deck-top"       // column:         Deck / Search
  | "deck-bottom";   // column-reverse: Search / Deck

export interface WorkspacePrefs {
  layout: WorkspaceLayout;
  splitPct: number;              // deck pane share, clamped 20..80
  deckView: string;              // deckViews registry id
  lastDeckName: string | null;
  narrowTab: "deck" | "search";  // active tab in narrow (stacked-tabs) mode
}

const KEY = "mtg.gui.workspace.v1";

export const DEFAULT_PREFS: WorkspacePrefs = {
  layout: "deck-left",
  splitPct: 45,
  deckView: "grid",
  lastDeckName: null,
  narrowTab: "deck",
};

const LAYOUTS: WorkspaceLayout[] = [
  "deck-left", "deck-right", "deck-top", "deck-bottom",
];

export function loadWorkspacePrefs(): WorkspacePrefs {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULT_PREFS };
    const p = JSON.parse(raw);
    return {
      layout: LAYOUTS.includes(p.layout) ? p.layout : DEFAULT_PREFS.layout,
      splitPct:
        typeof p.splitPct === "number" && isFinite(p.splitPct)
          ? Math.min(80, Math.max(20, p.splitPct))
          : DEFAULT_PREFS.splitPct,
      deckView: typeof p.deckView === "string" && p.deckView
        ? p.deckView
        : DEFAULT_PREFS.deckView,
      lastDeckName: typeof p.lastDeckName === "string" ? p.lastDeckName : null,
      narrowTab: p.narrowTab === "search" ? "search" : "deck",
    };
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export function saveWorkspacePrefs(patch: Partial<WorkspacePrefs>): void {
  try {
    const next = { ...loadWorkspacePrefs(), ...patch };
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* private mode / quota — prefs just don't persist */
  }
}
