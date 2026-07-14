import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { CardResult } from "../api/mock";
import ManaCost from "./ManaCost";

// Commander name input with typeahead — suggestions come from the DB filtered by
// the exact can_be_commander flag (not just "legendary creature"). With
// commandersOnly={false} it doubles as a general card picker (any DB card).
export default function CommanderInput({
  value,
  onChange,
  placeholder,
  commandersOnly = true,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  commandersOnly?: boolean;
}) {
  const [sugg, setSugg] = useState<CardResult[]>([]);
  const [open, setOpen] = useState(false);
  const chosen = useRef(false);   // a just-selected name shouldn't re-open the list

  useEffect(() => {
    if (chosen.current) {
      chosen.current = false;
      return;
    }
    const term = value.trim();
    if (term.length < 2) {
      setSugg([]);
      setOpen(false);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const params = new URLSearchParams({ name: term, limit: "8" });
        if (commandersOnly) params.set("commanders_only", "true");
        const res = await api<{ results: CardResult[] }>(
          `/api/cards/search?${params}`);
        setSugg(res.results);
        setOpen(res.results.length > 0);
      } catch {
        setOpen(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [value]);

  function select(name: string) {
    chosen.current = true;
    onChange(name);
    setOpen(false);
  }

  return (
    <div className="autocomplete">
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => sugg.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && open && sugg.length > 0) {
            e.preventDefault();
            select(sugg[0].name);
          }
          if (e.key === "Escape") setOpen(false);
        }}
        placeholder={placeholder}
      />
      {open && (
        <div className="suggestions">
          {sugg.map((s) => (
            <div
              key={s.name}
              className="suggestion"
              // onMouseDown fires BEFORE the input's blur closes the list
              onMouseDown={() => select(s.name)}
            >
              <span>{s.name}</span>
              <ManaCost cost={s.mana_cost} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
