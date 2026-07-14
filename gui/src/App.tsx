import { useRef, useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import Home from "./routes/Home";
import Settings from "./routes/Settings";
import Collection from "./routes/Collection";
import BuildWizard from "./routes/BuildWizard";
import Results from "./routes/Results";
import Workspace from "./routes/Workspace";
import BuildBanner from "./components/BuildBanner";
import { api } from "./api/client";

export default function App() {
  const { pathname } = useLocation();
  const [dropReady, setDropReady] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout>>();

  function showToast(msg: string) {
    setToast(msg);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3500);
  }

  async function onDropCard(e: React.DragEvent) {
    e.preventDefault();
    setDropReady(false);
    const name = e.dataTransfer.getData("application/x-mtg-card")
      || e.dataTransfer.getData("text/plain");
    if (!name) return;
    try {
      const res = await api<{ name: string; added: boolean; count: number }>(
        "/api/bulk/add", { method: "POST", body: JSON.stringify({ name }) });
      showToast(res.added
        ? `✓ ${res.name} added to your collection (${res.count} cards)`
        : `${res.name} is already in your collection`);
    } catch (err: any) {
      showToast(`✗ ${err.message}`);
    }
  }

  return (
    <div className="shell">
      <BuildBanner />
      <nav className="nav">
        <span className="brand">mtg gui</span>
        <NavLink to="/">Home</NavLink>
        <NavLink
          to="/collection"
          className={dropReady ? "drop-ready" : ""}
          onDragOver={(e) => {
            if (e.dataTransfer.types.includes("application/x-mtg-card")
                || e.dataTransfer.types.includes("text/plain")) {
              e.preventDefault();               // makes the link a valid drop target
              e.dataTransfer.dropEffect = "copy";
              setDropReady(true);
            }
          }}
          onDragLeave={() => setDropReady(false)}
          onDrop={onDropCard}
        >
          Collection
        </NavLink>
        <NavLink to="/workspace">Workspace</NavLink>
        <NavLink to="/build">Build Wizard</NavLink>
        <NavLink to="/results">Results</NavLink>
        <NavLink to="/settings">Settings</NavLink>
      </nav>
      {toast && <div className="toast">{toast}</div>}
      <main className={`main${pathname === "/workspace" ? " main-wide" : ""}`}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/collection" element={<Collection />} />
          <Route path="/workspace" element={<Workspace />} />
          <Route path="/build" element={<BuildWizard />} />
          <Route path="/results" element={<Results />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
