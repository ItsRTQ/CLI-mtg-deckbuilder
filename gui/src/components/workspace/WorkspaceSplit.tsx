import { useEffect, useRef } from "react";
import { WorkspaceLayout } from "../../state/workspacePrefs";

// The 4 layouts are ONE flex container with a fixed DOM order (deck, splitter,
// search) — only flex-direction changes, so React never remounts the panes and
// their internal state (search results, zoom, scroll) survives every switch.
const DIRS: Record<WorkspaceLayout, "row" | "row-reverse" | "column" | "column-reverse"> = {
  "deck-left": "row",
  "deck-right": "row-reverse",
  "deck-top": "column",
  "deck-bottom": "column-reverse",
};

const MIN = 20, MAX = 80;
const clamp = (p: number) => Math.min(MAX, Math.max(MIN, p));

interface Props {
  layout: WorkspaceLayout;
  splitPct: number;                       // deck pane share (committed)
  onSplitCommit: (pct: number) => void;
  deck: React.ReactNode;
  search: React.ReactNode;
  /** Narrow (tabbed) mode: the inactive pane is CSS-hidden but stays MOUNTED
   * (state survives tab flips); the splitter is disabled. */
  narrowTab?: "deck" | "search" | null;
}

export default function WorkspaceSplit({
  layout, splitPct, onSplitCommit, deck, search, narrowTab = null,
}: Props) {
  const splitterDisabled = narrowTab !== null;
  const containerRef = useRef<HTMLDivElement>(null);
  const deckRef = useRef<HTMLElement>(null);
  const liveRef = useRef(splitPct);       // last value written during a drag

  const horizontal = layout === "deck-left" || layout === "deck-right";
  const reversed = layout === "deck-right" || layout === "deck-bottom";

  // Sync the pane's flex-basis on commit/layout change. During a drag we write
  // the style directly (no re-render per pointermove — same philosophy as the
  // card tilt FX).
  useEffect(() => {
    liveRef.current = splitPct;
    if (deckRef.current) deckRef.current.style.flexBasis = `${splitPct}%`;
  }, [splitPct, layout]);

  function pctFromPointer(e: PointerEvent | React.PointerEvent): number {
    const rect = containerRef.current!.getBoundingClientRect();
    const raw = horizontal
      ? ((e.clientX - rect.left) / rect.width) * 100
      : ((e.clientY - rect.top) / rect.height) * 100;
    return clamp(reversed ? 100 - raw : raw);
  }

  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    if (splitterDisabled) return;
    const handle = e.currentTarget;
    handle.setPointerCapture(e.pointerId);
    const move = (ev: PointerEvent) => {
      const pct = pctFromPointer(ev);
      liveRef.current = pct;
      if (deckRef.current) deckRef.current.style.flexBasis = `${pct}%`;
    };
    const up = () => {
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", up);
      handle.removeEventListener("pointercancel", up);
      onSplitCommit(liveRef.current);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", up);
    handle.addEventListener("pointercancel", up);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (splitterDisabled) return;
    // Arrows follow the handle's VISUAL movement; reversed layouts flip sign.
    const sign = reversed ? -1 : 1;
    let next: number | null = null;
    if (horizontal && e.key === "ArrowLeft") next = splitPct - 2 * sign;
    else if (horizontal && e.key === "ArrowRight") next = splitPct + 2 * sign;
    else if (!horizontal && e.key === "ArrowUp") next = splitPct - 2 * sign;
    else if (!horizontal && e.key === "ArrowDown") next = splitPct + 2 * sign;
    else if (e.key === "Home") next = MIN;
    else if (e.key === "End") next = MAX;
    if (next !== null) {
      e.preventDefault();
      onSplitCommit(clamp(next));
    }
  }

  return (
    <div
      ref={containerRef}
      className={`workspace-split${narrowTab ? " ws-narrow" : ""}`}
      style={{ flexDirection: DIRS[layout] }}
    >
      <section
        ref={deckRef}
        className={`ws-pane ws-pane-deck${narrowTab === "search" ? " ws-hidden" : ""}`}
        aria-label="Deck builder"
        aria-hidden={narrowTab === "search" || undefined}
      >
        {deck}
      </section>
      <div
        className={`ws-splitter${splitterDisabled ? " ws-splitter-off" : ""}`}
        role="separator"
        tabIndex={splitterDisabled ? -1 : 0}
        aria-label="Resize panels"
        aria-orientation={horizontal ? "vertical" : "horizontal"}
        aria-valuenow={Math.round(splitPct)}
        aria-valuemin={MIN}
        aria-valuemax={MAX}
        onPointerDown={onPointerDown}
        onKeyDown={onKeyDown}
      />
      <section
        className={`ws-pane ws-pane-search${narrowTab === "deck" ? " ws-hidden" : ""}`}
        aria-label="Card search"
        aria-hidden={narrowTab === "deck" || undefined}
      >
        {search}
      </section>
    </div>
  );
}
