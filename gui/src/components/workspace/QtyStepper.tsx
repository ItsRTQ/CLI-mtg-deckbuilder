import { useEffect, useRef } from "react";
import { useDeckWorkspace } from "../../state/DeckWorkspaceContext";

// Quantity stepper for BASICS only (nonbasics are singleton). Rapid clicks
// accumulate locally and flush as ONE repeated-name PATCH after 350ms idle —
// the serialized mutation queue then sees a single job per burst.
export default function QtyStepper({ name, quantity }: { name: string; quantity: number }) {
  const { changeQty } = useDeckWorkspace();
  const delta = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => () => clearTimeout(timer.current), []);

  function bump(d: number) {
    delta.current += d;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const n = delta.current;
      delta.current = 0;
      if (n !== 0) changeQty(name, n);
    }, 350);
  }

  // never queue below zero: cap the visible decrement at the current quantity
  const canDec = quantity + Math.min(delta.current, 0) > 0;

  return (
    <span className="qty-stepper" onClick={(e) => e.stopPropagation()}>
      <button aria-label={`Remove one ${name}`} disabled={!canDec}
              onClick={() => bump(-1)}>−</button>
      <button aria-label={`Add one ${name}`} onClick={() => bump(1)}>+</button>
    </span>
  );
}
