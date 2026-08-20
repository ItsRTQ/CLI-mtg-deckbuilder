import {
  createContext, useCallback, useContext, useMemo, useRef, useState,
} from "react";
import { CardResult } from "../api/mock";
import { Membership } from "../components/CardTile";
import {
  DeckDetail, createDeck as apiCreateDeck, getDeck, listDecks, patchDeckCards,
  replaceDeckList as apiReplaceList,
} from "../api/decks";
import { saveWorkspacePrefs } from "./workspacePrefs";

// Single source of truth for the workspace's open deck. EVERY mutation path
// (click-add, drop, stepper, clear, import-merge, undo) funnels through one
// serialized `mutate()` — one in-flight PATCH at a time, because every edit
// can RENAME the deck folder (the response's `name` is authoritative).

type Inverse =
  | { kind: "patch"; add: string[]; remove: string[] }
  | { kind: "list"; decklist: string };

const UNDO_CAP = 20;

interface DeckWorkspaceValue {
  deck: DeckDetail | null;
  deckVersion: number;             // bumps per successful mutation (stats refetch key)
  loading: boolean;
  error: string | null;            // last mutation/load error (transient toast)
  clearError: () => void;
  liveMessage: string;             // aria-live feed (rendered by the provider)
  pendingNames: ReadonlySet<string>;
  membershipFor: (card: CardResult) => Membership;
  quantityOf: (name: string) => number;
  openDeck: (name: string) => Promise<void>;
  closeDeck: () => void;
  createNewDeck: (commander: string) => Promise<boolean>;
  addCard: (name: string) => Promise<boolean>;
  removeCard: (name: string) => Promise<boolean>;
  changeQty: (name: string, delta: number) => Promise<boolean>;
  mergeCards: (entries: { name: string; quantity: number }[]) => Promise<boolean>;
  replaceList: (decklist: string) => Promise<{ skipped: string[] } | null>;
  clearDeck: () => Promise<boolean>;
  undo: () => Promise<boolean>;
  canUndo: boolean;
  dragCard: CardResult | null;     // set by the search pane on dragstart/dragend
  setDragCard: (c: CardResult | null) => void;
  // Recommendations → search pane bridge: a gap's "find candidates" publishes a
  // prefilled search here; CardSearch consumes it (seq disambiguates repeats).
  searchRequest: SearchRequest | null;
  requestSearch: (f: Omit<SearchRequest, "seq">) => void;
}

export interface SearchRequest {
  tags?: string[];
  query?: string;
  type?: string;
  colors?: string;
  seq: number;
}

const Ctx = createContext<DeckWorkspaceValue | null>(null);

export function useDeckWorkspace(): DeckWorkspaceValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useDeckWorkspace outside DeckWorkspaceProvider");
  return v;
}

const low = (s: string) => s.toLowerCase();
const front = (s: string) => low(s).split("//")[0].split("/")[0].trim();

