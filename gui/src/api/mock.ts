// Mock data, flipped OFF per feature as the real endpoints land:
//   Task 6 wires search  -> MOCK_SEARCH = false
//   Task 7 wires providers -> MOCK_PROVIDERS = false
//   Task 8 wires builds  -> MOCK_BUILDS = false
export const MOCK_SEARCH = false;
export const MOCK_PROVIDERS = false; // Settings.tsx talks to /api/providers directly now
export const MOCK_BUILDS = false; // BuildWizard/Results talk to /api/builds now

export interface CardResult {
  name: string;
  mana_cost?: string | null;
  mana_value?: number | null;
  type_line?: string | null;
  oracle_text?: string | null;
  color_identity?: string[] | null;
  usd_price?: number | null;
  image_url?: string | null;
  rarity?: string | null;
}

export const mockCards: CardResult[] = [
  {
    name: "Kiki-Jiki, Mirror Breaker",
    mana_cost: "{2}{R}{R}{R}",
    mana_value: 5,
    type_line: "Legendary Creature — Goblin Shaman",
    oracle_text:
      "{T}: Create a token that's a copy of target nonlegendary creature you control...",
    color_identity: ["R"],
    usd_price: 12.5,
  },
  {
    name: "Ragost, Deft Gastronaut",
    mana_cost: "{1}{R}{W}",
    mana_value: 3,
    type_line: "Legendary Creature — Slug Employee",
    oracle_text: "Whenever a Food you control is sacrificed...",
    color_identity: ["R", "W"],
    usd_price: 0.35,
  },
];

export interface ProviderInfo {
  name: string;
  installed: boolean;
  version?: string | null;
  detail?: string | null;
}

export const mockProviders: ProviderInfo[] = [
  { name: "claude-code", installed: true, version: "2.x (mock)" },
  { name: "ollama", installed: false, detail: "detection-only in v0.9.0" },
];

export interface BuildJob {
  job_id: string;
  status: "pending" | "running" | "validating" | "succeeded" | "failed" | "timeout" | "cancelled";
  phase: string;
  elapsed_seconds: number;
  log_tail?: string[];
  result?: {
    decklist?: { name: string; quantity: number }[];   // build jobs
    deck_name?: string;                                 // explain jobs
    explanation?: string;
    saved_to?: string;
    build_name?: string;
    save_warning?: string;
  } | null;
  error?: { type: string; message: string } | null;
}

let mockTick = 0;
export function mockJobStatus(jobId: string): BuildJob {
  mockTick += 1;
  if (mockTick < 4) {
    return {
      job_id: jobId,
      status: "running",
      phase: "agent drafting packages",
      elapsed_seconds: mockTick * 2,
      log_tail: [
        "mtg commander-analyze --commander \"Kiki-Jiki, Mirror Breaker\" ...",
        "mtg deck-add --cards \"Sol Ring;Arcane Signet\" --purpose ramp ...",
        "(mock build in progress...)",
      ],
    };
  }
  return {
    job_id: jobId,
    status: "succeeded",
    phase: "done",
    elapsed_seconds: 8,
    result: {
      decklist: [
        { name: "Kiki-Jiki, Mirror Breaker (Commander)", quantity: 1 },
        { name: "Sol Ring", quantity: 1 },
        { name: "Zealous Conscripts", quantity: 1 },
        { name: "Mountain", quantity: 32 },
      ],
      explanation: "Mock deck — the real agent build lands in Task 8.",
    },
  };
}
