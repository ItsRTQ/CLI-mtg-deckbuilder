import { useEffect, useRef, useState } from "react";
import { useDeckWorkspace } from "../../state/DeckWorkspaceContext";
import { DECK_VIEWS } from "./deckViews";

// Burger menu on the Deck Builder header. role=menu with focus management:
// opens focusing the first item, Escape/outside-click closes and returns
// focus to the trigger.
interface Props {
  viewId: string;
  onPickView: (id: string) => void;
  onImport: () => void;
  onStats: () => void;
}

export default function DeckMenu({ viewId, onPickView, onImport, onStats }: Props) {
  const { deck, clearDeck, closeDeck } = useDeckWorkspace();
  const [open, setOpen] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [copied, setCopied] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    setConfirmClear(false);
    setCopied(false);
    menuRef.current?.querySelector<HTMLElement>("[role=menuitem],[role=menuitemradio]")?.focus();
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  function close(refocus = true) {
    setOpen(false);
    if (refocus) btnRef.current?.focus();
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      e.stopPropagation();
      close();
      return;
    }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLElement>(
      "[role=menuitem]:not(:disabled),[role=menuitemradio]:not(:disabled)") ?? []);
    if (!items.length) return;
    const at = items.indexOf(document.activeElement as HTMLElement);
    const next = e.key === "ArrowDown"
      ? items[(at + 1) % items.length]
      : items[(at - 1 + items.length) % items.length];
    next.focus();
  }

  async function copyList() {
    if (!deck) return;
    try {
      await navigator.clipboard.writeText(deck.decklist);
      setCopied(true);
    } catch {
      /* clipboard unavailable */
    }
  }

  if (!deck) return null;
  return (
    <div className="deck-menu-wrap" ref={wrapRef} onKeyDown={onKeyDown}>
      <button ref={btnRef} className="ghost" title="Deck menu"
              aria-haspopup="menu" aria-expanded={open}
              onClick={() => setOpen(!open)}>
        ☰
      </button>
      {open && (
        <div className="deck-menu" role="menu" ref={menuRef}
             aria-label="Deck actions">
          <div className="deck-menu-group" role="group" aria-label="Deck view">
            {DECK_VIEWS.map((v) => (
              <button key={v.id} role="menuitemradio"
                      aria-checked={viewId === v.id}
                      onClick={() => { onPickView(v.id); close(); }}>
                {viewId === v.id ? "◉" : "○"} {v.label}
              </button>
            ))}
          </div>
          <hr />
          <button role="menuitem"
                  onClick={() => { close(false); onImport(); }}>
            ⬇ Import from text…
          </button>
          <button role="menuitem"
                  onClick={() => { close(false); onStats(); }}>
            📊 Statistics…
          </button>
          <button role="menuitem" onClick={copyList}>
            {copied ? "✓ Copied" : "📋 Copy decklist"}
          </button>
          <hr />
          {!confirmClear ? (
            <button role="menuitem" onClick={() => setConfirmClear(true)}>
              🗑 Clear deck…
            </button>
          ) : (
            <button role="menuitem" className="danger"
                    onClick={() => { clearDeck(); close(); }}>
              🗑 Really clear all cards? (undoable)
            </button>
          )}
          <button role="menuitem" onClick={() => { closeDeck(); close(false); }}>
            ⇄ Switch deck
          </button>
        </div>
      )}
    </div>
  );
}