export function DeckWorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [deck, setDeck] = useState<DeckDetail | null>(null);
  const [deckVersion, setDeckVersion] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveMessage, setLiveMessage] = useState("");
  const [pendingNames, setPendingNames] = useState<ReadonlySet<string>>(new Set());
  const [canUndo, setCanUndo] = useState(false);
  const [dragCard, setDragCard] = useState<CardResult | null>(null);
  const [searchRequest, setSearchRequest] = useState<SearchRequest | null>(null);
  const searchSeq = useRef(0);

  const deckRef = useRef<DeckDetail | null>(null);   // latest snapshot for queued jobs
  const queueRef = useRef<Promise<unknown>>(Promise.resolve());
  const undoRef = useRef<Inverse[]>([]);

  const announce = useCallback((msg: string) => setLiveMessage(msg), []);

  function commit(detail: DeckDetail) {
    deckRef.current = detail;
    setDeck(detail);
    setDeckVersion((v) => v + 1);
    saveWorkspacePrefs({ lastDeckName: detail.name });
  }

  async function refresh(name: string) {
    commit(await getDeck(name));
  }

  // A 404 mid-session means the deck folder was renamed/deleted elsewhere
  // (Collection modal, explain job). Re-match by commander; else back to the
  // picker with an explanation.
  async function recoverStale(e: any): Promise<boolean> {
    if (e?.status !== 404 || !deckRef.current) return false;
    const commander = deckRef.current.commander;
    try {
      const { decks } = await listDecks();
      const match = commander
        ? decks.find((x) => x.commander?.toLowerCase() === commander.toLowerCase())
        : null;
      if (match) {
        await refresh(match.name);
        setError(`The deck was renamed elsewhere — reloaded as "${match.name}". Retry your change.`);
        return true;
      }
    } catch { /* fall through */ }
    deckRef.current = null;
    setDeck(null);
    saveWorkspacePrefs({ lastDeckName: null });
    setError("This deck no longer exists — it was deleted or moved elsewhere.");
    return true;
  }

  // Edits pause while an agent job (build/explain) runs: the job owns and
  // renames deck folders — a concurrent PATCH would race it.
  async function agentGuard(): Promise<boolean> {
    const { agentBusyMessage } = await import("../api/builds");
    const busy = await agentBusyMessage();
    if (busy) setError(busy);
    return !!busy;
  }

  const openDeck = useCallback(async (name: string) => {
    setLoading(true);
    setError(null);
    try {
      commit(await getDeck(name));
      undoRef.current = [];
      setCanUndo(false);
    } catch (e: any) {
      // stale lastDeckName (deleted/renamed while away) → back to the picker
      if (e?.status === 404) saveWorkspacePrefs({ lastDeckName: null });
      else setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const closeDeck = useCallback(() => {
    deckRef.current = null;
    setDeck(null);
    undoRef.current = [];
    setCanUndo(false);
    saveWorkspacePrefs({ lastDeckName: null });
  }, []);

  const createNewDeck = useCallback(async (commander: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiCreateDeck(commander);
      commit(await getDeck(res.build_name));
      undoRef.current = [];
      setCanUndo(false);
      announce(`Deck created for ${commander}`);
      return true;
    } catch (e: any) {
      setError(e.message);
      return false;
    } finally {
      setLoading(false);
    }
  }, [announce]);

  function pushUndo(inv: Inverse) {
    undoRef.current.push(inv);
    if (undoRef.current.length > UNDO_CAP) undoRef.current.shift();
    setCanUndo(true);
  }

  /** THE shared mutation path. `job` runs against the LATEST deck snapshot
   * (queued jobs see predecessors' renames/quantities); returns the names to
   * mark pending, the request, its inverse, and the announcement. */
  function mutate(
    job: (d: DeckDetail) => {
      payload: { add?: string[]; remove?: string[] };
      inverse: Inverse | null;      // null = not undoable (undo itself)
      announceMsg: (d: DeckDetail) => string;
      pending: string[];
    } | null,
  ): Promise<boolean> {
    const run = async (): Promise<boolean> => {
      const d = deckRef.current;
      if (!d) return false;
      const step = job(d);
      if (!step) return false;
      if (await agentGuard()) return false;
      const marks = new Set(step.pending.map(low));
      setPendingNames((cur) => new Set([...cur, ...marks]));
      try {
        const res = await patchDeckCards(d.name, step.payload);
        await refresh(res.name);
        if (step.inverse) pushUndo(step.inverse);
        announce(step.announceMsg(deckRef.current!));
        return true;
      } catch (e: any) {
        if (!(await recoverStale(e))) setError(e.message);
        return false;
      } finally {
        setPendingNames((cur) => {
          const next = new Set(cur);
          marks.forEach((m) => next.delete(m));
          return next;
        });
      }
    };
    const p = queueRef.current.then(run, run);
    queueRef.current = p.catch(() => undefined);
    return p;
  }

  const addCard = useCallback((name: string) => mutate(() => ({
    payload: { add: [name] },
    inverse: { kind: "patch", add: [], remove: [name] },
    announceMsg: (d) => `${name} added — ${d.stats.total_cards} cards`,
    pending: [name],
  })), []);

  const removeCard = useCallback((name: string) => mutate((d) => {
    // remove the ENTRY: basics need their name repeated quantity times
    const entry = d.cards.find(
      (c) => c.section !== "commander" && low(c.name) === low(name));
    if (!entry) return null;
    const isBasic = (entry.type_line ?? "").toLowerCase().includes("basic");
    const repeats = isBasic ? entry.quantity : 1;
    return {
      payload: { remove: Array(repeats).fill(entry.name) },
      inverse: { kind: "patch", add: Array(repeats).fill(entry.name), remove: [] },
      announceMsg: (nd) => `${entry.name} removed — ${nd.stats.total_cards} cards`,
      pending: [entry.name],
    };
  }), []);

  const changeQty = useCallback((name: string, delta: number) => mutate((d) => {
    if (delta === 0) return null;
    const entry = d.cards.find(
      (c) => c.section !== "commander" && low(c.name) === low(name));
    if (delta < 0) {
      if (!entry) return null;
      const n = Math.min(-delta, entry.quantity);   // never over-remove
      return {
        payload: { remove: Array(n).fill(entry.name) },
        inverse: { kind: "patch", add: Array(n).fill(entry.name), remove: [] },
        announceMsg: (nd) => `${entry.name} −${n} — ${nd.stats.total_cards} cards`,
        pending: [entry.name],
      };
    }
    const cname = entry?.name ?? name;
    return {
      payload: { add: Array(delta).fill(cname) },
      inverse: { kind: "patch", add: [], remove: Array(delta).fill(cname) },
      announceMsg: (nd) => `${cname} +${delta} — ${nd.stats.total_cards} cards`,
      pending: [cname],
    };
  }), []);

  // import-merge: one atomic PATCH; quantities become repeated names (basics
  // merge server-side; the preview already filtered dupes/violations out)
  const mergeCards = useCallback((entries: { name: string; quantity: number }[]) =>
    mutate(() => {
      const add = entries.flatMap((e) => Array(Math.max(1, e.quantity)).fill(e.name));
      if (!add.length) return null;
      return {
        payload: { add },
        inverse: { kind: "patch", add: [], remove: add },
        announceMsg: (d) => `Imported ${add.length} cards — ${d.stats.total_cards} total`,
        pending: entries.map((e) => e.name),
      };
    }), []);

  const clearDeck = useCallback(() => mutate((d) => {
    const remove: string[] = [];
    for (const c of d.cards) {
      if (c.section === "commander") continue;
      const isBasic = (c.type_line ?? "").toLowerCase().includes("basic");
      for (let i = 0; i < (isBasic ? c.quantity : 1); i++) remove.push(c.name);
    }
    if (!remove.length) return null;
    return {
      payload: { remove },
      inverse: { kind: "list", decklist: d.decklist },
      announceMsg: () => "Deck cleared",
      pending: [],
    };
  }), []);

  // PUT /list (import-replace, undo of clear/replace). Serialized on the same
  // queue as the PATCHes.
  const replaceList = useCallback((decklist: string) => {
    const run = async (): Promise<{ skipped: string[] } | null> => {
      const d = deckRef.current;
      if (!d) return null;
      if (await agentGuard()) return null;
      const prior = d.decklist;
      try {
        const res = await apiReplaceList(d.name, decklist);
        await refresh(res.name);
        pushUndo({ kind: "list", decklist: prior });
        announce(`Deck list replaced — ${deckRef.current!.stats.total_cards} cards`);
        return { skipped: res.skipped };
      } catch (e: any) {
        if (!(await recoverStale(e))) setError(e.message);
        return null;
      }
    };
    const p = queueRef.current.then(run, run);
    queueRef.current = p.catch(() => undefined);
    return p;
  }, [announce]);

  const undo = useCallback(() => {
    const run = async (): Promise<boolean> => {
      const d = deckRef.current;
      if (!d || undoRef.current.length === 0) return false;
      if (await agentGuard()) return false;
      const inv = undoRef.current.pop()!;
      setCanUndo(undoRef.current.length > 0);
      try {
        if (inv.kind === "list") {
          const res = await apiReplaceList(d.name, inv.decklist);
          await refresh(res.name);
        } else {
          const res = await patchDeckCards(d.name, {
            add: inv.add, remove: inv.remove,
          });
          await refresh(res.name);
        }
        announce(`Undone — ${deckRef.current!.stats.total_cards} cards`);
        return true;
      } catch (e: any) {
        if (!(await recoverStale(e))) setError(e.message);
        return false;
      }
    };
    const p = queueRef.current.then(run, run);
    queueRef.current = p.catch(() => undefined);
    return p;
  }, [announce]);

  // O(1) membership: lowercased full name AND DFC front face → entry.
  const memberMap = useMemo(() => {
    const m = new Map<string, { quantity: number; isBasic: boolean; commander: boolean }>();
    if (!deck) return m;
    for (const c of deck.cards) {
      const v = {
        quantity: c.quantity,
        isBasic: (c.type_line ?? "").toLowerCase().includes("basic"),
        commander: c.section === "commander",
      };
      m.set(low(c.name), v);
      m.set(front(c.name), v);
    }
    return m;
  }, [deck]);

  const identity = useMemo(
    () => new Set(deck?.color_identity ?? []), [deck]);

  const membershipFor = useCallback((card: CardResult): Membership => {
    const pending = pendingNames.has(low(card.name));
    const hit = memberMap.get(low(card.name)) ?? memberMap.get(front(card.name));
    if (hit) {
      return {
        state: hit.commander || !hit.isBasic ? "limit" : "in",
        quantity: hit.quantity,
        pending,
      };
    }
    if (deck && (card.color_identity ?? []).some((c) => !identity.has(c))) {
      return { state: "illegal", quantity: 0, pending };
    }
    return { state: "none", quantity: 0, pending };
  }, [memberMap, identity, deck, pendingNames]);

  const quantityOf = useCallback(
    (name: string) => memberMap.get(low(name))?.quantity ?? 0, [memberMap]);

  const value: DeckWorkspaceValue = {
    deck, deckVersion, loading, error,
    clearError: useCallback(() => setError(null), []),
    liveMessage, pendingNames, membershipFor, quantityOf,
    openDeck, closeDeck, createNewDeck,
    addCard, removeCard, changeQty, mergeCards, replaceList, clearDeck,
    undo, canUndo, dragCard, setDragCard,
    searchRequest,
    requestSearch: useCallback((f: Omit<SearchRequest, "seq">) => {
      searchSeq.current += 1;
      setSearchRequest({ ...f, seq: searchSeq.current });
    }, []),
  };

  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="sr-only" aria-live="polite" role="status">
        {liveMessage}
      </div>
    </Ctx.Provider>
  );
}
